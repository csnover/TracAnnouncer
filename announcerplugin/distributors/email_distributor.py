from trac.core import Component, implements, ExtensionPoint
from trac.util.compat import set, sorted
from trac.config import Option, BoolOption, IntOption, OrderedExtensionsOption
from trac.util import get_pkginfo
from trac.util.text import to_unicode
from trac.util.translation import _

from announcerplugin.api import IAnnouncementDistributor
from announcerplugin.api import IAnnouncementFormatter
from announcerplugin.api import IAnnouncementPreferenceProvider
from announcerplugin.api import IAnnouncementAddressResolver
from announcerplugin.api import AnnouncementSystem
import announcerplugin, trac

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import formatdate
try:
    from email.header import Header
except:
    from email.Header import Header
import time, Queue, threading, smtplib

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
            
class EmailDistributor(Component):
    
    implements(IAnnouncementDistributor, IAnnouncementPreferenceProvider)

    formatters = ExtensionPoint(IAnnouncementFormatter)
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

    smtp_user = Option('announcer', 'smtp_user', '',
        """Username for SMTP server. (''since 0.9'').""")

    smtp_password = Option('announcer', 'smtp_password', '',
        """Password for SMTP server. (''since 0.9'').""")

    smtp_from = Option('announcer', 'smtp_from', 'trac@localhost',
        """Sender address to use in notification emails.""")
        
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
    def get_distribution_transport(self):
        return "email"

    def formats(self, transport, realm):
        "Find valid formats for transport and realm"
        formats = {}
        for f in self.formatters:
            if f.get_format_transport() == transport:
                if realm in f.get_format_realms(transport):
                    styles = f.get_format_styles(transport, realm)
                    for style in styles:
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
        if not self.smtp_enabled or transport != self.get_distribution_transport():
            return
        fmtdict = self.formats(transport, event.realm)
        if not fmtdict:
            return
        msgdict = {}
        for name, authed, addr in recipients:
            fmt = name and \
                self._get_preferred_format(event.realm, name, authed) or \
                self._get_default_format()
                
            if name and not addr:
                for rslvr in self.resolvers:
                    addr = rslvr.get_address_for_name(name, authed)
                    if addr:
                        self.log.debug("EmailDistributor found the " \
                                "address '%s' for '%s (%s)' via: %s"%(
                                addr, name, authed and \
                                'authenticated' or 'not authenticated', 
                                rslvr.__class__.__name__))
                        break
            if addr:
                msgdict.setdefault(fmt, set()).add((name, authed, addr))
            else:
                self.log.debug("EmailDistributor was unable to find an " \
                        "address for: %s (%s)"%(name, authed and \
                        'authenticated' or 'not authenticated'))
        for msgset, fmtr, fmt in [
                (msgdict[f], fmtdict[f], f) for f in msgdict.keys()
                ]:
            if not msgset:
                continue
            self.log.debug(
                "EmailDistributor is sending event as '%s' to: %s"%(
                    fmt, ', '.join(x[2] for x in msgset)))
            self._do_send(transport, event, fmt, msgset, fmtr)
                    
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
        from email.Charset import Charset, QP, BASE64
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

    def _do_send(self, transport, event, format, recipients, formatter):
        output = formatter.format(transport, event.realm, format, event)
        subject = formatter.format_subject(transport, event.realm, format, 
                event)
        alternate_format = formatter.get_format_alternative(transport, 
                event.realm, format)
        if alternate_format:
            alternate_output = formatter.format(transport, event.realm, 
                    alternate_format, event)
        else:
            alternate_output = None
        rootMessage = MIMEMultipart("related")
        proj_name = self.env.project_name
        trac_version = get_pkginfo(trac.core).get('version', trac.__version__)
        announcer_version = get_pkginfo(announcerplugin).get('version', 
                'Undefined')
        rootMessage['X-Mailer'] = 'AnnouncerPlugin v%s on Trac ' \
                'v%s'%(announcer_version, trac_version)
        rootMessage['X-Trac-Version'] = trac_version
        rootMessage['X-Announcer-Version'] = announcer_version
        rootMessage['X-Trac-Project'] = proj_name
        rootMessage['Precedence'] = 'bulk'
        rootMessage['Auto-Submitted'] = 'auto-generated'
        provided_headers = formatter.format_headers(transport, event.realm, 
                format, event)
        for key in provided_headers:
            rootMessage['X-Announcement-%s'%key.capitalize()] = \
                    to_unicode(provided_headers[key])
        rootMessage['Date'] = formatdate()
        # sanity check
        if not self._charset.body_encoding:
            try:
                dummy = body.encode('ascii')
            except UnicodeDecodeError:
                raise TracError(_("Ticket contains non-ASCII chars. " \
                                  "Please change encoding setting"))

        rootMessage['Subject'] = Header(subject, self._charset) 
        from_header = '"%s" <%s>'%(
            Header(self.smtp_from_name or proj_name, self._charset),
            self.smtp_from
        )
        rootMessage['From'] = from_header
        if self.smtp_always_bcc:
            rootMessage['Bcc'] = self.smtp_always_bcc
        if self.smtp_to:
            rootMessage['To'] = '"%s"'%(self.smtp_to)
        if self.use_public_cc:
            rootMessage['Cc'] = ', '.join([x[2] for x in recipients if x])
        rootMessage['Reply-To'] = self.smtp_replyto
        rootMessage.preamble = 'This is a multi-part message in MIME format.'
        if alternate_output:
            parentMessage = MIMEMultipart('alternative')
            rootMessage.attach(parentMessage)
        else:
            parentMessage = rootMessage
        if alternate_output:
            alt_msg_format = 'html' in alternate_format and 'html' or 'plain'
            msgText = MIMEText(alternate_output, alt_msg_format)
            parentMessage.attach(msgText)
        msg_format = 'html' in format and 'html' or 'plain'
        msgText = MIMEText(output, msg_format)
        del msgText['Content-Transfer-Encoding']
        msgText.set_charset(self._charset)
        parentMessage.attach(msgText)
        start = time.time()
        package = (from_header, [x[2] for x in recipients if x], 
                rootMessage.as_string())
        if self.use_threaded_delivery:
            self.get_delivery_queue().put(package)
        else:
            self._transmit(*package)
        stop = time.time()
        self.log.debug("EmailDistributor took %s seconds to send."\
                %(round(stop-start,2)))

    def _transmit(self, smtpfrom, addresses, message):
        # use defaults to make sure connect() is called in the constructor
        smtp = smtplib.SMTP(
            self.smtp_server or 'localhost', 
            self.smtp_port or 25
        )
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
        transport = self.get_distribution_transport()
        supported_realms = {}
        for formatter in self.formatters:
            if formatter.get_format_transport() == transport:
                for realm in formatter.get_format_realms(transport):
                    if realm not in supported_realms:
                        supported_realms[realm] = set()
                    supported_realms[realm].update(
                       formatter.get_format_styles(transport, realm)
                    )
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

