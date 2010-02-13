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

from trac.core import *
from announcer.api import IAnnouncementSubscriptionFilter
from announcer.api import IAnnouncementPreferenceProvider
import re

class ChangeAuthorFilter(Component):
    implements(IAnnouncementSubscriptionFilter)
    implements(IAnnouncementPreferenceProvider)
    
    def filter_subscriptions(self, event, subscriptions):
        for subscription in subscriptions:
            if event.author == subscription[1] and \
                    self._author_filter(event.author):
                self.log.debug(
                    "Filtering %s because of rule: ChangeAuthorFilter"\
                    %event.author
                )
                pass
            else:
                yield subscription

    def _author_filter(self, sid):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT value
              FROM session_attribute
             WHERE sid=%s
               AND name='announcer_author_filter'
        """, (sid,))
        value = cursor.fetchone()
        if value == '0':
            return False
        else:
            # default to true
            return True

    def get_announcement_preference_boxes(self, req):
        if req.authname == 'anonymous' and 'email' not in req.session:
            return
        yield 'author_filter', 'Author Filter'

    def render_announcement_preference_box(self, req, panel):
        if req.method == "POST":
            opt = req.args.get('author_filter')
            self.log.error(req.args)
            if opt == '1':
                req.session["announcer_author_filter"] = '1'
            else:
                req.session["announcer_author_filter"] = '0'
        # default on
        attr = req.session.get('announcer_author_filter', '1')
        opt = attr != '0' and True or None
        return 'prefs_announcer_author_filter.html', \
                dict(data=dict(author_filter=opt))


