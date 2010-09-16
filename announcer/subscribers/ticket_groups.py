# -*- coding: utf-8 -*-
#
# Copyright (c) 2008, Stephen Hansen
# Copyright (c) 2009-2010, Robert Corsaro
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

from trac.core import Component, implements
from trac.ticket import model
from trac.web.chrome import add_warning
from trac.config import ListOption

from announcer.api import IAnnouncementSubscriber, istrue
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import _
from announcer.util.settings import BoolSubscriptionSetting

class JoinableGroupSubscriber(Component):
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
    
    joinable_groups = ListOption('announcer', 'joinable_groups', [], 
        doc="""Joinable groups represent 'opt-in' groups that users may 
        freely join. 
        
        Enter a list of groups (without @) seperated by commas.  The name of
        the groups should be a simple alphanumeric string. By adding the group
        name preceeded by @ (such as @sec for the sec group) to the CC field of
        a ticket, everyone in that group will receive an announcement when that
        ticket is changed.
        """)
    
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
                    yield member
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
