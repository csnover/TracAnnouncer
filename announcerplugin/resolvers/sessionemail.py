from trac.core import Component, implements
from trac.util.compat import sorted

from announcerplugin.api import IAnnouncementAddressResolver

class SessionEmailResolver(Component):
    implements(IAnnouncementAddressResolver)
    
    def get_address_for_name(self, name, authenticated):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT value
              FROM session_attribute
             WHERE sid=%s
               AND authenticated=%s
               AND name=%s
        """, (name, authenticated and 1 or 0, 'email'))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
