from trac.core import Component, implements
from trac.util.compat import sorted

from announcerplugin.api import IAnnouncementAddressResolver
from announcerplugin.api import IAnnouncementPreferenceProvider

class SpecifiedEmailResolver(Component):
    implements(IAnnouncementAddressResolver, IAnnouncementPreferenceProvider)
    
    def get_address_for_name(self, name, authenticated):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT value
              FROM session_attribute
             WHERE sid=%s
               AND authenticated=1
               AND name=%s
        """, (name,'announcer_specified_email'))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None    

    # IAnnouncementDistributor
    def get_announcement_preference_boxes(self, req):
        if req.authname != "anonymous":
            yield "emailaddress", "Announcement Email Address"
        
    def render_announcement_preference_box(self, req, panel):
        cfg = self.config
        sess = req.session
        if req.method == "POST":
            opt = req.args.get('specified_email', '')
            sess['announcer_specified_email'] = opt
        specified = sess.get('announcer_specified_email', '')
        data = dict(specified_email = specified,)
        return "prefs_announcer_emailaddress.html", data    
