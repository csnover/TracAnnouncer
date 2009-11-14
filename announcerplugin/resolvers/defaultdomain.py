from trac.core import Component, implements
from trac.util.compat import sorted
from trac.config import Option

from announcerplugin.api import IAnnouncementAddressResolver

class DefaultDomainEmailResolver(Component):
    implements(IAnnouncementAddressResolver)
    
    smtp_default_domain = Option('announcer', 'smtp_default_domain', '',
        """Default host/domain to append to address that do not specify one""")
    
    def get_address_for_name(self, name, authenticated):
        if self.smtp_default_domain:
            return '%s@%s' % (name, self.smtp_default_domain)
        return None    
