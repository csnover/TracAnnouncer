from trac.core import *
from trac.config import BoolOption
from trac.wiki.api import IWikiChangeListener
from announcerplugin.api import AnnouncementSystem, AnnouncementEvent

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
    implements(IWikiChangeListener)
    
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
        
