# -*- coding: utf-8 -*-
#
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
from trac.core import * 
from trac.config import Option 
from trac.util.text import to_unicode
from genshi.template import NewTextTemplate

from announcer.distributors.mail import IAnnouncementEmailDecorator 
from announcer.util.mail import next_decorator, set_header
 
class TicketSubjectEmailDecorator(Component):

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

    implements(IAnnouncementEmailDecorator)

    def decorate_message(self, event, message, decorates=None):
        if event.realm == 'ticket':
            for k in ('id', 'priority', 'severity'):
                name = 'X-Announcement-%s'%k.capitalize()
                set_header(message, name, event.target[k])

        return next_decorator(event, message, decorates)

