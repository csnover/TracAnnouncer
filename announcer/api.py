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
"""
TracAnnouncer is a flexible trac notifications drop in replacement that is
very flexible and customizable.  There is a focus on users being able to
configure what notifications they would like and relieving the sysadmin
from having to manage notifications.

HACKING NOTES:

The most confusing part of announce is that subscriptions have three
related fields, that are not intuitive.  (sid, authenticated, address).
There is a very good reason for this.  First, Trac users are identified
throughout the system with the sid, authenticated pair.  Anonymous user
are allowed to set their sid to anything that they would like via the
advanced preferences in the preferences section of the site.  The can
set their sid to the same sid as some authenticated user.  The way we
tell the difference between the two identical sids is the authenticated
flag.  There is a third type of user when we are talking about announcements.
Users can enter any email address in some ticket fields, like CC.  These
subscriptions are not associated with any sid.  So the sid and authenticated
in the subscription would be None, None.  These users should be treated
with all default configuration and permissions checked against anonymous.
I hope this helps, because it took me a while to wrap my head around :P
"""

import pkg_resources
import time

from operator import itemgetter

from trac.config import ExtensionOption
from trac.core import *
from trac.db import Table, Column, Index
from trac.db import DatabaseManager
from trac.env import IEnvironmentSetupParticipant
from trac.util.compat import set


class IAnnouncementProducer(Interface):
    """Producer converts Trac events from different subsystems, into
    AnnouncerEvents.
    """

    def realms():
        """Returns an iterable that lists all the realms that this producer
        is capable of producing events for.
        """


class IAnnouncementSubscriber(Interface):
    """IAnnouncementSubscriber provides an interface where a Plug-In can
    register realms and categories of subscriptions it is able to provide.

    An IAnnouncementSubscriber component can use any means to determine
    if a user is interested in hearing about a given event. More then one
    component can handle the same realms and categories.

    The subscriber must also indicate not just that a user is interested
    in receiving a particular notice. Again, how it makes that decision is
    entirely up to a particular implementation."""

    def matches(event):
        """Returns a list of subscriptions that match the given event.
        Responses should be yielded as 7 part tuples as follows:
        (distributor, sid, authenticated, address, format, priority, adverb)
        The default installation includes email and xmpp distributors.  The
        default installation includes formats for text/plain and text/html.
        If an unknown format is return, it will be replaced by a default known
        format.  Priority is used to resolve conflicting subscriptions for the
        same user/distribution pair.  adverb is either always or never.
        """

    def description():
        """A description of the subscription that shows up in the users
        preferences.
        """

    def requires_authentication():
        """Returns True or False.  If the user is required to be authenticated
        to create the subscription, then return True.  This applies to things
        like ticket owner subscriber, since the ticket owner can never be the
        sid of an unauthenticated user and we have no way to lookup users by
        email address (as of yet).
        """


class IAnnouncementDefaultSubscriber(Interface):
    """Default subscriptions that the module will automatically generate.
    This should only be used in reasonable situations, where users can be
    determined by the event itself.  For instance, ticket author has a
    default subscription that is controlled via trac.ini.  This is because
    we can lookup the ticket author during the event and create a
    subscription for them.  Default subscriptions should be low priority
    so that the user can easily override them.
    """

    def default_subscriptions():
        """Yields 5 part tuple containing (class, distributor, priority,
        adverb).  This is used to display default subscriptions in the
        user UI and can also be used by matches to figure out what
        default subscriptions it should yield.
        """


class IAnnouncementSubscriptionFilter(Interface):
    """IAnnouncementSubscriptionFilter provides an interface where a component
    can filter subscribers from the final distribution list.
    """

    def filter_subscriptions(event, subscriptions):
        """Returns a filtered iterator of subscriptions.  This method is called
        after all get_subscriptions_for_event calls are made to allow
        components to remove addresses from the distribution list.  This can
        be used for things like "never notify updater" functionality.
        """


class IAnnouncementFormatter(Interface):
    """Formatters are responsible for converting an event into a message
    appropriate for a given transport.

    For transports like 'aim' or 'irc', this may be a short summary of a
    change. For 'email', it may be a plaintext or html overview of all
    the changes and perhaps the existing state.

    It's up to a formatter to determine what ends up ultimately being sent
    to the end-user. It's capable of pulling data out of the target object
    that wasn't changed, picking and choosing details for whatever reason.

    Since a formatter must be intimately familiar with the realm that
    originated the event, formatters are tied to specific transport + realm
    combinations. This means there may be a proliferation of formatters as
    options expand.
    """

    def format_styles(transport, realm):
        """Returns an iterable of styles that this formatter supports for
        a specified transport and realm.

        Many formatters may simply return a single style and never have more;
        that's fine. But if its useful to encapsulate code for several similar
        styles a formatter can handle more then one. For example, 'text/plain'
        and 'text/html' may be useful variants the same formatter handles.

        Formatters retain the ability to descriminate by transport, but don't
        need to.
        """

    def alternative_style_for(transport, realm, style):
        """Returns an alternative style for the given style if one is
        available.
        """

    def format(transport, realm, style, event):
        """Converts the event into the specified style. If the transport or
        realm passed into this method are not ones this formatter can handle,
        it should return silently and without error.

        The exact return type of this method is intentionally undefined. It
        will be whatever the distributor that it is designed to work with
        expects.
        """


class IAnnouncementDistributor(Interface):
    """The Distributor is responsible for actually delivering an event to the
    desired subscriptions.

    A distributor should attempt to avoid blocking; using subprocesses is
    preferred to threads.

    Each distributor handles a single transport, and only one distributor
    in the system should handle that. For example, there should not be
    two distributors for the 'email' transport.
    """

    def transports():
        """Returns an iter of the transport supported."""

    def distribute(transport, recipients, event):
        """This method is meant to actually distribute the event to the
        specified recipients, over the specified transport.

        If it is passed a transport it does not support, it should return
        silently and without error.

        The recipients is a list of (name, address) pairs with either (but not
        both) being allowed to be None. If name is provided but address isn't,
        then the distributor should defer to IAnnouncementAddressResolver
        implementations to determine what the address should be.

        If the name is None but the address is not, then the distributor
        should rely on the address being correct and use it-- if possible.

        The distributor may initiate as many transactions as are necessecary
        to deliver a message, but should use as few as possible; for example
        in the EmailDistributor, if all of the recipients are receiving a
        plain text form of the message, a single message with many BCC's
        should be used.

        The distributor is responsible for determining which of the
        IAnnouncementFormatters should get the privilege of actually turning
        an event into content. In cases where multiple formatters are capable
        of converting an event into a message for a given transport, a
        user preference would be a dandy idea.
        """


class IAnnouncementPreferenceProvider(Interface):
    """Represents a single 'box' in the Announcements preference panel.

    Any component can always implement IPreferencePanelProvider to get
    preferences from users, of course. However, considering there may be
    several components related to the Announcement system, and many may
    have different preferences for a user to set, that would clutter up
    the preference interfac quite a bit.

    The IAnnouncementPreferenceProvider allows several boxes to be
    chained in the same panel to group the preferenecs related to the
    Announcement System.

    Implementing announcement preference boxes should be essentially
    identical to implementing entire panels.
    """

    def get_announcement_preference_boxes(req):
        """Accepts a request object, and returns an iterable of
        (name, label) pairs; one for each box that the implementation
        can generate.

        If a single item is returned, be sure to 'yield' it instead of
        returning it."""

    def render_announcement_preference_box(req, box):
        """Accepts a request object, and the name (as from the previous
        method) of the box that should be rendered.

        Returns a tuple of (template, data) with the template being a
        filename in a directory provided by an ITemplateProvider which
        shall be rendered into a single <div> element, when combined
        with the data member.
        """


class IAnnouncementAddressResolver(Interface):
    """Handles mapping Trac usernames to addresses for distributors to use."""

    def get_address_for_name(name, authenticated):
        """Accepts a session name, and returns an address.

        This address explicitly does not always have to mean an email address,
        nor does it have to be an address stored within the Trac system at
        all.

        Implementations of this interface are never 'detected' automatically,
        and must instead be specifically named for a particular distributor.
        This way, some may find email addresses (for EmailDistributor), and
        others may find AIM screen name.

        If no address for the specified name can be found, None should be
        returned. The next resolver will be attempted in the chain.
        """


class AnnouncementEvent(object):
    """AnnouncementEvent

    This packages together in a single place all data related to a particular
    event; notably the realm, category, and the target that represents the
    initiator of the event.

    In some (rare) cases, the target may be None; in cases where the message
    is all that matters and there's no possible data you could conceivably
    get beyond just the message.
    """
    def __init__(self, realm, category, target, author=""):
        self.realm = realm
        self.category = category
        self.target = target
        self.author = author

    def get_basic_terms(self):
        return (self.realm, self.category)

    def get_session_terms(self, session_id):
        return tuple()


class IAnnouncementSubscriptionResolver(Interface):
    """Supports new and old style of subscription resolution until new code
    is complete."""

    def subscriptions(event):
        """Return all subscriptions as (dist, sid, auth, address, format)
        priority 1 is highest.  adverb is 'always' or 'never'.
        """


class SubscriptionResolver(Component):
    """Collect, and resolve subscriptions."""

    implements(IAnnouncementSubscriptionResolver)

    subscribers = ExtensionPoint(IAnnouncementSubscriber)

    def subscriptions(self, event):
        """Yields all subscriptions for a given event."""

        subscriptions = []
        for sp in self.subscribers:
            subscriptions.extend(
                [x for x in sp.matches(event) if x]
            )

        """
        This logic is meant to generate a list of subscriptions for each
        distirbution method.  The important thing is that we pick the rule with
        the highest priority for each (sid, distribution) pair.  If it is
        "never", then the user is dropped from the list.  If it is always, then
        the user is kept.  Only the users highest priority rule is used and all
        others are skipped.
        """
        # sort by dist, sid, authenticated, priority
        ordered_subs = sorted(subscriptions, key=itemgetter(1,2,3,6))

        resolved_subs = []

        # collect highest priority for each (sid, dist) pair
        state = {
            'last': None
        }
        for s in ordered_subs:
            if (s[1], s[2], s[3]) == state['last']:
                continue
            if s[-1] == 'always':
                self.log.debug("Adding (%s [%s]) for 'always' on rule (%s) "
                    "for (%s)"%(s[2], s[3], s[0], s[1]))
                resolved_subs.append(s[1:6])
            else:
                self.log.debug("Ignoring (%s [%s]) for 'never' on rule (%s) "
                    "for (%s)"%(s[2], s[3], s[0], s[1]))

            # if s[1] is None, then the subscription is for a raw email
            # address that has been set in some field and we shouldn't skip
            # the next raw email subscription.  In other words, all raw email
            # subscriptions should be added.
            if s[2]:
                state['last'] = (s[1], s[2], s[3])

        return resolved_subs


_TRUE_VALUES = ('yes', 'true', 'enabled', 'on', 'aye', '1', 1, True)

def istrue(value, otherwise=False):
    return True and (value in _TRUE_VALUES) or otherwise


try:
    from trac.util.translation import domain_functions

    _, tag_, N_, add_domain = \
        domain_functions('announcer', ('_', 'tag_', 'N_', 'add_domain'))

except ImportError:
    # fall back to 0.11 behavior, i18n functions are no-ops then
    def add_domain():
        pass

    _ = N_ = tag_ = _noop = lambda string: string
    pass


class AnnouncementSystem(Component):
    """AnnouncementSystem represents the entry-point into the announcement
    system, and is also the central controller that handles passing notices
    around.

    An announcement begins when something-- an announcement provider--
    constructs an AnnouncementEvent (or subclass) and calls the send method
    on the AnnouncementSystem.

    Every event is classified by two required fields-- realm and category.
    In general, the realm corresponds to the realm of a Resource within Trac;
    ticket, wiki, milestone, and such. This is not a requirement, however.
    Realms can be anything distinctive-- if you specify novel realms to solve
    a particular problem, you'll simply also have to specify subscribers and
    formatters who are able to deal with data in those realms.

    The other classifier is a category that is defined by the providers and
    has no particular meaning; for the providers that implement the
    I*ChangeListener interfaces, the categories will often correspond to the
    kinds of events they receive. For tickets, they would be 'created',
    'changed' and 'deleted'.

    There is no requirement for an event to have more then realm and category
    to classify an event, but if more is provided in a subclass that the
    subscribers can use to pick through events, all power to you.
    """

    implements(IEnvironmentSetupParticipant)

    subscribers = ExtensionPoint(IAnnouncementSubscriber)
    subscription_filters = ExtensionPoint(IAnnouncementSubscriptionFilter)
    subscription_resolvers = ExtensionPoint(IAnnouncementSubscriptionResolver)
    distributors = ExtensionPoint(IAnnouncementDistributor)

    resolver = ExtensionOption('announcer', 'subscription_resolvers',
        IAnnouncementSubscriptionResolver, 'SubscriptionResolver',
        """Comma seperated list of subscription resolver components in the
        order they will be called.
        """)



    # IEnvironmentSetupParticipant implementation
    """Subscriptions table will is deprecated in favor of the new
    subscriber interface.

    TODO: We still need to create an upgrade script that will port
    subscriptions from the subscription table and the session_attribute
    table to the subscription_attribute table.
    """
    SCHEMA = [
        Table('subscription', key='id')[
            Column('id', auto_increment=True),
            Column('time', type='int64'),
            Column('changetime', type='int64'),
            Column('class'),
            Column('sid'),
            Column('authenticated', type='int'),
            Column('distributor'),
            Column('format'),
            Column('priority', type='int'),
            Column('adverb')
        ],
        Table('subscription_attribute', key='id')[
            Column('id', auto_increment=True),
            Column('sid'),
            Column('authenticated', type='int'),
            Column('class'),
            Column('realm'),
            Column('target')
        ]
    ]

    def __init__(self):
        # bind the 'announcer' catalog to the locale directory
        locale_dir = pkg_resources.resource_filename(__name__, 'locale')
        add_domain(self.env.path, locale_dir)

    def environment_created(self):
        self._upgrade_db(self.env.get_db_cnx())

    def environment_needs_upgrade(self, db):
        cursor = db.cursor()
        for table in self.SCHEMA:
            try:
                cursor.execute("select count(*) from %s"%table.name)
                cursor.fetchone()
            except:
                db.rollback()
                return True
        return False

    def upgrade_environment(self, db):
        self._upgrade_db(db)

    def _upgrade_db(self, db):
        try:
            db_backend, _ = DatabaseManager(self.env)._get_connector()
            for table in self.SCHEMA:
                try:
                    cursor = db.cursor()
                    cursor.execute("select count(*) from %s"%table.name)
                    cursor.fetchone()
                except:
                    db.rollback()
                    cursor = db.cursor()
                    for stmt in db_backend.to_sql(table):
                        self.log.debug(stmt)
                        cursor.execute(stmt)
                        db.commit()
        except Exception, e:
            db.rollback()
            self.log.error(e, exc_info=True)
            raise TracError(str(e))
    # The actual AnnouncementSystem now..

    def send(self, evt):
        start = time.time()
        self._real_send(evt)
        stop = time.time()
        self.log.debug("AnnouncementSystem sent event in %s seconds."\
                %(round(stop-start,2)))

    def _real_send(self, evt):
        """Accepts a single AnnouncementEvent instance (or subclass), and
        returns nothing.

        There is no way (intentionally) to determine what the
        AnnouncementSystem did with a particular event besides looking through
        the debug logs.
        """
        try:
            subscriptions = self.resolver.subscriptions(evt)
            for sf in self.subscription_filters:
                subscriptions = set(
                    sf.filter_subscriptions(evt, subscriptions)
            )

            self.log.debug(
                "AnnouncementSystem has found the following subscriptions: " \
                        "%s"%(', '.join(['[%s(%s) via %s]' % ((s[1] or s[3]),\
                        s[2] and 'authenticated' or 'not authenticated',s[0])\
                        for s in subscriptions]
                    )
                )
            )
            packages = {}
            for transport, sid, authenticated, address, subs_format \
                    in subscriptions:
                if transport not in packages:
                    packages[transport] = set()
                packages[transport].add((sid,authenticated,address))
            for distributor in self.distributors:
                for transport in distributor.transports():
                    if transport in packages:
                        distributor.distribute(transport, packages[transport],
                                evt)
        except:
            self.log.error("AnnouncementSystem failed.", exc_info=True)

