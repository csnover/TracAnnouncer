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

import announcer
import re
import trac

from email.utils import parseaddr

from trac.config import ListOption, Option
from trac.core import *
from trac.util.text import to_unicode

from genshi.template import NewTextTemplate

from announcer.distributors.mail import IAnnouncementEmailDecorator
from announcer.util.mail import set_header, msgid, next_decorator, uid_encode

"""Email decorators have the chance to modify emails or their headers before
the email distributor sends them out.
"""

class ThreadingEmailDecorator(Component):
    """Add Message-ID, In-Reply-To and References message headers for resources.
    All message ids are derived from the properties of the ticket so that they
    can be regenerated later.
    """

    implements(IAnnouncementEmailDecorator)

    supported_realms = ListOption('announcer', 'email_threaded_realms',
        'ticket,wiki',
        doc="""These are realms with announcements that should be threaded
        emails.  In order for email threads to work, the announcer
        system needs to give the email recreatable Message-IDs based
        on the resources in the realm.  The resources must have a unique
        and immutable id, name or str() representation in it's realm
        """)

    def decorate_message(self, event, message, decorates=None):
        """
        Added headers to the outgoing email to track it's relationship
        with a ticket.

        References, In-Reply-To and Message-ID are just so email clients can
        make sense of the threads.
        """
        if to_unicode(event.realm) in self.supported_realms:
            uid = uid_encode(self.env.abs_href(), event.realm, event.target)
            email_from = self.config.get('announcer', 'email_from', 'localhost')
            _, email_addr = parseaddr(email_from)
            host = re.sub('^.+@', '', email_addr)
            mymsgid = msgid(uid, host)
            if event.category == 'created':
                set_header(message, 'Message-ID', mymsgid)
            else:
                set_header(message, 'In-Reply-To', mymsgid)
                set_header(message, 'References', mymsgid)

        return next_decorator(event, message, decorates)


class StaticEmailDecorator(Component):
    """The static ticket decorator implements a policy to -always- send an
    email to a certain address.

    Controlled via the always_cc and always_bcc option in the announcer section
    of the trac.ini.  If no subscribers are found, then even if always_cc and
    always_bcc addresses are specified, no announcement will be sent.  Since
    these fields are added after announcers subscription system, filters such
    as never_announce and never_notify author won't work with these addresses.

    These settings are considered dangerous if you are using the verify email
    or reset password features of the accountmanager plugin.
    """

    implements(IAnnouncementEmailDecorator)

    always_cc = Option("announcer", "email_always_cc", None,
        """Email addresses specified here will always
        be cc'd on all announcements.  This setting is dangerous if
        accountmanager is present.
        """)

    always_bcc = Option("announcer", "email_always_bcc", None,
        """Email addresses specified here will always
        be bcc'd on all announcements.  This setting is dangerous if
        accountmanager is present.
        """)

    def decorate_message(self, event, message, decorates=None):
        for k, v in {'Cc': self.always_cc, 'Bcc': self.always_bcc}.items():
            if v:
                self.log.debug("StaticEmailDecorator added '%s' "
                        "because of rule: email_always_%s"%(v, k.lower())),
                if message[k] and len(str(message[k]).split(',')) > 0:
                    recips = ", ".join(str(message[k]), v)
                else:
                    recips = v
                set_header(message, k, recips)
        return next_decorator(event, message, decorates)


class AnnouncerEmailDecorator(Component):
    """Add some boring headers that should be set."""

    implements(IAnnouncementEmailDecorator)

    def decorate_message(self, event, message, decorators):
        mailer = 'AnnouncerPlugin v%s on Trac v%s'%(
            announcer.__version__,
            trac.__version__
        )
        set_header(message, 'Auto-Submitted', 'auto-generated')
        set_header(message, 'Precedence', 'bulk')
        set_header(message, 'X-Announcer-Version', announcer.__version__)
        set_header(message, 'X-Mailer', mailer)
        set_header(message, 'X-Trac-Announcement-Realm', event.realm)
        set_header(message, 'X-Trac-Project', self.env.project_name)
        set_header(message, 'X-Trac-Version', trac.__version__)

        return next_decorator(event, message, decorators)


class TicketSubjectEmailDecorator(Component):
    """Formats ticket announcement subject headers based on the
    ticket_email_subject configuration.
    """

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
            template = NewTextTemplate(self.ticket_email_subject.encode('utf8'))
            subject = template.generate(
                ticket=event.target,
                event=event,
                action=event.category
            ).render('text', encoding=None)

            prefix = self.config.get('announcer', 'email_subject_prefix')
            if prefix == '__default__':
                prefix = '[%s] ' % self.env.project_name
            if prefix:
                subject = "%s%s"%(prefix, subject)
            if event.category != 'created':
                subject = 'Re: %s'%subject
            set_header(message, 'Subject', subject)

        return next_decorator(event, message, decorates)


class TicketAddlHeaderEmailDecorator(Component):
    """Adds X-Announcement-(id,priority and severity) headers to ticket
    emails.  This is useful for automated handling of incoming emails or
    customized filtering.
    """

    implements(IAnnouncementEmailDecorator)

    def decorate_message(self, event, message, decorates=None):
        if event.realm == 'ticket':
            for k in ('id', 'priority', 'severity'):
                name = 'X-Announcement-%s'%k.capitalize()
                set_header(message, name, event.target[k])

        return next_decorator(event, message, decorates)


class WikiSubjectEmailDecorator(Component):
    """Formats wiki announcement subject headers based on the
    wiki_email_subject configuration.
    """

    implements(IAnnouncementEmailDecorator)

    wiki_email_subject = Option('announcer', 'wiki_email_subject',
            "Page: ${page.name} ${action}",
            """Format string for the wiki email subject.  This is a
               mini genshi template and it is passed the page, event
               and action objects.""")

    def decorate_message(self, event, message, decorates=None):
        if event.realm == 'wiki':
            template = NewTextTemplate(self.wiki_email_subject.encode('utf8'))
            subject = template.generate(
                page=event.target,
                event=event,
                action=event.category
            ).render('text', encoding=None)

            prefix = self.config.get('announcer', 'email_subject_prefix')
            if prefix == '__default__':
                prefix = '[%s] ' % self.env.project_name
            if prefix:
                subject = "%s%s"%(prefix, subject)
            if event.category != 'created':
                subject = 'Re: %s'%subject
            set_header(message, 'Subject', subject)

        return next_decorator(event, message, decorates)
