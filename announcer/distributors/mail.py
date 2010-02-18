# -*- coding: utf-8 -*-
#
# Copyright (c) 2008, Stephen Hansen
# Copyright (c) 2009, Robert Corsaro
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
import Queue
import random
import re
import smtplib
import sys
import threading
import time

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import formatdate, formataddr
from email.Charset import Charset, QP, BASE64
try:
    from email.header import Header
except:
    from email.Header import Header

from trac.core import *
from trac.util.compat import set, sorted
from trac.config import Option, BoolOption, IntOption, OrderedExtensionsOption
from trac.util import get_pkginfo, md5
from trac.util.datefmt import to_timestamp
from trac.util.text import to_unicode, CRLF
from trac.util.translation import _

from announcer.api import AnnouncementSystem
from announcer.api import IAnnouncementAddressResolver
from announcer.api import IAnnouncementDistributor
from announcer.api import IAnnouncementFormatter
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import IAnnouncementProducer
from announcer.util.mail import set_header

class IAnnouncementEmailDecorator(Interface):
    def decorate_message(event, message, decorators):
        """
        Manipulate the message before it is sent on it's way.  The callee
        should call the next decorator by by popping decorators and calling
        the popped decorator.  If decorators is empty, don't worry about it.
        """

class EmailDistributor(Component):
    
    implements(IAnnouncementDistributor, IAnnouncementPreferenceProvider)

    formatters = ExtensionPoint(IAnnouncementFormatter)
    producers = ExtensionPoint(IAnnouncementProducer)
    distributors = ExtensionPoint(IAnnouncementDistributor)
    # Make ordered
    decorators = ExtensionPoint(IAnnouncementEmailDecorator)
    resolvers = OrderedExtensionsOption('announcer', 'email_address_resolvers',
        IAnnouncementAddressResolver, 'SpecifiedEmailResolver, '\
        'SessionEmailResolver, DefaultDomainEmailResolver', 
        doc="""Comma seperated list of email resolver components in the order 
        they will be called.  If an email address is resolved, the remaining 
        resolvers will no be called.""")

    smtp_enabled = BoolOption('announcer', 'smtp_enabled', 'false',
        """Enable SMTP (email) notification.""")

    smtp_server = Option('announcer', 'smtp_server', 'localhost',
        """SMTP server hostname to use for email notifications.""")

    smtp_port = IntOption('announcer', 'smtp_port', 25,
        """SMTP server port to use for email notification.""")

    smtp_timeout = IntOption('announcer', 'smtp_timeout', 10,
        """SMTP server connection timeout.""")

    smtp_user = Option('announcer', 'smtp_user', '',
        """Username for SMTP server. (''since 0.9'').""")

    smtp_password = Option('announcer', 'smtp_password', '',
        """Password for SMTP server. (''since 0.9'').""")

    smtp_from = Option('announcer', 'smtp_from', 'trac@localhost',
        """Sender address to use in notification emails.""")

    smtp_debuglevel = IntOption('announcer', 'smtp_debuglevel', 0,
        doc="""Set to 1 for useful smtp debugging on stdout.""")
        
    smtp_ssl = BoolOption('announcer', 'smtp_ssl', 'false',
        doc="""Use ssl for smtp connection.""")
        
    smtp_from_name = Option('announcer', 'smtp_from_name', '',
        """Sender name to use in notification emails.""")

    smtp_replyto = Option('announcer', 'smtp_replyto', 'trac@localhost',
        """Reply-To address to use in notification emails.""")

    smtp_always_cc = Option('announcer', 'smtp_always_cc', '',
        """Email address(es) to always send notifications to,
           addresses can be see by all recipients (Cc:).""")

    smtp_always_bcc = Option('announcer', 'smtp_always_bcc', '',
        """Email address(es) to always send notifications to,
           addresses do not appear publicly (Bcc:). (''since 0.10'').""")
                   
    ignore_domains = Option('announcer', 'ignore_domains', '',
        """Comma-separated list of domains that should not be considered
           part of email addresses (for usernames with Kerberos domains)""")
           
    admit_domains = Option('announcer', 'admit_domains', '',
        """Comma-separated list of domains that should be considered as
        valid for email addresses (such as localdomain)""")
           
    mime_encoding = Option('announcer', 'mime_encoding', 'base64',
        """Specifies the MIME encoding scheme for emails.
        
        Valid options are 'base64' for Base64 encoding, 'qp' for
        Quoted-Printable, and 'none' for no encoding. Note that the no encoding
        means that non-ASCII characters in text are going to cause problems
        with notifications (''since 0.10'').""")

    use_public_cc = BoolOption('announcer', 'use_public_cc', 'false',
        """Recipients can see email addresses of other CC'ed recipients.
        
        If this option is disabled (the default), recipients are put on BCC
        (''since 0.10'').""")

    use_short_addr = BoolOption('announcer', 'use_short_addr', 'false',
        """Permit email address without a host/domain (i.e. username only)
        
        The SMTP server should accept those addresses, and either append
        a FQDN or use local delivery (''since 0.10'').""")
        
    use_tls = BoolOption('announcer', 'use_tls', 'false',
        """Use SSL/TLS to send notifications (''since 0.10'').""")
    
    smtp_subject_prefix = Option('announcer', 'smtp_subject_prefix',
                                 '__default__', 
        """Text to prepend to subject line of notification emails. 
        
        If the setting is not defined, then the [$project_name] prefix.
        If no prefix is desired, then specifying an empty option 
        will disable it.(''since 0.10.1'').""")

    smtp_to = Option('announcer', 'smtp_to', None, 'Default To: field')
    
    use_threaded_delivery = BoolOption('announcer', 'use_threaded_delivery', 
            'false', """If true, the actual delivery of the message will occur 
            in a separate thread.  Enabling this will improve responsiveness 
            for requests that end up with an announcement being sent over 
            email. It requires building Python with threading support 
            enabled-- which is usually the case. To test, start Python and 
            type 'import threading' to see if it raises an error.""")
    
    default_email_format = Option('announcer', 'default_email_format', 
            'text/plain',
            doc="""The default mime type of the email notifications.  This
            can be overriden on a per user basis through the announcer
            preferences panel.""")

    def __init__(self):
        self.delivery_queue = None
        self._init_pref_encoding()

    def get_delivery_queue(self):
        if not self.delivery_queue:
            self.delivery_queue = Queue.Queue()
            thread = DeliveryThread(self.delivery_queue, self._transmit)
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
        if not self.smtp_enabled or not found:
            self.log.debug("EmailDistributer smtp_enabled set to false")
            return
        fmtdict = self.formats(transport, event.realm)
        if not fmtdict:
            self.log.error(
                "EmailDistributer No formats found for %s %s"%(
                    transport, event.realm))
            return
        msgdict = {}
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
                msgdict.setdefault(fmt, set()).add((name, authed, addr))
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
                    
    def _get_default_format(self):
        return self.default_email_format
        
    def _get_preferred_format(self, realm, sid, authenticated):
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
        host = self.smtp_from[self.smtp_from.find('@') + 1:]
        msgid = '<%03d.%s@%s>' % (len(s), dig, host)
        return msgid

    def _do_send(self, transport, event, format, recipients, formatter):
        output = formatter.format(transport, event.realm, format, event)
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

        headers = dict()
        headers['Message-ID'] = self._message_id(event.realm)
        headers['Date'] = formatdate()
        from_header = formataddr((
            self.smtp_from_name or self.env.project_name,
            self.smtp_from
        ))
        headers['From'] = from_header
        if self.smtp_always_bcc:
            headers['Bcc'] = self.smtp_always_bcc
        if self.smtp_to:
            headers['To'] = '"%s"'%(self.smtp_to)
        if self.use_public_cc:
            headers['Cc'] = ', '.join([x[2] for x in recipients if x])
        headers['Reply-To'] = self.smtp_replyto
        for k, v in headers.iteritems():
            set_header(rootMessage, k, v)

        rootMessage.preamble = 'This is a multi-part message in MIME format.'
        if alternate_output:
            parentMessage = MIMEMultipart('alternative')
            rootMessage.attach(parentMessage)
        else:
            parentMessage = rootMessage
        if alternate_output:
            alt_msg_format = 'html' in alternate_style and 'html' or 'plain'
            msgText = MIMEText(alternate_output, alt_msg_format)
            parentMessage.attach(msgText)
        msg_format = 'html' in format and 'html' or 'plain'
        msgText = MIMEText(output, msg_format)
        del msgText['Content-Transfer-Encoding']
        msgText.set_charset(self._charset)
        parentMessage.attach(msgText)
        decorators = self._get_decorators()
        if len(decorators) > 0:
            decorator = decorators.pop()
            decorator.decorate_message(event, rootMessage, decorators)
        package = (from_header, [x[2] for x in recipients if x], 
                rootMessage.as_string())
        start = time.time()
        if self.use_threaded_delivery:
            self.get_delivery_queue().put(package)
        else:
            self._transmit(*package)
        stop = time.time()
        self.log.debug("EmailDistributor took %s seconds to send."\
                %(round(stop-start,2)))

    def _get_decorators(self):
        return self.decorators[:]

    def _transmit(self, smtpfrom, addresses, message):
        # Ensure the message complies with RFC2822: use CRLF line endings
        message = CRLF.join(re.split("\r?\n", message))

        # use defaults to make sure connect() is called in the constructor
        smtpclass = smtplib.SMTP
        if self.smtp_ssl:
            smtpclass = smtplib.SMTP_SSL
        smtp = smtpclass(
            host=self.smtp_server,
            port=self.smtp_port,
            timeout=self.smtp_timeout
        )
        if self.smtp_debuglevel:
            smtp.set_debuglevel(self.smtp_debuglevel)
        if self.use_tls:
            smtp.ehlo()
            if not smtp.esmtp_features.has_key('starttls'):
                raise TracError(_("TLS enabled but server does not support " \
                        "TLS"))
            smtp.starttls()
            smtp.ehlo()
        if self.smtp_user:
            smtp.login(self.smtp_user, self.smtp_password)
        smtp.sendmail(smtpfrom, addresses, message)
        smtp.quit()
        
    # IAnnouncementDistributor
    def get_announcement_preference_boxes(self, req):
        yield "email", "E-Mail Format"
        
    def render_announcement_preference_box(self, req, panel):
        supported_realms = {}
        for producer in self.producers:
            for realm in producer.realms():
                for distributor in self.distributors:
                    for transport in distributor.transports():
                        for fmtr in self.formatters:
                            for style in fmtr.styles(transport, realm):
                                if realm not in supported_realms:
                                    supported_realms[realm] = set()
                                supported_realms[realm].add(style)
            
        if req.method == "POST":
            for realm in supported_realms:
                opt = req.args.get('email_format_%s'%realm, False)
                if opt:
                    req.session['announcer_email_format_%s'%realm] = opt
        prefs = {}
        for realm in supported_realms:
            prefs[realm] = req.session.get('announcer_email_format_%s'%realm, None)
        data = dict(
            realms = supported_realms,
            preferences = prefs,
        )
        return "prefs_announcer_email.html", data    

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

