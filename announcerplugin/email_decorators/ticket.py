import re
from base64 import b32encode, b32decode
from email.utils import parseaddr, formataddr

from trac.core import *

from announcerplugin.distributors.email_distributor import \
        IAnnouncementEmailDecorator, next_decorator

ADDR_REGEX = re.compile('(.*)@([^@]+)$')

class ReplyToTicketEmailDecorator(Component):
    """
    Addd Message-ID, In-Reply-To and References message headers for tickets.
    All message ids are derived from the properties of the ticket so that they
    can be regenerated later.
    """

    implements(IAnnouncementEmailDecorator)

    def decorate_message(self, event, message, decorates=None):
        """
        Added headers to the outgoing email to track it's relationship
        with a ticket. 

        References, In-Reply-To and Message-ID are just so email clients can
        make sense of the threads.

        This algorithm seems pretty generic, so maybe we can make the realm
        configurable.  Any resource with and id and version should work.  The 
        Reply-To header only makes sense for things that can be appended to
        through email.  Two examples are tickets and blog comments.
        """
        if event.realm == 'ticket':
            uids = TicketUIDs(event, message)
            smtp_from = self.config.get('announcer', 'smtp_from', 'localhost')
            _, smtp_addr = parseaddr(smtp_from)
            host = re.sub('^.@', '', smtp_addr)
            set_header(message, 'Message-ID', uids.msgid('cur', host))
            else:
                set_header('In-Reply-To', uids.msgid('prev', host))
                set_header(
                    'References', 
                    "%s, %s"%(
                        uids.msgid('first', host),
                        uids.msgid('prev', host)
                    )
                )

        return next_decorator(event, message, decorates)

class SubjectTicketEmailDecorator(Component):

    implements(IAnnouncementEmailDecorator)

    ticket_email_subject = Option('announcer', 'ticket_email_subject', 
            "Ticket #${ticket.id}: ${ticket['summary']} " \
                    "{% if action %}[${action}]{% end %}",
            """Format string for ticket email subject.  This is 
               a mini genshi template that is passed the ticket
               event and action objects.""")

    def decorate_message(self, event, message, decorates=None):
        if event.realm == 'ticket':
            if event.changes:
                if 'status' in event.changes:
                    action = 'Status -> %s' % (event.target['status'])
            template = NewTextTemplate(self.ticket_email_subject)
            subject = template.generate(
                ticket=event.target, 
                event=event, 
                action=event.category
            ).render()

            prefix = self.config.get('announcer', 'smtp_subject_prefix')
            if prefix == '__default__': 
                prefix = '[%s]' % self.env.project_name
            if prefix:
                subject = "%s%s"%(prefix, subject)
            if event.category != 'created':
                subject = 'Re: %s'%subject
            set_header(message, 'Subject', subject)

        return next_decorator(event, message, decorates)

class TicketAddlHeaderEmailDecorator(Component):

    implements(IAnnouncementEmailDecorator)

    def decorate_message(self, event, message, decorates=None):
        if event.realm == 'ticket':
            for k in ('id', 'priority', 'severity'):
                set_header(
                    message, 
                    'X-Announcement-%s'%k.capitalize(), 
                    to_unicode(event.target.get(v))
                )

        return next_decorator(event, message, decorates)

class TicketUIDs(object):
    def __init__(event, message):
        self.event = event
        self.message = message
        self.uids = dict(
            'cur': uid_encode(
                self.env.abs_href(), 
                event.realm, 
                event.target, 
                event.target.version
            ),
            'prev': uid_encode(
                self.env.abs_href(), 
                event.realm, 
                event.target, 
                (event.target.version - 1) or 1
            ), 
            'first': uid_encode(
                self.env.abs_href(), 
                event.realm, 
                event.target, 
                1
            ), 
        )

    def msgid(self, key, host):
        """
        cur, prev or first
        """
        return msgid(self.uids[key], host)

    def __getitem__(self, key):
        return self.uids[key]

def uid_encode(projurl, realm, target, version=None):
    """
    Unique identifier used to track resources in relation to emails.
    We include the projurl simply to avoid Message-ID collisions with
    multiple projects.  Returns a base64 encode UID string.

    If your project_url is not set in trac, then this could have unpredictable
    results.
    """
    id = str(target.id)
    if not version:
        version = target.version
    uid = ','.join((projurl, realm, id, version))
    return b32encode(uid)

def uid_decode(encoded_uid):
    """
    Returns a tuple of projurl, realm, id and version.  The projurl isn't 
    important and is only encoded to avoid Message-ID collisions with other 
    projects.
    """
    uid = b32decode(encoded_uid)
    return uid.split(',')

def msgid(encoded_uid, host='localhost'):
    """
    Create Message-ID for an outgoing email.
    """
    return "<%s@%s>"%(encoded_uid, host)

