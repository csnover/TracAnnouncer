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

# TODO: Test all anonymous subscribers
# TODO: Subscriptions admin page

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
from trac.web.chrome import add_warning, add_script, add_notice
from trac.wiki.api import IWikiChangeListener

from genshi.builder import tag

from announcer.api import IAnnouncementDefaultSubscriber
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import IAnnouncementSubscriber
from announcer.api import _, istrue
from announcer.model import Subscription, SubscriptionAttribute
from announcer.util.settings import BoolSubscriptionSetting
from announcer.util.settings import SubscriptionSetting

"""Subscribers should return a list of subscribers based on event rules.
The subscriber interface is very simple and flexible.  Subscription have
an 'adverb' attached, always or never.  A subscription can also stop a
subscriber from recieving a notification if it's adverb is 'never' and it
is the highest priority matching subscription.

One thing that remains to be done is to allow admin to control defaults for
users that never login and set their subscriptions up.  Some of these
should look to see if the user has any subscriptions in the subscription
table, and if it doesn't, then use the default setting from trac.ini.

There should also be a screen in the admin section of the site that let's the
admin setup rules for users.  It should be possible to copy rules from one
user to another.

We must also support unauthenticated users in the form of email addresses.
An email address can be used in place of an sid in many places in Trac.
Here's what I can think of:

 * Component owner
 * CC field
 * Custom cc field
 * Ticket owner
 * Ticket reporter

The final thing to consider is unauthenticated users who have entered an email
address in the preferences panel.  To me this is the least important case and
will probably be lowest priority.

"""

class AllTicketSubscriber(Component):
    """Subscriber for all ticket changes."""
    implements(IAnnouncementSubscriber)

    def description(self):
        return _("notify me when any ticket changes")

    def matches(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return

        klass = self.__class__.__name__
        for i in Subscription.find_by_class(self.env, klass):
            yield i.subscription_tuple()


class TicketOwnerSubscriber(Component):
    """Allows ticket owners to subscribe to their tickets."""
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementDefaultSubscriber)

    default_on = BoolOption("announcer", "always_notify_owner", 'true',
        """The always_notify_owner option mimics the option of the same name
        in the notification section, except users can override in their
        preferences.
        """)

    default_distributor = ListOption("announcer",
        "always_notify_owner_distributor", "email",
        doc="""Comma seperated list of distributors to send the message to
        by default.  ex. email, xmpp
        """)

    def matches(self, event):
        if event.realm != "ticket":
            return
        if event.category not in ('created', 'changed', 'attachment added'):
            return
        ticket = event.target
        if not ticket['owner']:
            return

        klass = self.__class__.__name__

        subs = Subscription.find_by_sids_and_class(
                self.env, (ticket['owner'],), klass)
        for s in subs:
            yield s.subscription_tuple()

        # Default subscription
        for s in self.default_subscriptions():
            if re.match(r'^[^@]+@.+', ticket['owner']):
                sid, auth, addr = None, None, ticket['owner']
            else:
                sid, auth, addr = ticket['owner'], True, None
            yield (s[0], s[1], ticket['owner'], sid, auth, addr, None, s[3],
                    s[4])

    def description(self):
        return _("notify me when a ticket that I own is created or modified")

    def default_subscriptions(self):
        if self.default_on:
            for d in self.default_distributor:
                yield (self.__class__.__name__, d, 101, 'always')


class TicketComponentOwnerSubscriber(Component):
    """Allows component owners to subscribe to tickets assigned to their
    components.
    """
    implements(IAnnouncementDefaultSubscriber)
    implements(IAnnouncementSubscriber)

    default_on = BoolOption("announcer", "always_notify_component_owner",
        'true',
        """Whether or not to notify the owner of the ticket's component.  The
        user can override this setting in their preferences.
        """)

    default_distributor = ListOption("announcer",
        "always_notify_component_owner_distributor", "email",
        doc="""Comma seperated list of distributors to send the message to
        by default.  ex. email, xmpp
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
                    yield (self.__class__.__name__, 'email', None, False,
                            component.owner, None, 1, 'always')
                else:
                    subs = Subscription.find_by_sids_and_class(
                            self.env, (component.owner,), self.__class__.__name__)
                    for s in subs:
                        yield s.subscription_tuple()

                # Default subscription
                for s in self.default_subscriptions():
                    if re.match(r'^[^@]+@.+', component.owner):
                        sid, auth, addr = None, None, component.owner
                    else:
                        sid, auth, addr = component.owner, True, None
                    yield (s[0], s[1], component.owner, sid, auth, addr, None,
                            s[3], s[4])
        except:
            self.log.debug("Component for ticket (%s) not found"%ticket['id'])

    def description(self):
        return _("notify me when a ticket that belongs to a component "
                "that I own is created or modified")

    def default_subscriptions(self):
        if self.default_on:
            for d in self.default_distributor:
                yield (self.__class__.__name__, d, 101, 'always')

class TicketUpdaterSubscriber(Component):
    """Allows updaters to subscribe to their own updates."""
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
        return _("notify me when I update a ticket")

class TicketReporterSubscriber(Component):
    """Allows the users to subscribe to tickets that they report."""
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
                yield (self.__class__.__name__, 'email', None, False,
                        reporter, None, 1, 'always')
            else:
                subs = Subscription.find_by_sids_and_class(
                        self.env, (reporter,), self.__class__.__name__)
                for s in subs:
                    yield s.subscription_tuple()

    def description(self):
        return _("notify me when a ticket that I reported is updated")

class CarbonCopySubscriber(Component):
    """Carbon copy subscriber for cc ticket field."""
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementSubscriber)

    def matches(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('created', 'changed', 'attachment added'):
            return

        klass = self.__class__.__name__
        cc = event.target['cc'] or ''
        sids = set()
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
                    yield (klass, 'email', None, False, address, None, 1, 'always')
                else:
                    sids.add(sid)
        for s in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield s.subscription_tuple()

    def description(self):
        return _("notify me when I'm listed in the CC field of a ticket")


class TicketComponentSubscriber(Component):
    """Allows users to subscribe to ticket assigned to the components of their
    choice.
    """
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementPreferenceProvider)

    def matches(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return

        component = event.target['component']
        if not component:
            return

        klass = self.__class__.__name__

        attrs = SubscriptionAttribute.find_by_class_realm_and_target(
                self.env, klass, 'ticket', component)
        sids = set(map(lambda x: x['sid'], attrs))

        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return _("notify me when a ticket associated with " \
                "a component I'm watching changes")

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "joinable_components", _("Ticket Component Subscriptions")

    def render_announcement_preference_box(self, req, panel):
        klass = self.__class__.__name__
        if req.method == "POST":
            @self.env.with_transaction()
            def do_update(db):
                SubscriptionAttribute.delete_by_sid_and_class(self.env,
                        req.session.sid, klass, db)
                def _map(value):
                    g = re.match('^component_(.*)', value)
                    if g:
                        if istrue(req.args.get(value)):
                            return g.groups()[0]
                components = set(filter(None, map(_map,req.args.keys())))
                SubscriptionAttribute.add(self.env, req.session.sid, klass,
                        'ticket', components, db)

        d = {}
        attrs = filter(None, map(
            lambda x: x['target'],
            SubscriptionAttribute.find_by_sid_and_class(
                self.env, req.session.sid, klass
            )
        ))
        for c in model.Component.select(self.env):
            if c.name in attrs:
                d[c.name] = True
            else:
                d[c.name] = None

        return "prefs_announcer_joinable_components.html", dict(components=d)


class TicketCustomFieldSubscriber(Component):
    """Allows users to subscribe to tickets that have their sid listed in any
    field that has a name in the custom_cc_fields list.  The custom_cc_fields
    list must be configured by the system administrator.
    """
    implements(IAnnouncementSubscriber)

    custom_cc_fields = ListOption('announcer', 'custom_cc_fields',
            doc="Field names that contain users that should be notified on "
            "ticket changes")

    def matches(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return

        klass = self.__class__.__name__
        ticket = event.target
        sids = set()

        for field in self.custom_cc_fields:
            subs = ticket[field] or ''
            for chunk in re.split('\s|,', subs):
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
                    self.log.debug("TicketCustomFieldSubscriber " \
                        "added '%s <%s>'"%(sid,address))
                    if not sid:
                        yield (klass, 'email', None, False, address, None, 1,
                                'always')
                    else:
                        sids.add(sid)

        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return _("notify me when I'm listed in any of the (%s) "
                 "fields"%(','.join(self.custom_cc_fields),))


class JoinableGroupSubscriber(Component):
    """Allows users to subscribe to groups as defined by the system
    administrator.  Any ticket with the said group listed in the cc
    field will trigger announcements to users in the group.
    """
    implements(IAnnouncementSubscriber)
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
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return

        klass = self.__class__.__name__
        ticket = event.target
        sids = set()

        cc = event.target['cc'] or ''
        for chunk in re.split('\s|,', cc):
            chunk = chunk.strip()
            if chunk and chunk.startswith('@'):
                member = None
                grp = chunk[1:]

                attrs = SubscriptionAttribute.find_by_class_realm_and_target(
                        self.env, klass, 'ticket', grp)
                sids.update(set(map(lambda x: x['sid'], attrs)))

        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return _("notify me on ticket changes in one of my subscribed groups")

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        if self.joinable_groups:
            yield "joinable_groups", _("Group Subscriptions")

    def render_announcement_preference_box(self, req, panel):
        klass = self.__class__.__name__

        if req.method == "POST":
            @self.env.with_transaction()
            def do_update(db):
                SubscriptionAttribute.delete_by_sid_and_class(self.env,
                        req.session.sid, klass, db)
                def _map(value):
                    g = re.match('^joinable_group_(.*)', value)
                    if g:
                        if istrue(req.args.get(value)):
                            return g.groups()[0]
                groups = set(filter(None, map(_map,req.args.keys())))
                SubscriptionAttribute.add(self.env, req.session.sid, klass,
                        'ticket', groups, db)

        attrs = filter(None, map(
            lambda x: x['target'],
            SubscriptionAttribute.find_by_sid_and_class(
                self.env, req.session.sid, klass
            )
        ))
        data = dict(joinable_groups = {})
        for group in self.joinable_groups:
            data['joinable_groups'][group] = (group in attrs) and True or None
        return "prefs_announcer_joinable_groups.html", data


class UserChangeSubscriber(Component):
    """Allows users to get notified anytime a particular user change
    triggers an event.
    """
    implements(IAnnouncementSubscriber)
    implements(IAnnouncementPreferenceProvider)

    def matches(self, event):
        klass = self.__class__.__name__

        attrs = SubscriptionAttribute.find_by_class_realm_and_target(
                self.env, klass, 'user', event.author)
        sids = set(map(lambda x: x['sid'], attrs))

        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return _("notify me when one of my watched users changes something")

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "watch_users", _("Watch Users")

    def render_announcement_preference_box(self, req, panel):
        klass = self.__class__.__name__

        if req.method == "POST":
            @self.env.with_transaction()
            def do_update(db):
                SubscriptionAttribute.delete_by_sid_and_class(self.env,
                        req.session.sid, klass, db)
                users = map(lambda x: x.strip(),
                        req.args.get("announcer_watch_users").split(','))
                SubscriptionAttribute.add(self.env, req.session.sid, klass,
                        'user', users, db)

        attrs = filter(None, map(
            lambda x: x['target'],
            SubscriptionAttribute.find_by_sid_and_class(
                self.env, req.session.sid, klass
            )
        ))
        return "prefs_announcer_watch_users.html", dict(data=dict(
            announcer_watch_users=','.join(attrs)
        ))


class WatchSubscriber(Component):
    """Allows user to subscribe to ticket or wikinotification on a per
    resource basis.  Watch, Unwatch links are added to wiki pages and tickets
    that the user can select to start watching a resource.
    """

    implements(IRequestFilter)
    implements(IRequestHandler)
    implements(IAnnouncementSubscriber)
    implements(ITicketChangeListener)
    implements(IWikiChangeListener)

    watchable_paths = ListOption('announcer', 'watchable_paths',
        'wiki/*,ticket/*',
        doc='List of URL paths to allow watching. Globs are supported.')
    ctxtnav_names = ListOption('announcer', 'ctxtnav_names',
        "Watch This, Unwatch This",
        doc="Text of context navigation entries. "
            "An empty list removes them from the context navigation bar.")

    path_match = re.compile(r'/watch(/.*)')

    # IRequestHandler methods
    def match_request(self, req):
        m = self.path_match.match(req.path_info)
        if m:
            (path_info,) = m.groups()
            realm, _ = self.path_info_to_realm_target(path_info)
            return "%s_VIEW" % realm.upper() in req.perm
        return False

    def process_request(self, req):
        match = self.path_match.match(req.path_info)
        (path_info,) = match.groups()

        realm, target = self.path_info_to_realm_target(path_info)

        req.perm.require('%s_VIEW' % realm.upper())
        self.toggle_watched(req.session.sid, realm, target, req)

        req.redirect(req.href(realm, target))

    def toggle_watched(self, sid, realm, target, req=None):
        if self.is_watching(sid, realm, target):
            self.set_unwatch(sid, realm, target)
            self._schedule_notice(req, _('You are no longer receiving ' \
                    'change notifications about this resource.'))
        else:
            self.set_watch(sid, realm, target)
            self._schedule_notice(req, _('You are now receiving ' \
                    'change notifications about this resource.'))

    def _schedule_notice(self, req, message):
        req.session['_announcer_watch_message_'] = message

    def _add_notice(self, req):
        if '_announcer_watch_message_' in req.session:
            add_notice(req, req.session['_announcer_watch_message_'])
            del req.session['_announcer_watch_message_']

    def is_watching(self, sid, realm, target):
        klass = self.__class__.__name__
        attrs = SubscriptionAttribute.find_by_sid_class_realm_and_target(
                self.env, sid, klass, realm, target)
        if attrs:
            return True
        else:
            return False

    def set_watch(self, sid, realm, target):
        klass = self.__class__.__name__
        SubscriptionAttribute.add(self.env, sid, klass, realm, (target,))

    def set_unwatch(self, sid, realm, target):
        klass = self.__class__.__name__
        (attr,) = SubscriptionAttribute.find_by_sid_class_realm_and_target(
                self.env, sid, klass, realm, target)
        if attr:
            SubscriptionAttribute.delete(self.env, attr['id'])

    # IRequestFilter methods
    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, content_type):
        self._add_notice(req)

        if req.authname != "anonymous":
            for pattern in self.watchable_paths:
                realm, target = self.path_info_to_realm_target(req.path_info)
                if fnmatch('%s/%s'%(realm,target), pattern):
                    if '%s_VIEW'%realm.upper() not in req.perm:
                        return (template, data, content_type)
                    self.render_watcher(req)
                    break
        return (template, data, content_type)

    # Internal methods
    def render_watcher(self, req):
        if not self.ctxtnav_names:
          return
        realm, target = self.path_info_to_realm_target(req.path_info)
        if self.is_watching(req.session.sid, realm, target):
            action_name = len(self.ctxtnav_names) >= 2 and \
                    self.ctxtnav_names[1] or 'Unwatch This'
        else:
            action_name = len(self.ctxtnav_names) and \
                    self.ctxtnav_names[0] or 'Watch This'
        add_ctxtnav(req,
            tag.a(
                _(action_name), href=req.href.watch(realm, target)
            )
        )

    def path_info_to_realm_target(self, path_info):
        realm = target = None
        g = re.match(r'^/([^/]+)(.*)', path_info)
        if g:
            realm, target = g.groups()
            target = target.strip('/')
        return self.normalize_realm_target(realm, target)

    def normalize_realm_target(self, realm, target):
        if not realm:
            realm = 'wiki'
        if not target and realm == 'wiki':
            target = 'WikiStart'

        return realm, target

    # IWikiChangeListener
    def wiki_page_added(*args):
        pass

    def wiki_page_changed(*args):
        pass

    def wiki_page_deleted(self, page):
        klass = self.__class__.__name__
        SubscriptionAttribute.delete_by_class_realm_and_target(
                self.env, klass, 'wiki', page.name)

    def wiki_page_version_deleted(*args):
        pass

    # ITicketChangeListener
    def ticket_created(*args):
        pass

    def ticket_changed(*args):
        pass

    def ticket_deleted(self, ticket):
        klass = self.__class__.__name__
        SubscriptionAttribute.delete_by_class_realm_and_target(
                self.env, klass, 'ticket', page.name)
        db = self.env.get_db_cnx()

    def matches(self, event):
        klass = self.__class__.__name__

        attrs = SubscriptionAttribute.find_by_class_realm_and_target(self.env,
                klass, event.realm, self._get_target_id(event.target))
        sids = set(map(lambda x: x['sid'], attrs))

        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return _("notify me when one of my watched wiki or tickets is updated")

    def _get_target_id(self, target):
        if hasattr(target, 'id'):
            tid = str(target.id)
        elif hasattr(target, 'name'):
            tid = target.name
        else:
            id = str(target)
        return tid

class GeneralWikiSubscriber(Component):
    """Allows users to subscribe to wiki announcements based on a pattern
    that they define.  Any wiki announcements whose page name matches the
    pattern will be recieved by the user.
    """

    implements(IAnnouncementSubscriber)
    implements(IAnnouncementPreferenceProvider)

    def matches(self, event):
        if event.realm != 'wiki':
            return
        if event.category not in ('changed', 'created', 'attachment added',
                'deleted', 'version deleted'):
            return

        klass = self.__class__.__name__

        attrs = SubscriptionAttribute.find_by_class_and_realm(
                self.env, klass, 'wiki')

        def match(pattern):
            for raw in pattern['target'].split(' '):
                if raw != '':
                    pat = urllib.unquote(raw).replace('*', '.*')
                    if re.match(pat, event.target.name):
                        return True

        sids = set(map(lambda x: x['sid'], filter(match, attrs)))

        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()


    def description(self):
        return _("notify me when a wiki that matches my wiki watch pattern "
                 "is created, or updated")

    def get_announcement_preference_boxes(self, req):
        if req.perm.has_permission('WIKI_VIEW'):
            yield "general_wiki", _("General Wiki Announcements")

    def render_announcement_preference_box(self, req, panel):
        klass = self.__class__.__name__

        if req.method == "POST":
            @self.env.with_transaction()
            def do_update(db):
                SubscriptionAttribute.delete_by_sid_and_class(self.env,
                        req.session.sid, klass, db)
                SubscriptionAttribute.add(self.env, req.session.sid, klass,
                    'wiki', req.args.get('wiki_interests', db))

        (interests,) = SubscriptionAttribute.find_by_sid_and_class(
            self.env, req.session.sid, klass) or ({'target':''},)

        return "prefs_announcer_wiki.html", dict(
            wiki_interests = '\n'.join(
                urllib.unquote(x) for x in interests['target'].split(' ')
            )
        )
