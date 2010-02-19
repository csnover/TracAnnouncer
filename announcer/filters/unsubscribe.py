# -*- coding: utf-8 -*-
#
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

from announcer.api import IAnnouncementSubscriptionFilter
from announcer.api import IAnnouncementPreferenceProvider

class UnsubscribeFilter(Component):
    implements(IAnnouncementSubscriptionFilter, IAnnouncementPreferenceProvider)
    
    def filter_subscriptions(self, event, subscriptions):
        unsubscribed = list(self._unsubscribed())
        for subscription in subscriptions:
            if subscription[1] in unsubscribed:
                self.log.debug(
                    "Filtering %s because of rule: UnsubscribeFilter"\
                    %subscription[1]
                )
                pass
            else:
                yield subscription

    def _unsubscribed(self):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid
              FROM session_attribute
             WHERE name=%s
               AND value=1
        """, ('announcer_unsubscribe_all',))
        for result in cursor.fetchall():
            yield result[0]
        
    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and "email" not in req.session:
            return
        yield "unsubscribe_all", "Unsubscribe From All Announcements"

    def render_announcement_preference_box(self, req, panel):
        if req.method == "POST":
            opt = req.args.get('unsubscribe_all')
            if opt:
                req.session['announcer_unsubscribe_all'] = '1'
            else:
                req.session['announcer_unsubscribe_all'] = '0'
        attr = req.session.get('announcer_unsubscribe_all') 
        opt = attr == '1' and True or None
        return "prefs_announcer_unsubscribe_all.html", \
            dict(data=dict(unsubscribe_all = opt))
