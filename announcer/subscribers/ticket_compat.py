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

import re

from trac.core import *
from trac.config import BoolOption, Option
from trac.resource import ResourceNotFound
from trac.ticket import model
from trac.util.text import to_unicode
from trac.web.chrome import add_warning

from announcer.api import IAnnouncementSubscriber, istrue
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import _

from announcer.util.settings import BoolSubscriptionSetting

class LegacyTicketSubscriber(Component):
    """Mimics Trac notification settings with added bonus of letting users
    override their settings.  
    """
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
    
    owner = BoolOption("announcer", "always_notify_owner", True,
        """The always_notify_owner option mimics the option of the same name 
        in the notification section, except users can override in their 
        preferences.
        """)

    reporter = BoolOption("announcer", "always_notify_reporter", True, 
        """The always_notify_reporter option mimics the option of the 
        same name in the notification section, except users can override in 
        their preferences.
        """)

    updater = BoolOption("announcer", "always_notify_updater", True, 
        """The always_notify_updater option mimics the option of the 
        same name in the notification section, except users can override in 
        their preferences. 
        """)

    component_owner = BoolOption("announcer", "always_notify_component_owner", 
        True,
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
                        yield subscription
                    
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

class CarbonCopySubscriber(Component):
    """Carbon copy subscriber for cc ticket field."""
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
        
