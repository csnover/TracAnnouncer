from trac.core import Component, implements, TracError
from trac.web.chrome import add_stylesheet
from announcerplugin.api import IAnnouncementSubscriber
from announcerplugin.api import IAnnouncementPreferenceProvider
from announcerplugin.query import *

class RuleBasedTicketSubscriber(Component):
    
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
    
    # IAnnouncementSubscriber
    def get_subscription_realms(self):
        return ('*', )
        
    def get_subscription_categories(self, realm):
        return ('*', )
        
    def get_subscriptions_for_event(self, event):
        terms = self._get_basic_terms(event)
        db = self.env.get_db_ctx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT id, sid, authenticated, rule
              FROM subscriptions
             WHERE enabled=1 AND managed=''
               AND realm=%s
               AND category=%s
        """, (event.realm, event.category))
        for rule_id, session_id, authenticated, rule in cursor.fetchall():
            query = Query(rule)
            print "For", session_id, "Rule:", rule
            if query(terms + self._get_session_terms(session_id, event)):
                print True
            else:
                print False
        
    def _get_basic_terms(self, event):
        terms = [event.realm, event.category]
        try:
            terms.extend(event.get_basic_terms())
        except:
            pass
        print "Basic terms", terms
        return terms
        
    def _get_session_terms(self, session_id, event):
        terms = []
        try:
            terms.extend(event.get_session_terms(session_id))
        except:
            pass
        print "Session terms", terms
        return terms
        
    # IAnnouncementPreferenceProvider
    def get_announcement_preference_boxes(self, req):
        yield ('rules', 'Rule-based subscriptions')
        
    def render_announcement_preference_box(self, req, box):
        add_stylesheet(req, 'announcerplugin/css/rulediv.css')
        categories = {
            'ticket': ('created', 'changed', 'attachment added', 'deleted'),
            'wiki': ('created', 'changed', 'attachment added', 'deleted')
        }
        rules = [
            dict(
                id=1,
                enabled=True,
                realm="ticket",
                category="changed",
                value="this or that",
            ),
            dict(
                id=3,
                enabled=False,
                realm="wiki",
                category="created",
                value="this or that",
            ),
            dict(
                id=5,
                enabled=True,
                realm="ticket",
                category="changed",
                value="this or that",
            ),
        ]
        data = dict(
            categories=categories,
            rules=rules,
        )
        return "prefs_announcer_rules.html", data 
