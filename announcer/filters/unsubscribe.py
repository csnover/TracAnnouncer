# -*- coding: utf-8 -*-
#
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
from trac.config import BoolOption

from announcer.api import IAnnouncementSubscriptionFilter
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import _

from announcer.util.settings import BoolSubscriptionSetting

class UnsubscribeFilter(Component):
    implements(IAnnouncementSubscriptionFilter, IAnnouncementPreferenceProvider)

    never_announce = BoolOption('announcer', 'never_announce', 'false',
            """Default value for user overridable never_announce setting.

            This setting stops any announcements from ever being sent to the
            user.
            """)
    
    def filter_subscriptions(self, event, subscriptions):
        setting = self._setting()
        for subscription in subscriptions:
            if setting.get_user_setting(subscription[1])[1]:
                self.log.debug(
                    "Filtering %s because of rule: UnsubscribeFilter"\
                    %subscription[1]
                )
                pass
            else:
                yield subscription

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and "email" not in req.session:
            return
        yield "unsubscribe_all", _("Unsubscribe From All Announcements")

    def render_announcement_preference_box(self, req, panel):
        setting = self._setting()
        if req.method == "POST":
            setting.set_user_setting(req.session, 
                    value=req.args.get('unsubscribe_all'))
        value = setting.get_user_setting(req.session.sid)[1]
        return "prefs_announcer_unsubscribe_all.html", \
            dict(data=dict(unsubscribe_all = value))

    def _setting(self):
        return BoolSubscriptionSetting(
            self.env,
            'never_announce',
            self.never_announce
        )
