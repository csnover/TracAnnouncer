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

from trac.attachment import IAttachmentChangeListener
from trac.config import BoolOption
from trac.core import *
from trac.ticket.api import ITicketChangeListener
from trac.ticket.model import Ticket
from trac.wiki.api import IWikiChangeListener
from trac.wiki.model import WikiPage

from announcer.api import AnnouncementSystem, AnnouncementEvent, IAnnouncementProducer
from announcer.producers.ticket import TicketChangeEvent
from announcer.producers.wiki import WikiChangeEvent

class AttachmentChangeProducer(Component):
    implements(IAttachmentChangeListener, IAnnouncementProducer)

    def __init__(self, *args, **kwargs):
        pass

    def realms(self):
        yield 'ticket'
        yield 'wiki'

    def attachment_added(self, attachment):
        parent = attachment.resource.parent
        if parent.realm == "ticket":
            ticket = Ticket(self.env, parent.id)
            announcer = AnnouncementSystem(ticket.env)
            announcer.send(
                TicketChangeEvent("ticket", "attachment added", ticket,
                    attachment=attachment, author=attachment.author,
                )
            )
        elif parent.realm == "wiki":
            page = WikiPage(self.env, parent.id)
            announcer = AnnouncementSystem(page.env)
            announcer.send(
                WikiChangeEvent("wiki", "attachment added", page,
                    attachment=attachment, author=attachment.author,
                )
            )

    def attachment_deleted(self, attachment):
        pass

class TicketChangeEvent(AnnouncementEvent):
    def __init__(self, realm, category, target,
                 comment=None, author=None, changes={},
                 attachment=None):
        AnnouncementEvent.__init__(self, realm, category, target)
        self.author = author
        self.comment = comment
        self.changes = changes
        self.attachment = attachment

    def get_basic_terms(self):
        for term in AnnouncementEvent.get_basic_terms(self):
            yield term
        ticket = self.target
        yield ticket['component']

    def get_session_terms(self, session_id):
        ticket = self.target
        if session_id == self.author:
            yield "updater"
        if session_id == ticket['owner']:
            yield "owner"
        if session_id == ticket['reporter']:
            yield "reporter"

class TicketChangeProducer(Component):
    implements(ITicketChangeListener, IAnnouncementProducer)

    ignore_cc_changes = BoolOption('announcer', 'ignore_cc_changes', 'false',
        doc="""When true, the system will not send out announcement events if
        the only field that was changed was CC. A change to the CC field that
        happens at the same as another field will still result in an event
        being created.""")

    def __init__(self, *args, **kwargs):
        pass

    def realms(self):
        yield 'ticket'

    def ticket_created(self, ticket):
        announcer = AnnouncementSystem(ticket.env)
        announcer.send(
            TicketChangeEvent("ticket", "created", ticket,
                author=ticket['reporter']
            )
        )

    def ticket_changed(self, ticket, comment, author, old_values):
        if old_values.keys() == ['cc'] and not comment and \
                self.ignore_cc_changes:
            return
        announcer = AnnouncementSystem(ticket.env)
        announcer.send(
            TicketChangeEvent("ticket", "changed", ticket,
                comment, author, old_values
            )
        )

    def ticket_deleted(self, ticket):
        pass

class WikiChangeEvent(AnnouncementEvent):
    def __init__(self, realm, category, target,
                 comment=None, author=None, version=None,
                 timestamp=None, remote_addr=None,
                 attachment=None):
        AnnouncementEvent.__init__(self, realm, category, target)
        self.author = author
        self.comment = comment
        self.version = version
        self.timestamp = timestamp
        self.remote_addr = remote_addr
        self.attachment = attachment

class WikiChangeProducer(Component):
    implements(IWikiChangeListener, IAnnouncementProducer)

    def realms(self):
        yield 'wiki'

    def wiki_page_added(self, page):
        history = list(page.get_history())[0]
        announcer = AnnouncementSystem(page.env)
        announcer.send(
            WikiChangeEvent("wiki", "created", page,
                author=history[2], version=history[0]
            )
        )

    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        announcer = AnnouncementSystem(page.env)
        announcer.send(
            WikiChangeEvent("wiki", "changed", page,
                comment=comment, author=author, version=version,
                timestamp=t, remote_addr=ipnr
            )
        )

    def wiki_page_deleted(self, page):
        announcer = AnnouncementSystem(page.env)
        announcer.send(
            WikiChangeEvent("wiki", "deleted", page)
        )

    def wiki_page_version_deleted(self, page):
        announcer = AnnouncementSystem(page.env)
        announcer.send(
            WikiChangeEvent("wiki", "version deleted", page)
        )
