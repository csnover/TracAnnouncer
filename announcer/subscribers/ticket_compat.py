# -*- coding: utf-8 -*-
#
# Copyright (c) 2008, Stephen Hansen
# Copyright (c) 2009, Robert Corsaro
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

import re

from trac.core import *
from trac.config import BoolOption, Option
from trac.resource import ResourceNotFound
from trac.ticket import model
from trac.util.text import to_unicode
from trac.util.translation import _
from trac.web.chrome import add_warning

from announcer.api import IAnnouncementSubscriber, istrue
from announcer.api import IAnnouncementPreferenceProvider

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
                val = val and '1' or '0'
                req.session['announcer_legacy_notify_%s'%attr] = val

        # component
        component = req.session.get('announcer_legacy_notify_component_owner')
        if component is None:
            component = self.always_notify_component_owner
        else:
            component = component == u'1'

        # owner
        owner = req.session.get('announcer_legacy_notify_owner')
        if owner is None:
            owner = self.always_notify_owner
        else:
            owner = owner == u'1'

        # reporter
        reporter = req.session.get('announcer_legacy_notify_reporter')
        if reporter is None:
            reporter = self.always_notify_reporter
        else:
            reporter = reporter == u'1'

        # updater
        updater = req.session.get('announcer_legacy_notify_updater')
        if updater is None:
            updater = self.always_notify_updater
        else:
            updater = updater == u'1'

        return "prefs_announcer_legacy.html", dict(
            data=dict(
                component=component,
                owner=owner,
                reporter=reporter,
                updater=updater
            )    
        )

    def subscriptions(self, event):
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
            return result[0] == '1'
        return None

class CarbonCopySubscriber(Component):
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
                        yield ('email', name, name and True or False, address)
        
