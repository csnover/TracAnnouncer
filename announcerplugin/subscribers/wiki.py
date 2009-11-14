from trac.core import Component, implements
from announcerplugin.api import IAnnouncementPreferenceProvider
from announcerplugin.api import IAnnouncementSubscriber, istrue
from trac.ticket import model
from trac.web.chrome import add_warning
from trac.config import ListOption
import re, urllib

class GeneralWikiSubscriber(Component):
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
        
    def get_subscription_realms(self):
        return ('wiki',)
        
    def get_subscription_categories(self, realm):
        if realm == "wiki":
            return ('changed', 'created', 'attachment added', 'deleted', 
                    'version deleted')
        else:
            return tuple()
            
    def get_subscriptions_for_event(self, event):
        if event.realm == 'wiki':
            if event.category in self.get_subscription_categories(event.realm):
                page = event.target
                for name, authenticated in self._get_membership(page.name):
                    yield ('email', name, authenticated, None)
        
    def _get_membership(self, name):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid, authenticated, value
              FROM session_attribute
             WHERE name=%s
        """, ('announcer_wiki_interests', ))
        for sid, authenticated, value in cursor.fetchall():
            for raw in value.split(' '):
                pat = urllib.unquote(raw).replace('*', '.*')
                if re.match(pat, name):
                    self.log.debug(
                        "GeneralWikiSubscriber added '%s (%s)' because name "\
                        "'%s' matches pattern: %s"%(sid, authenticated and \
                        'authenticated' or 'not authenticated', name, pat))
                    yield sid, authenticated
                    
    def get_announcement_preference_boxes(self, req):
        yield "general_wiki", "General Wiki Announcements"
        
    def render_announcement_preference_box(self, req, panel):
        sess = req.session
        if req.method == "POST":
            results = req.args.get('wiki_interests', '')
            if results:
                options = results.splitlines()
                sess['announcer_wiki_interests'] = ' '.join(
                    urllib.quote(x) for x in options
                )
        if 'announcer_wiki_interests' in sess:
            interests = sess['announcer_wiki_interests']
        else:
            interests = ''
        return "prefs_announcer_wiki.html", dict(
            wiki_interests = '\n'.join(
                urllib.unquote(x) for x in interests.split(' ')
            )
        )

