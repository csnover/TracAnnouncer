# -*- coding: utf-8 -*-
#
# Copyright (c) 2008, Stephen Hansen
# Copyright (c) 2009, Robert Corsaro
# Copyright (c) 2010, Steffen Hoffmann
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <ORGANIZATION> nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------

# TODO: pick format based on subscription.  For now users will use the same
#       format for all announcements, but in the future we can make this more
#       flexible, since it's in the subscription table.

import Queue
import random
import re
import smtplib
import sys
import threading
import time

from email.Charset import Charset, QP, BASE64
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import formatdate, formataddr
try:
    from email.header import Header
except:
    from email.Header import Header
from subprocess import Popen, PIPE

from trac.config import BoolOption, ExtensionOption, IntOption, Option, \
                        OrderedExtensionsOption, ChoiceOption
from trac.core import *
from trac.util import get_pkginfo, md5
from trac.util.compat import set, sorted
from trac.util.datefmt import to_timestamp
from trac.util.text import CRLF, to_unicode

from announcer.api import AnnouncementSystem
from announcer.api import IAnnouncementAddressResolver
from announcer.api import IAnnouncementDistributor
from announcer.api import IAnnouncementFormatter
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import IAnnouncementProducer
from announcer.api import _

from announcer.util.mail import set_header
from announcer.util.mail_crypto import CryptoTxt


class IEmailSender(Interface):
    """Extension point interface for components that allow sending e-mail."""

    def send(self, from_addr, recipients, message):
        """Send message to recipients."""


class IAnnouncementEmailDecorator(Interface):
    def decorate_message(event, message, decorators):
        """Manipulate the message before it is sent on it's way.  The callee
        should call the next decorator by popping decorators and calling the
        popped decorator.  If decorators is empty, don't worry about it.
        """


class EmailDistributor(Component):

    implements(IAnnouncementDistributor)

    formatters = ExtensionPoint(IAnnouncementFormatter)
    # Make ordered
    decorators = ExtensionPoint(IAnnouncementEmailDecorator)

    resolvers = OrderedExtensionsOption('announcer', 'email_address_resolvers',
        IAnnouncementAddressResolver, 'SpecifiedEmailResolver, '\
        'SessionEmailResolver, DefaultDomainEmailResolver',
        """Comma seperated list of email resolver components in the order
        they will be called.  If an email address is resolved, the remaining
        resolvers will not be called.
        """)

    email_sender = ExtensionOption('announcer', 'email_sender',
        IEmailSender, 'SmtpEmailSender',
        """Name of the component implementing `IEmailSender`.

        This component is used by the announcer system to send emails.
        Currently, `SmtpEmailSender` and `SendmailEmailSender` are provided.
        """)

    enabled = BoolOption('announcer', 'email_enabled', 'true',
        """Enable email notification.""")

    email_from = Option('announcer', 'email_from', 'trac@localhost',
        """Sender address to use in notification emails.""")

    from_name = Option('announcer', 'email_from_name', '',
        """Sender name to use in notification emails.""")

    replyto = Option('announcer', 'email_replyto', 'trac@localhost',
        """Reply-To address to use in notification emails.""")

    mime_encoding = ChoiceOption('announcer', 'mime_encoding',
        ['base64', 'qp', 'none'],
        """Specifies the MIME encoding scheme for emails.

        Valid options are 'base64' for Base64 encoding, 'qp' for
        Quoted-Printable, and 'none' for no encoding. Note that the no encoding
        means that non-ASCII characters in text are going to cause problems
        with notifications.
        """)

    use_public_cc = BoolOption('announcer', 'use_public_cc', 'false',
        """Recipients can see email addresses of other CC'ed recipients.

        If this option is disabled (the default), recipients are put on BCC
        """)

    # used in email decorators, but not here
    subject_prefix = Option('announcer', 'email_subject_prefix',
                                 '__default__',
        """Text to prepend to subject line of notification emails.

        If the setting is not defined, then the [$project_name] prefix.
        If no prefix is desired, then specifying an empty option
        will disable it.
        """)

    to = Option('announcer', 'email_to', 'undisclosed-recipients: ;',
        'Default To: field')

    use_threaded_delivery = BoolOption('announcer', 'use_threaded_delivery',
        'false',
        """Do message delivery in a separate thread.

        Enabling this will improve responsiveness for requests that end up
        with an announcement being sent over email. It requires building
        Python with threading support enabled-- which is usually the case.
        To test, start Python and type 'import threading' to see
        if it raises an error.
        """)

    default_email_format = Option('announcer', 'default_email_format',
        'text/plain',
        """The default mime type of the email notifications.

        This can be overridden on a per user basis through the announcer
        preferences panel.
        """)

    rcpt_allow_regexp = Option('announcer', 'rcpt_allow_regexp', '',
        """A whitelist pattern to match any address to before adding to
        recipients list.
        """)

    rcpt_local_regexp = Option('announcer', 'rcpt_local_regexp', '',
        """A whitelist pattern to match any address, that should be
        considered local.

        This will be evaluated only if msg encryption is set too.
        Recipients with matching email addresses will continue to
        receive unencrypted email messages.
        """)

    crypto = Option('announcer', 'email_crypto', '',
        """Enable cryptographically operation on email msg body.

        Empty string, the default for unset, disables all crypto operations.
        Valid values are:
            sign          sign msg body with given privkey
            encrypt       encrypt msg body with pubkeys of all recipients
            sign,encrypt  sign, than encrypt msg body
        """)

    # get GnuPG configuration options
    gpg_binary = Option('announcer', 'gpg_binary', 'gpg',
        """GnuPG binary name, allows for full path too.

        Value 'gpg' is same default as in python-gnupg itself.
        For usual installations location of the gpg binary is auto-detected.
        """)

    gpg_home = Option('announcer', 'gpg_home', '',
        """Directory containing keyring files.

        In case of wrong configuration missing keyring files without content
        will be created in the configured location, provided necessary
        write permssion is granted for the corresponding parent directory.
        """)

    private_key = Option('announcer', 'gpg_signing_key', None,
        """Keyid of private key (last 8 chars or more) used for signing.

        If unset, a private key will be selected from keyring automagicly.
        The password must be available i.e. provided by running gpg-agent
        or empty (bad security). On failing to unlock the private key,
        msg body will get emptied.
        """)


    def __init__(self):
        self.delivery_queue = None
        self._init_pref_encoding()

    def get_delivery_queue(self):
        if not self.delivery_queue:
            self.delivery_queue = Queue.Queue()
            thread = DeliveryThread(self.delivery_queue, self.send)
            thread.start()
        return self.delivery_queue

    # IAnnouncementDistributor
    def transports(self):
        yield "email"

    def formats(self, transport, realm):
        "Find valid formats for transport and realm"
        formats = {}
        for f in self.formatters:
            for style in f.styles(transport, realm):
                formats[style] = f
        self.log.debug(
            "EmailDistributor has found the following formats capable "
            "of handling '%s' of '%s': %s"%(transport, realm,
                ', '.join(formats.keys())))
        if not formats:
            self.log.error("EmailDistributor is unable to continue " \
                    "without supporting formatters.")
        return formats

    def distribute(self, transport, recipients, event):
        found = False
        for supported_transport in self.transports():
            if supported_transport == transport:
                found = True
        if not self.enabled or not found:
            self.log.debug("EmailDistributer email_enabled set to false")
            return
        fmtdict = self.formats(transport, event.realm)
        if not fmtdict:
            self.log.error(
                "EmailDistributer No formats found for %s %s"%(
                    transport, event.realm))
            return
        msgdict = {}
        msgdict_encrypt = {}
        msg_pubkey_ids = []
        # compile pattern before use for better performance
        RCPT_ALLOW_RE = re.compile(self.rcpt_allow_regexp)
        RCPT_LOCAL_RE = re.compile(self.rcpt_local_regexp)

        if self.crypto != '':
            self.log.debug("EmailDistributor attempts crypto operation.")
            self.enigma = CryptoTxt(self.gpg_binary, self.gpg_home)

        for name, authed, addr in recipients:
            fmt = name and \
                self._get_preferred_format(event.realm, name, authed) or \
                self._get_default_format()
            if fmt not in fmtdict:
                self.log.debug(("EmailDistributer format %s not available " +
                    "for %s %s, looking for an alternative")%(
                        fmt, transport, event.realm))
                # If the fmt is not available for this realm, then try to find
                # an alternative
                oldfmt = fmt
                fmt = None
                for f in fmtdict.values():
                    fmt = f.alternative_style_for(
                            transport, event.realm, oldfmt)
                    if fmt: break
            if not fmt:
                self.log.error(
                    "EmailDistributer was unable to find a formatter " +
                    "for format %s"%k
                )
                continue
            rslvr = None
            if name and not addr:
                # figure out what the addr should be if it's not defined
                for rslvr in self.resolvers:
                    addr = rslvr.get_address_for_name(name, authed)
                    if addr: break
            if addr:
                self.log.debug("EmailDistributor found the " \
                        "address '%s' for '%s (%s)' via: %s"%(
                        addr, name, authed and \
                        'authenticated' or 'not authenticated',
                        rslvr.__class__.__name__))

                # ok, we found an addr, add the message
                # but wait, check for allowed rcpt first, if set
                if RCPT_ALLOW_RE.search(addr) is not None:
                    # check for local recipients now
                    local_match = RCPT_LOCAL_RE.search(addr)
                    if self.crypto in ['encrypt', 'sign,encrypt'] and \
                            local_match is None:
                        # search available public keys for matching UID
                        pubkey_ids = self.enigma.get_pubkey_ids(addr)
                        if len(pubkey_ids) > 0:
                            msgdict_encrypt.setdefault(fmt, set()).add((name,
                                                            authed, addr))
                            msg_pubkey_ids[len(msg_pubkey_ids):] = pubkey_ids
                            self.log.debug("EmailDistributor got pubkeys " \
                                "for %s: %s" % (addr, pubkey_ids))
                        else:
                            self.log.debug("EmailDistributor dropped %s " \
                                "after missing pubkey with corresponding " \
                                "address %s in any UID" % (name, addr))
                    else:
                        msgdict.setdefault(fmt, set()).add((name, authed,
                                                            addr))
                        if local_match is not None:
                            self.log.debug("EmailDistributor expected " \
                                "local delivery for %s to: %s" % (name, addr))
                else:
                    self.log.debug("EmailDistributor dropped %s for " \
                        "not matching allowed recipient pattern %s" % \
                        (addr, self.rcpt_allow_regexp))
            else:
                self.log.debug("EmailDistributor was unable to find an " \
                        "address for: %s (%s)"%(name, authed and \
                        'authenticated' or 'not authenticated'))
        for k, v in msgdict.items():
            if not v or not fmtdict.get(k):
                continue
            self.log.debug(
                "EmailDistributor is sending event as '%s' to: %s"%(
                    fmt, ', '.join(x[2] for x in v)))
            self._do_send(transport, event, k, v, fmtdict[k])
        for k, v in msgdict_encrypt.items():
            if not v or not fmtdict.get(k):
                continue
            self.log.debug(
                "EmailDistributor is sending encrypted info on event " \
                "as '%s' to: %s"%(fmt, ', '.join(x[2] for x in v)))
            self._do_send(transport, event, k, v, fmtdict[k], msg_pubkey_ids)

    def _get_default_format(self):
        return self.default_email_format

    def _get_preferred_format(self, realm, sid, authenticated):
        if authenticated is None:
            authenticated = 0
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT value
              FROM session_attribute
             WHERE sid=%s
               AND authenticated=%s
               AND name=%s
        """, (sid, int(authenticated), 'announcer_email_format_%s' % realm))
        result = cursor.fetchone()
        if result:
            chosen = result[0]
            self.log.debug("EmailDistributor determined the preferred format" \
                    " for '%s (%s)' is: %s"%(sid, authenticated and \
                    'authenticated' or 'not authenticated', chosen))
            return chosen
        else:
            return self._get_default_format()

    def _init_pref_encoding(self):
        self._charset = Charset()
        self._charset.input_charset = 'utf-8'
        pref = self.mime_encoding.lower()
        if pref == 'base64':
            self._charset.header_encoding = BASE64
            self._charset.body_encoding = BASE64
            self._charset.output_charset = 'utf-8'
            self._charset.input_codec = 'utf-8'
            self._charset.output_codec = 'utf-8'
        elif pref in ['qp', 'quoted-printable']:
            self._charset.header_encoding = QP
            self._charset.body_encoding = QP
            self._charset.output_charset = 'utf-8'
            self._charset.input_codec = 'utf-8'
            self._charset.output_codec = 'utf-8'
        elif pref == 'none':
            self._charset.header_encoding = None
            self._charset.body_encoding = None
            self._charset.input_codec = None
            self._charset.output_charset = 'ascii'
        else:
            raise TracError(_('Invalid email encoding setting: %s'%pref))

    def _message_id(self, realm):
        """Generate a predictable, but sufficiently unique message ID."""
        modtime = time.time()
        rand = random.randint(0,32000)
        s = '%s.%d.%d.%s' % (self.env.project_url,
                          modtime, rand,
                          realm.encode('ascii', 'ignore'))
        dig = md5(s).hexdigest()
        host = self.email_from[self.email_from.find('@') + 1:]
        msgid = '<%03d.%s@%s>' % (len(s), dig, host)
        return msgid

    def _filter_recipients(self, rcpt):
        return rcpt

    def _do_send(self, transport, event, format, recipients, formatter,
                 pubkey_ids=[]):

        output = formatter.format(transport, event.realm, format, event)

        # DEVEL: force message body plaintext style for crypto operations
        if self.crypto != '' and pubkey_ids != []:
            if self.crypto == 'sign':
                output = self.enigma.sign(output, self.private_key)
            elif self.crypto == 'encrypt':
                output = self.enigma.encrypt(output, pubkey_ids)
            elif self.crypto == 'sign,encrypt':
                output = self.enigma.sign_encrypt(output, pubkey_ids,
                                                     self.private_key)

            self.log.debug(output)
            self.log.debug(_("EmailDistributor crypto operaton successful."))
            alternate_output = None
        else:
            alternate_style = formatter.alternative_style_for(
                transport,
                event.realm,
                format
            )
            if alternate_style:
                alternate_output = formatter.format(
                    transport,
                    event.realm,
                    alternate_style,
                    event
                )
            else:
                alternate_output = None

        # sanity check
        if not self._charset.body_encoding:
            try:
                dummy = output.encode('ascii')
            except UnicodeDecodeError:
                raise TracError(_("Ticket contains non-ASCII chars. " \
                                  "Please change encoding setting"))

        rootMessage = MIMEMultipart("related")
        # TODO: is this good? (from jabber branch)
        #rootMessage.set_charset(self._charset)

        headers = dict()
        headers['Message-ID'] = self._message_id(event.realm)
        headers['Date'] = formatdate()
        from_header = formataddr((
            self.from_name or self.env.project_name,
            self.email_from
        ))
        headers['From'] = from_header
        headers['To'] = '"%s"'%(self.to)
        if self.use_public_cc:
            headers['Cc'] = ', '.join([x[2] for x in recipients if x])
        headers['Reply-To'] = self.replyto
        for k, v in headers.iteritems():
            set_header(rootMessage, k, v)

        rootMessage.preamble = 'This is a multi-part message in MIME format.'
        if alternate_output:
            parentMessage = MIMEMultipart('alternative')
            rootMessage.attach(parentMessage)

            alt_msg_format = 'html' in alternate_style and 'html' or 'plain'
            msgText = MIMEText(alternate_output, alt_msg_format)
            parentMessage.attach(msgText)
        else:
            parentMessage = rootMessage

        msg_format = 'html' in format and 'html' or 'plain'
        msgText = MIMEText(output, msg_format)
        del msgText['Content-Transfer-Encoding']
        msgText.set_charset(self._charset)
        parentMessage.attach(msgText)
        decorators = self._get_decorators()
        if len(decorators) > 0:
            decorator = decorators.pop()
            decorator.decorate_message(event, rootMessage, decorators)

        recip_adds = [x[2] for x in recipients if x]
        # Append any to, cc or bccs added to the recipient list
        for field in ('To', 'Cc', 'Bcc'):
            if rootMessage[field] and \
                    len(str(rootMessage[field]).split(',')) > 0:
                for addy in str(rootMessage[field]).split(','):
                    self._add_recipient(recip_adds, addy)
        # replace with localized bcc hint
        if headers['To'] == 'undisclosed-recipients: ;':
            set_header(rootMessage, 'To', _('undisclosed-recipients: ;'))

        self.log.debug("Content of recip_adds: %s" %(recip_adds))
        package = (from_header, recip_adds, rootMessage.as_string())
        start = time.time()
        if self.use_threaded_delivery:
            self.get_delivery_queue().put(package)
        else:
            self.send(*package)
        stop = time.time()
        self.log.debug("EmailDistributor took %s seconds to send."\
                %(round(stop-start,2)))

    def send(self, from_addr, recipients, message):
        """Send message to recipients via e-mail."""
        # Ensure the message complies with RFC2822: use CRLF line endings
        message = CRLF.join(re.split("\r?\n", message))
        self.email_sender.send(from_addr, recipients, message)

    def _get_decorators(self):
        return self.decorators[:]

    def _add_recipient(self, recipients, addy):
        if addy.strip() != '"undisclosed-recipients: ;"':
            recipients.append(addy)



class SmtpEmailSender(Component):
    """E-mail sender connecting to an SMTP server."""

    implements(IEmailSender)

    server = Option('smtp', 'server', 'localhost',
        """SMTP server hostname to use for email notifications.""")

    timeout = IntOption('smtp', 'timeout', 10,
        """SMTP server connection timeout. (requires python-2.6)""")

    port = IntOption('smtp', 'port', 25,
        """SMTP server port to use for email notification.""")

    user = Option('smtp', 'user', '',
        """Username for SMTP server.""")

    password = Option('smtp', 'password', '',
        """Password for SMTP server.""")

    use_tls = BoolOption('smtp', 'use_tls', 'false',
        """Use SSL/TLS to send notifications over SMTP.""")

    use_ssl = BoolOption('smtp', 'use_ssl', 'false',
        """Use ssl for smtp connection.""")

    debuglevel = IntOption('smtp', 'debuglevel', 0,
        """Set to 1 for useful smtp debugging on stdout.""")


    def send(self, from_addr, recipients, message):
        # use defaults to make sure connect() is called in the constructor
        smtpclass = smtplib.SMTP
        if self.use_ssl:
            smtpclass = smtplib.SMTP_SSL

        args = {
            'host': self.server,
            'port': self.port
        }
        # timeout isn't supported until python 2.6
        vparts = sys.version_info[0:2]
        if vparts[0] >= 2 and vparts[1] >= 6:
            args['timeout'] = self.timeout

        smtp = smtpclass(**args)
        smtp.set_debuglevel(self.debuglevel)
        if self.use_tls:
            smtp.ehlo()
            if not smtp.esmtp_features.has_key('starttls'):
                raise TracError(_("TLS enabled but server does not support " \
                        "TLS"))
            smtp.starttls()
            smtp.ehlo()
        if self.user:
            smtp.login(
                self.user.encode('utf-8'),
                self.password.encode('utf-8')
            )
        smtp.sendmail(from_addr, recipients, message)
        if self.use_tls or self.use_ssl:
            # avoid false failure detection when the server closes
            # the SMTP connection with TLS/SSL enabled
            import socket
            try:
                smtp.quit()
            except socket.sslerror:
                pass
        else:
            smtp.quit()


class SendmailEmailSender(Component):
    """E-mail sender using a locally-installed sendmail program."""

    implements(IEmailSender)

    sendmail_path = Option('sendmail', 'sendmail_path', 'sendmail',
        """Path to the sendmail executable.

        The sendmail program must accept the `-i` and `-f` options.
        """)

    def send(self, from_addr, recipients, message):
        self.log.info("Sending notification through sendmail at %s to %s"
                      % (self.sendmail_path, recipients))
        cmdline = [self.sendmail_path, "-i", "-f", from_addr]
        cmdline.extend(recipients)
        self.log.debug("Sendmail command line: %s" % ' '.join(cmdline))
        try:
            child = Popen(cmdline, bufsize=-1, stdin=PIPE, stdout=PIPE,
                          stderr=PIPE)
            (out, err) = child.communicate(message)
            if child.returncode or err:
                raise Exception("Sendmail failed with (%s, %s), command: '%s'"
                                % (child.returncode, err.strip(), cmdline))
        except OSError, e:
            self.log.error("Failed to run sendmail[%s] with error %s"%\
                    (self.sendmail_path, e))


class DeliveryThread(threading.Thread):
    def __init__(self, queue, sender):
        threading.Thread.__init__(self)
        self._sender = sender
        self._queue = queue
        self.setDaemon(True)

    def run(self):
        while 1:
            sendfrom, recipients, message = self._queue.get()
            self._sender(sendfrom, recipients, message)

