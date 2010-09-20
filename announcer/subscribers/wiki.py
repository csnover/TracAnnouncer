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
import re, urllib

from trac.config import ListOption
from trac.core import Component, implements
from trac.ticket import model
from trac.web.chrome import add_warning

from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import IAnnouncementSubscriber, istrue
from announcer.api import _
from announcer.util.settings import SubscriptionSetting

class GeneralWikiSubscriber(Component):
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)

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
            yield result

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
