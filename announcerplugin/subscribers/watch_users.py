from trac.core import Component, implements
from announcerplugin.api import IAnnouncementSubscriber, istrue
from announcerplugin.api import IAnnouncementPreferenceProvider
from trac.ticket import model
from trac.web.chrome import add_warning
from trac.config import ListOption
import re

class UserChangeSubscriber(Component):
    """Allows users to get notified anytime a particular user change or 
    modifies a ticket or wiki page."""
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)

    def get_subscription_realms(self):
        return ('wiki', 'ticket')
    
    def get_subscription_categories(self, realm):
        return('changed', 'created', 'attachment added')
    
    def get_subscriptions_for_event(self, event):
        if event.category in ('changed', 'created', 'attachment added'):
            for sub in self._get_membership(event.author):
                yield sub

    def _get_membership(self, author):
        """Check the user's selection.  None means 
        they haven't selected ."""
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid, authenticated, value
              FROM session_attribute
             WHERE name='announcer_watch_users'
        """)
        for result in cursor.fetchall():
            for name in result[2].split(','):
                if name.strip() == author:
                    name, authenticated = result[0], result[1]
                    self.log.debug("UserChangeSubscriber added '%s'"%name)
                    yield ('email', name, authenticated, None)

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymouse" and 'email' not in req.session:
            return
        yield "watch_users", "Watch Users"

    def render_announcement_preference_box(self, req, panel):
        if req.method == "POST":
            names = req.args.get("announcer_watch_users")
            if names:
                req.session['announcer_watch_users'] = names
            elif req.session.get('announcer_watch_users'):
                del req.session['announcer_watch_users']
        return "prefs_announcer_watch_users.html", dict(data=dict(
            announcer_watch_users=req.session.get('announcer_watch_users', '')
        ))
