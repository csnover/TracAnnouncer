from trac.core import Component, implements
from announcerplugin.api import IAnnouncementSubscriber, istrue
from announcerplugin.api import IAnnouncementPreferenceProvider
from trac.ticket import model
from trac.web.chrome import add_warning
from trac.config import ListOption
import re

class TicketCustomFieldSubscriber(Component):
    implements(IAnnouncementSubscriber)

    custom_cc_fields = ListOption('announcer', 'custom_cc_fields',
            doc="Field names that contain users that should be notified on "
            "ticket changes")
    
    def get_subscription_realms(self):
        return ('ticket',)
    
    def get_subscription_categories(self, realm):
        if realm == "ticket":
            return('changed', 'created', 'attachment added')
        else:
            ()
    
    def get_subscriptions_for_event(self, event):
        if event.realm == 'ticket':
            ticket = event.target
            if event.category in ('changed', 'created', 'attachment added'):
                for sub in self._get_membership(event.target):
                    yield sub

    def _get_membership(self, ticket):
        for field in self.custom_cc_fields:
            subs = ticket[field] or ''
            for chunk in re.split('\s|,', subs):
                chunk = chunk.strip()
                if not chunk or chunk.startswith('@'):
                    continue
                if '@' in chunk:
                    address = chunk
                    name = None
                else:
                    name = chunk
                    address = None
                if name or address:
                    self.log.debug("TicketCustomFieldSubscriber " \
                        "added '%s <%s>'"%(name,address))
                    yield ('email', name, name and True or False, address)

