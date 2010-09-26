# -*- coding: utf-8 -*-
#
# Copyright (c) 2008, Stephen Hansen
# Copyright (c) 2009, Robert Corsaro
# Copyright (c) 2010, Steffen Hoffmann
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <ORGANIZATION> nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------

import re, urllib

from fnmatch import fnmatch

from trac.config import BoolOption, Option, ListOption
from trac.core import *
from trac.resource import ResourceNotFound, get_resource_url
from trac.ticket import model
from trac.ticket.api import ITicketChangeListener
from trac.util.text import to_unicode
from trac.web.api import IRequestFilter, IRequestHandler, Href
from trac.web.chrome import ITemplateProvider, add_ctxtnav, add_stylesheet
from trac.web.chrome import add_warning, add_script
from trac.wiki.api import IWikiChangeListener

from genshi.builder import tag

from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import IAnnouncementSubscriber
from announcer.api import IAnnouncementSubscriberDeprecated
from announcer.api import _, istrue
from announcer.model import Subscription
from announcer.util.settings import BoolSubscriptionSetting
from announcer.util.settings import SubscriptionSetting

class AllTicketSubscriber(Component):
    """Subscriber for all ticket changes."""
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementSubscriberDeprecated)
    implements(IAnnouncementPreferenceProvider)

    def get_announcement_preference_boxes(self, req):
        yield "tickets", _("Ticket Subscriptions")

    def render_announcement_preference_box(self, req, panel):
        setting = BoolSubscriptionSetting(self.env, "all_tickets")
        if req.method == "POST":
            value = req.args.get('ticket_all', False)
            setting.set_user_setting(req.session, value=value)
        vars = {}
        vars['ticket_all'] = setting.get_user_setting(req.session.sid)[1]
        return "prefs_announcer_ticket_all.html", dict(data=vars)

    def description(self):
        return "notify me when any ticket changes"

    def subscriptions(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid
              FROM session_attribute
             WHERE name='sub_all_tickets'
        """)
        for row in cursor.fetchall():
            sid = row[0]
            b = BoolSubscriptionSetting(self.env, 'all_tickets')
            dist, value, authed = b.get_user_setting(sid)
            if value:
                self.log.debug(_("AllTicketSubscriber added '%s" \
                    "'."%sid))
                yield (dist, sid, authed, None, None)

    def matches(self, event):
        klass = self.__class__.__name__
        for i in Subscription.find_by_class(self.env, klass):
            yield i.subscription_tuple()


class TicketOwnerSubscriber(Component):
    implements(IAnnouncementSubscriber)

    owner = BoolOption("announcer", "always_notify_owner", 'true',
        """The always_notify_owner option mimics the option of the same name
        in the notification section, except users can override in their
        preferences.
        """)

    def matches(self, event):
        if event.realm != "ticket":
            return
        if event.category not in ('created', 'changed', 'attachment added'):
            return
        ticket = event.target
        if not ticket['owner']:
            return

        subs = Subscription.find_by_sids_and_class(
                self.env, (ticket['owner'],), self.__class__.__name__)
        for s in subs:
            yield s.subscription_tuple()

    def description(self):
        return "notify me when a ticket that I own is created or modified"

class TicketComponentOwnerSubscriber(Component):
    implements(IAnnouncementSubscriber)

    component_owner = BoolOption("announcer", "always_notify_component_owner",
        'true',
        """Whether or not to notify the owner of the ticket's component.  The
        user can override this setting in their preferences.
        """)

    def matches(self, event):
        if event.realm != "ticket":
            return
        if event.category not in ('created', 'changed', 'attachment added'):
            return
        ticket = event.target
        try:
            component = model.Component(self.env, ticket['component'])
            if component.owner:
                if '@' in component.owner:
                    yield (self.__class__.__name__, 'email', None, False, component.owner, None, 1, 'always')
                else:
                    subs = Subscription.find_by_sids_and_class(
                            self.env, (component.owner,), self.__class__.__name__)
                    for s in subs:
                        yield s.subscription_tuple()
        except:
            self.log.debug("Component for ticket (%s) not found"%ticket['id'])

    def description(self):
        return "notify me when a ticket that belongs to a component that I own is created or modified"

class TicketUpdaterSubscriber(Component):
    implements(IAnnouncementSubscriber)

    updater = BoolOption("announcer", "always_notify_updater", 'true',
        """The always_notify_updater option mimics the option of the
        same name in the notification section, except users can override in
        their preferences.
        """)

    def matches(self, event):
        if event.realm != "ticket":
            return
        if event.category not in ('created', 'changed', 'attachment added'):
            return

        if event.author:
            subs = Subscription.find_by_sids_and_class(
                    self.env, (event.author,), self.__class__.__name__)
            for s in subs:
                yield s.subscription_tuple()

    def description(self):
        return "notify me when I update a ticket"

class TicketReporterSubscriber(Component):
    implements(IAnnouncementSubscriber)

    reporter = BoolOption("announcer", "always_notify_reporter", 'true',
        """The always_notify_reporter option mimics the option of the
        same name in the notification section, except users can override in
        their preferences.
        """)

    def matches(self, event):
        if event.realm != "ticket":
            return
        if event.category not in ('created', 'changed', 'attachment added'):
            return

        ticket = event.target
        if ticket['reporter']:
            reporter = ticket['reporter']
            if '@' in reporter and self.reporter:
                yield (self.__class__.__name__, 'email', None, False, reporter, None, 1, 'always')
            else:
                subs = Subscription.find_by_sids_and_class(
                        self.env, (reporter,), self.__class__.__name__)
                for s in subs:
                    yield s.subscription_tuple()

    def description(self):
        return "notify me when a ticket that I reported is updated"

class CarbonCopySubscriber(Component):
    """Carbon copy subscriber for cc ticket field."""
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementSubscriber)

    def subscriptions(self, event):
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
                        yield ('email', name, name and True or False, address, None)

    def matches(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('created', 'changed', 'attachment added'):
            return

        cc = event.target['cc'] or ''
        for chunk in re.split('\s|,', cc):
            chunk = chunk.strip()
            if not chunk or chunk.startswith('@'):
                continue
            if '@' in chunk:
                address = chunk
                sid = None
            else:
                sid = chunk
                address = None
            if sid or address:
                if not sid:
                    yield (self.__class__.__name__, 'email', None, False, address, None, 1, 'always')
                else:
                    subs = Subscription.find_by_sids_and_class(
                            self.env, (sid,), self.__class__.__name__)
                    for s in subs:
                        yield s.subscription_tuple()

    def description(self):
        return "notify me when I'm listed in the CC field of a ticket"

class LegacyTicketSubscriber(Component):
    """DEPRECATED: Mimics Trac notification settings with added bonus of letting users
    override their settings.
    """
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementPreferenceProvider)

    owner = BoolOption("announcer", "always_notify_owner", 'true',
        """The always_notify_owner option mimics the option of the same name
        in the notification section, except users can override in their
        preferences.
        """)

    reporter = BoolOption("announcer", "always_notify_reporter", 'true',
        """The always_notify_reporter option mimics the option of the
        same name in the notification section, except users can override in
        their preferences.
        """)

    updater = BoolOption("announcer", "always_notify_updater", 'true',
        """The always_notify_updater option mimics the option of the
        same name in the notification section, except users can override in
        their preferences.
        """)

    component_owner = BoolOption("announcer", "always_notify_component_owner",
        'true',
        """Whether or not to notify the owner of the ticket's component.  The
        user can override this setting in their preferences.
        """)

    def get_announcement_preference_boxes(self, req):
        yield "legacy", _("Ticket Subscriptions")

    def render_announcement_preference_box(self, req, panel):
        settings = self._settings()
        if req.method == "POST":
            for attr, setting in settings.items():
                setting.set_user_setting(req.session,
                    value=req.args.get('legacy_notify_%s'%attr), save=False)
            req.session.save()

        vars = {}
        for attr, setting in settings.items():
            vars[attr] = setting.get_user_setting(req.session.sid)[1]
        return "prefs_announcer_legacy.html", dict(data=vars)

    def subscriptions(self, event):
        if event.realm == "ticket":
            if event.category in ('created', 'changed', 'attachment added'):
                settings = self._settings()
                ticket = event.target
                for attr, setting in settings.items():
                    getter = self.__getattribute__('_get_%s'%attr)
                    subscription = getter(event, ticket, setting)
                    if subscription:
                        yield subscription + (None,)

    # A group of helpers for getting each type of subscriber
    def _get_component_owner(self, event, ticket, setting):
        try:
            component = model.Component(self.env, ticket['component'])
            if component.owner:
                if setting.get_user_setting(component.owner)[1]:
                    self._log_sub(component.owner, True, setting.name)
                    return ('email', component.owner, True, None)
        except ResourceNotFound, message:
            self.log.warn(_("LegacyTicketSubscriber couldn't add " \
                    "component owner because component was not found, " \
                    "message: '%s'"%(message,)))

    def _get_owner(self, event, ticket, setting):
        if ticket['owner']:
            if setting.get_user_setting(ticket['owner'])[1]:
                owner = ticket['owner']
                if '@' in owner:
                    name, authenticated, address = None, False, owner
                else:
                    name, authenticated, address = owner, True, None
                self._log_sub(owner, authenticated, setting.name)
                return ('email', name, authenticated, address)

    def _get_reporter(self, event, ticket, setting):
        if ticket['reporter']:
            if setting.get_user_setting(ticket['reporter'])[1]:
                reporter = ticket['reporter']
                if '@' in reporter:
                    name, authenticated, address = None, False, reporter
                else:
                    name, authenticated, address = reporter, True, None
                self._log_sub(reporter, authenticated, setting.name)
                return ('email', name, authenticated, address)

    def _get_updater(self, event, ticket, setting):
        if event.author:
            if setting.get_user_setting(event.author)[1]:
                self._log_sub(event.author, True, setting.name)
                return ('email', event.author, True, None)

    def _log_sub(self, author, authenticated, rule):
        """Log subscriptions"""
        auth = authenticated and 'authenticated' or 'not authenticated'
        self.log.debug("""LegacyTicketSubscriber added '%s (%s)' because of
            rule: always_notify_%s
            """%(author, auth, rule))

    def _settings(self):
        ret = {}
        for p in ('component_owner', 'owner', 'reporter', 'updater'):
            default = self.__getattribute__(p)
            ret[p] = BoolSubscriptionSetting(self.env, "ticket_%s"%p, default)
        return ret

class TicketComponentSubscriber(Component):
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementSubscriberDeprecated)
    implements(IAnnouncementPreferenceProvider)

    def subscriptions(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return
        settings = self._settings()
        setting = settings.get(event.target['component'])
        if setting:
            for result in setting.get_subscriptions():
                self.log.debug("TicketComponentSubscriber added '%s " \
                        "(%s)' for component '%s'"%(
                        result[1], result[2], event.target['component']))
                yield result + (None,)

    def matches(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return

        component = event.target['component']
        if not component:
            return

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid
              FROM subscription_attribute
             WHERE value=%s
               AND class=%s
        """, (component,self.__class__.__name__))
        sids = map(lambda x: x[0], cursor.fetchall())

        klass = self.__class__.__name__
        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return "notify me when a ticket associated with a component I'm watching changes"

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "joinable_components", _("Ticket Component Subscriptions")

    def render_announcement_preference_box(self, req, panel):
        settings = self._settings()
        if req.method == "POST":
            for attr, setting in settings.items():
                setting.set_user_setting(req.session,
                    value=req.args.get('component_%s'%attr), save=False)
            req.session.save()
            @self.env.with_transaction()
            def update(db):
                cursor = db.cursor()
                cursor.execute("""
                DELETE FROM subscription_attribute
                      WHERE sid = %s
                        AND class = %s
                """, (req.session.sid,self.__class__.__name__))
                for i in req.args.keys():
                    g = re.match('^component_(.*)', i)
                    if g:
                        if istrue(req.args.get(i)):
                            cursor.execute("""
                            INSERT INTO subscription_attribute
                                        (sid, class, value)
                                 VALUES (%s, %s, %s)
                            """, (req.session.sid,
                                self.__class__.__name__, g.groups()[0]))

        d = {}
        for attr, setting in settings.items():
            d[attr]= setting.get_user_setting(req.session.sid)[1]
        return "prefs_announcer_joinable_components.html", dict(components=d)

    def _settings(self):
        settings = {}
        for component in model.Component.select(self.env):
            settings[component.name] = BoolSubscriptionSetting(
                self.env,
                'component_%s'%component.name
            )
        return settings


class TicketCustomFieldSubscriber(Component):
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementSubscriberDeprecated)

    custom_cc_fields = ListOption('announcer', 'custom_cc_fields',
            doc="Field names that contain users that should be notified on "
            "ticket changes")

    def subscriptions(self, event):
        if event.realm == 'ticket':
            ticket = event.target
            if event.category in ('changed', 'created', 'attachment added'):
                for sub in self._get_membership(event.target):
                    yield sub + (None,)

    def matches(self, event):
        yield

    def description(self):
        return "notify me when I'm listed in the (%s) field"%self.custom_cc_fields

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


class JoinableGroupSubscriber(Component):
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementSubscriberDeprecated)
    implements(IAnnouncementPreferenceProvider)

    joinable_groups = ListOption('announcer', 'joinable_groups', [],
        doc="""Joinable groups represent 'opt-in' groups that users may
        freely join.

        Enter a list of groups (without @) seperated by commas.  The name of
        the groups should be a simple alphanumeric string. By adding the group
        name preceeded by @ (such as @sec for the sec group) to the CC field of
        a ticket, everyone in that group will receive an announcement when that
        ticket is changed.
        """)

    def matches(self, event):
        yield

    def description(self):
        return "notify me on ticket changes in one of my subscribed groups"

    def subscriptions(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return
        settings = self._settings()
        cc = event.target['cc'] or ''
        for chunk in re.split('\s|,', cc):
            chunk = chunk.strip()
            if chunk.startswith('@'):
                member = None
                grp = chunk[1:]
                for member in settings[grp].get_subscriptions():
                    self.log.debug(
                        "JoinableGroupSubscriber added '%s (%s)' " \
                        "because of opt-in to group: %s"%(member[1], \
                        member[2] and 'authenticated' or \
                        'not authenticated', grp))
                    yield member + (None,)
                if member is None:
                    self.log.debug("JoinableGroupSubscriber found " \
                            "no members for group: %s."%grp)

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        if self.joinable_groups:
            yield "joinable_groups", _("Group Subscriptions")

    def render_announcement_preference_box(self, req, panel):
        settings = self._settings()
        if req.method == "POST":
            for grp, setting in settings.items():
                setting.set_user_setting(req.session,
                    value=req.args.get('joinable_group_%s'%grp), save=False)
            req.session.save()
        groups = {}
        for grp, setting in settings.items():
            groups[grp] = setting.get_user_setting(req.session.sid)[1]
        data = dict(joinable_groups = groups)
        return "prefs_announcer_joinable_groups.html", data

    def _settings(self):
        settings = {}
        for grp in self.joinable_groups:
            settings[grp[1:]] = BoolSubscriptionSetting(
                    self.env, 'group_%s'%grp[1:])
        return settings

class UserChangeSubscriber(Component):
    """Allows users to get notified anytime a particular user change or
    modifies a ticket or wiki page."""
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementSubscriberDeprecated)
    implements(IAnnouncementPreferenceProvider)

    def matches(self, event):
        yield

    def description(self):
        return "notify me when one of my watched users changes something"

    def subscriptions(self, event):
        if event.realm in ('wiki', 'ticket'):
            if event.category in ('changed', 'created', 'attachment added'):
                def match(dist, val):
                    for part in val.split(','):
                        if part.strip() == event.author:
                            return True
                for sub in self._setting().get_subscriptions(match):
                    self.log.debug("UserChangeSubscriber added '%s'"%sub[1])
                    yield sub + (None,)

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymouse" and 'email' not in req.session:
            return
        yield "watch_users", _("Watch Users")

    def render_announcement_preference_box(self, req, panel):
        setting = self._setting()
        if req.method == "POST":
            setting.set_user_setting(req.session,
                    value=req.args.get("announcer_watch_users"))
        return "prefs_announcer_watch_users.html", dict(data=dict(
            announcer_watch_users=setting.get_user_setting(req.session.sid)[1]
        ))

    def _setting(self):
        return SubscriptionSetting(self.env, 'watch_users')
class WatchSubscriber(Component):

    implements(IRequestFilter)
    implements(IRequestHandler)
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementSubscriberDeprecated)
    implements(ITicketChangeListener)
    implements(IWikiChangeListener)

    watchable_paths = ListOption('announcer', 'watchable_paths',
        'wiki/*,ticket/*',
        doc='List of URL paths to allow watching. Globs are supported.')
    ctxtnav_names = ListOption('announcer', 'ctxtnav_names',
        "Watch This, Unwatch This",
        doc="Text of context navigation entries. "
            "An empty list removes them from the context navigation bar.")

    path_match = re.compile(r'/watch/(.*)')

    # IRequestHandler methods
    def match_request(self, req):
        if self.path_match.match(req.path_info):
            realm = self.normalise_resource(req.path_info).split('/')[1]
            return "%s_VIEW" % realm.upper() in req.perm
        return False

    def process_request(self, req):
        match = self.path_match.match(req.path_info)
        resource = self.normalise_resource(match.groups()[0])
        realm = resource.split('/', 1)[0]
        req.perm.require('%s_VIEW' % realm.upper())
        self.toggle_watched(req.session.sid, (not req.authname == \
                'anonymous') and 1 or 0, resource, req)
        req.redirect(req.href(resource))

    def toggle_watched(self, sid, authenticated, resource, req=None):
        realm, resource = resource.split('/', 1)
        if self.is_watching(sid, authenticated, realm, resource):
            self.set_unwatch(sid, authenticated, realm, resource)
            self._schedule_notice(req, _('You are no longer receiving ' \
                    'change notifications about this resource.'))
        else:
            self.set_watch(sid, authenticated, realm, resource)
            self._schedule_notice(req, _('You are now receiving ' \
                    'change notifications about this resource.'))

    def _schedule_notice(self, req, message):
        req.session['_announcer_watch_message_'] = message

    def _add_notice(self, req):
        if '_announcer_watch_message_' in req.session:
            from trac.web.chrome import add_notice
            add_notice(req, req.session['_announcer_watch_message_'])
            del req.session['_announcer_watch_message_']

    def is_watching(self, sid, authenticated, realm, resource):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT id
              FROM subscriptions
             WHERE sid=%s AND authenticated=%s
               AND enabled=1 AND managed=%s
               AND realm=%s
               AND category=%s
               AND rule=%s
        """, (sid, int(authenticated), 'watcher', realm, '*',
                to_unicode(resource)))
        result = cursor.fetchone()
        if result:
            return True
        else:
            return False

    def set_watch(self, sid, authenticated, realm, resource):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        self.set_unwatch(sid, authenticated, realm, resource, use_db=db)
        cursor.execute("""
            INSERT INTO subscriptions
                        (sid, authenticated,
                         enabled, managed,
                         realm, category,
                         rule, transport)
                 VALUES
                        (%s, %s,
                         1, %s,
                         %s, %s,
                         %s, %s)
        """, (
                sid, int(authenticated),
                'watcher', realm, '*',
                resource, 'email'
            )
        )
        db.commit()

    def set_unwatch(self, sid, authenticated, realm, resource, use_db=None):
        if not use_db:
            db = self.env.get_db_cnx()
        else:
            db = use_db
        cursor = db.cursor()
        cursor.execute("""
            DELETE
              FROM subscriptions
             WHERE sid=%s AND authenticated=%s
               AND enabled=1 AND managed=%s
               AND realm=%s
               AND category=%s
               AND rule=%s
        """, (sid, int(authenticated), 'watcher', realm, '*',
            to_unicode(resource)))
        if not use_db:
            db.commit()

    # IRequestFilter methods
    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, content_type):
        self._add_notice(req)

        if req.authname != "anonymous" or (req.authname == 'anonymous' and \
                'email' in req.session):
            for pattern in self.watchable_paths:
                path = self.normalise_resource(req.path_info)
                if fnmatch(path, pattern):
                    realm = path.split('/', 1)[0]
                    if '%s_VIEW'%realm.upper() not in req.perm:
                        return (template, data, content_type)
                    self.render_watcher(req)
                    break
        return (template, data, content_type)

    # Internal methods
    def render_watcher(self, req):
        if not self.ctxtnav_names:
          return
        resource = self.normalise_resource(req.path_info)
        parts = resource.split('/', 1)
        if len(parts) < 2:
            return
        realm, resource = parts
        if self.is_watching(req.session.sid, not req.authname == 'anonymous',
                realm, resource):
            action_name = len(self.ctxtnav_names) >= 2 and \
                    self.ctxtnav_names[1] or 'Unwatch This'
        else:
            action_name = len(self.ctxtnav_names) and \
                    self.ctxtnav_names[0] or 'Watch This'
        add_ctxtnav(req,
            tag.a(
                _(action_name), href=req.href.watch(realm, resource)
            )
        )

    def normalise_resource(self, resource):
        if isinstance(resource, basestring):
            resource = resource.strip('/')
            # Special-case start page
            if not resource:
                resource = "wiki/WikiStart"
            elif resource == 'wiki':
                resource += '/WikiStart'
            return resource
        return get_resource_url(self.env, resource, Href('')).strip('/')

    # IWikiChangeListener
    def wiki_page_added(*args):
        pass

    def wiki_page_changed(*args):
        pass

    def wiki_page_deleted(self, page):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            DELETE
              FROM subscriptions
             WHERE managed=%s
               AND realm=%s
               AND rule=%s
        """, ('watcher', 'wiki', to_unicode(page.name)))
        db.commit()

    def wiki_page_version_deleted(*args):
        pass

    # ITicketChangeListener
    def ticket_created(*args):
        pass

    def ticket_changed(*args):
        pass

    def ticket_deleted(self, ticket):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            DELETE
              FROM subscriptions
             WHERE managed=%s
               AND realm=%s
               AND rule=%s
        """, ('watcher', 'ticket', to_unicode(ticket.id)))
        db.commit()

    def matches(self, event):
        yield

    def description(self):
        return "notify me when one of my watched wiki or tickets is updated"

    # IAnnouncementSubscriber
    def subscriptions(self, event):
        if event.realm in ('wiki', 'ticket'):
            db = self.env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute("""
                SELECT transport, sid, authenticated
                  FROM subscriptions
                 WHERE enabled=1 AND managed=%s
                   AND realm=%s
                   AND category=%s
                   AND rule=%s
            """, ('watcher', event.realm, '*',
                to_unicode(self._get_target_identifier(event.realm,
                event.target))))

            for transport, sid, authenticated in cursor.fetchall():
                self.log.debug("WatchSubscriber added '%s (%s)' because " \
                    "of rule: watched"%(sid,authenticated and \
                    'authenticated' or 'not authenticated'))
                yield (transport, sid, authenticated, None, None)

    def _get_target_identifier(self, realm, target):
        if realm == "wiki":
            return target.name
        elif realm == "ticket":
            return target.id

class GeneralWikiSubscriber(Component):
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementSubscriberDeprecated)
    implements(IAnnouncementPreferenceProvider)

    def matches(self, event):
        yield

    def description(self):
        return "notify me when a wiki that matches my wiki watch pattern is created, or updated"

    def subscriptions(self, event):
        if event.realm != 'wiki':
            return
        if event.category not in ('changed', 'created', 'attachment added',
                'deleted', 'version deleted'):
            return

        def match(dist, value):
            for raw in value.split(' '):
                if raw != '':
                    pat = urllib.unquote(raw).replace('*', '.*')
                    if re.match(pat, event.target.name):
                        return True

        setting = self._setting()
        for result in setting.get_subscriptions(match):
            self.log.debug("GeneralWikiSubscriber added '%s (%s)'"%(
                    result[1], result[2]))
            yield result + (None,)

    def get_announcement_preference_boxes(self, req):
        if req.perm.has_permission('WIKI_VIEW'):
            yield "general_wiki", _("General Wiki Announcements")

    def render_announcement_preference_box(self, req, panel):
        if req.perm.has_permission('WIKI_VIEW'):
            setting = self._setting()
            if req.method == "POST":
                setting.set_user_setting(req.session,
                        value=req.args.get('wiki_interests'))
            interests = setting.get_user_setting(req.session.sid)[1] or ''
            return "prefs_announcer_wiki.html", dict(
                wiki_interests = '\n'.join(
                    urllib.unquote(x) for x in interests.split(' ')
                )
            )

    def _setting(self):
        return SubscriptionSetting(self.env, 'wiki_pattern')
