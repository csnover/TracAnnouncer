import re

from trac.core import *
from trac.config import BoolOption, Option
from trac.resource import ResourceNotFound
from trac.ticket import model
from trac.util.text import to_unicode
from trac.util.translation import _
from trac.web.chrome import add_warning

from announcerplugin.api import IAnnouncementSubscriber, istrue
from announcerplugin.api import IAnnouncementPreferenceProvider

class StaticTicketSubscriber(Component):
    """The static ticket subscriber implements a policy to -always- send an 
    email to a certain address. Controlled via the smtp_always_bcc option in 
    the announcer section of the trac.ini"""
    
    implements(IAnnouncementSubscriber)

    smtp_always_cc = Option("announcer", "smtp_always_cc", 
        doc="""Email addresses specified here will always
               be cc'd on all notifications.""")

    smtp_always_bcc = Option("announcer", "smtp_always_bcc", 
        doc="""Email addresses specified here will always
               be cc'd on all notifications.  With announce,
               bcc is unneccesary since users can't see
               each others email addresses.""")
    
    def get_subscription_realms(self):
        return (self.smtp_always_bcc or self.smtp_always_cc) and \
                ('*',) or tuple()
        
    def get_subscription_categories(self, realm):
        return (self.smtp_always_bcc or self.smtp_always_cc) and \
                ('*',) or tuple()
        
    def get_subscriptions_for_event(self, event):
        if self.smtp_always_cc:
            for s in self.smtp_always_cc.split(','):
                self.log.debug(_("StaticTicketSubscriber added '%s' " \
                        "because of rule: smtp_always_cc"%s))
                yield ('email', None, False, s.strip())
        if self.smtp_always_bcc:
            for s in self.smtp_always_bcc.split(','):
                self.log.debug(_("StaticTicketSubscriber added '%s' " \
                        "because of rule: smtp_always_bcc"%s))
                yield ('email', None, False, s.strip())

class LegacyTicketSubscriber(Component):
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
    
    always_notify_owner = BoolOption("announcer", "always_notify_owner", 'true', 
        """The always_notify_owner option mimics the option of the same name 
        in the notification section, except users can opt-out in their 
        preferences. Used only if LegacyTicketSubscriber is enabled.""")

    always_notify_reporter = BoolOption("announcer", "always_notify_reporter", 
        'true', """The always_notify_reporter option mimics the option of the 
        same name in the notification section, except users can opt-out in 
        their preferences. Used only if LegacyTicketSubscriber is enabled.""")

    always_notify_updater = BoolOption("announcer", "always_notify_updater", 
        'true', """The always_notify_updater option mimics the option of the 
        same name in the notification section, except users can opt-out in 
        their preferences. Used only if LegacyTicketSubscriber is enabled.""")

    always_notify_component_owner = BoolOption("announcer", 
            "always_notify_component_owner", 'true',
            """Whether or not to notify the owner of the ticket's 
            component.""")
        
    def get_announcement_preference_boxes(self, req):
        yield "legacy", "Ticket Subscriptions"

    def render_announcement_preference_box(self, req, panel):
        if req.method == "POST":
            for attr in ('component_owner', 'owner', 'reporter', 'updater'):
                val = req.args.get('legacy_notify_%s'%attr) == 'on'
                req.session['announcer_legacy_notify_%s'%attr] = val

        # component
        component = req.session.get('announcer_legacy_notify_component_owner')
        if component is None:
            component = self.always_notify_component_owner
        else:
            component = component == u'True'

        # owner
        owner = req.session.get('announcer_legacy_notify_owner')
        if owner is None:
            owner = self.always_notify_owner
        else:
            owner = owner == u'True'

        # reporter
        reporter = req.session.get('announcer_legacy_notify_reporter')
        if reporter is None:
            reporter = self.always_notify_reporter
        else:
            reporter = reporter == u'True'

        # updater
        updater = req.session.get('announcer_legacy_notify_updater')
        if updater is None:
            updater = self.always_notify_updater
        else:
            updater = updater == u'True'

        return "prefs_announcer_legacy.html", dict(
            data=dict(
                component=component,
                owner=owner,
                reporter=reporter,
                updater=updater
            )    
        )

    def get_subscription_realms(self):
        return ('ticket',)
        
    def get_subscription_categories(self, realm):
        if realm == 'ticket':
            return ('created', 'changed', 'attachment added')
        else:
            return tuple()

    def get_subscriptions_for_event(self, event):
        if event.realm == "ticket":
            if event.category in ('created', 'changed', 'attachment added'):
                ticket = event.target
                subs = filter(lambda a: a, (
                    self._always_notify_component_owner(ticket),
                    self._always_notify_ticket_owner(ticket),
                    self._always_notify_ticket_reporter(ticket), 
                    self._always_notify_ticket_updater(event, ticket)
                ))
                for s in subs:
                    yield s
    def _always_notify_component_owner(self, ticket):
        try:
            component = model.Component(self.env, ticket['component'])
            if component.owner:
                notify = self._check_user_setting('notify_component_owner', 
                        component.owner)
                if notify is None:
                    notify = self.always_notify_component_owner
                if notify:
                    self._log_sub(component.owner, True, 
                            'always_notify_component_owner')
                    return ('email', component.owner, True, None)
        except ResourceNotFound, message:
            self.log.warn(_("LegacyTicketSubscriber couldn't add " \
                    "component owner because component was not found, " \
                    "message: '%s'"%(message,)))

    def _always_notify_ticket_owner(self, ticket):
        if ticket['owner']:
            notify = self._check_user_setting('notify_owner', ticket['owner'])
            if notify is None:
                notify = self.always_notify_owner
            if notify: 
                owner = ticket['owner']
                if '@' in owner:
                    name, authenticated, address = None, False, owner
                else:
                    name, authenticated, address = owner, True, None
                self._log_sub(owner, authenticated, 'always_notify_owner')
                return ('email', name, authenticated, address)
        
    def _always_notify_ticket_reporter(self, ticket):
        if ticket['reporter']:
            notify = self._check_user_setting('notify_reporter', ticket['reporter'])
            if notify is None:
                notify = self.always_notify_reporter
            if notify:
                reporter = ticket['reporter']
                if '@' in reporter:
                    name, authenticated, address = None, False, reporter
                else:
                    name, authenticated, address = reporter, True, None
                self._log_sub(reporter, authenticated, 'always_notify_reporter')
                return ('email', name, authenticated, address)

    def _always_notify_ticket_updater(self, event, ticket):
        if event.author:
            notify = self._check_user_setting('notify_updater', event.author)
            if notify is None:
                notify = self.always_notify_updater
            if notify:
                self._log_sub(event.author, True, 'always_notify_updater')
                return ('email', event.author, True, None)
    
    def _log_sub(self, author, authenticated, rule):
        "Log subscriptions"
        auth = authenticated and 'authenticated' or 'not authenticated'
        self.log.debug(_("LegacyTicketSubscriber added '%s " \
            "(%s)' because of rule: %s"%(author, auth, rule)))
        
    def _check_user_setting(self, preference, sid):
        """Check the user's selection.  None means 
        they haven't selected anything."""
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT value 
              FROM session_attribute
             WHERE sid=%s
               AND authenticated=1
               AND name=%s
        """, (sid, 'announcer_legacy_' + preference))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None

class CarbonCopySubscriber(Component):
    implements(IAnnouncementSubscriber)
    
    def get_subscription_realms(self):
        return ('ticket',)
        
    def get_subscription_categories(self, realm):
        if realm == 'ticket':
            return ('created', 'changed', 'attachment added')
        else:
            return tuple()
        
    def get_subscriptions_for_event(self, event):
        if event.realm == 'ticket':
            if event.category in ('created', 'changed', 'attachment added'):
                cc = event.target['cc'] or ''
                for chunk in re.split('\s|,', cc):
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
                        self.log.debug(_("CarbonCopySubscriber added '%s " \
                            "<%s>' because of rule: carbon copied" \
                            %(name,address)))
                        yield ('email', name, name and True or False, address)
        
