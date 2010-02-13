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

from trac.core import *
from trac.attachment import IAttachmentChangeListener
from announcer.api import AnnouncementSystem, IAnnouncementProducer
from announcer.producers.ticket import TicketChangeEvent
from announcer.producers.wiki import WikiChangeEvent
from trac.ticket.model import Ticket
from trac.wiki.model import WikiPage

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
