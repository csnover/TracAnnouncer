from trac.core import *
from trac.attachment import IAttachmentChangeListener
from announcerplugin.api import AnnouncementSystem
from announcerplugin.producers.ticket import TicketChangeEvent
from announcerplugin.producers.wiki import WikiChangeEvent
from trac.ticket.model import Ticket
from trac.wiki.model import WikiPage

class AttachmentChangeProducer(Component):
    implements(IAttachmentChangeListener)
    
    def __init__(self, *args, **kwargs):
        pass

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
