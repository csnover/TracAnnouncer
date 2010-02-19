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

from trac.core import Component, implements
from trac.ticket import model
from trac.web.chrome import add_warning
from trac.config import ListOption

from announcer.api import IAnnouncementSubscriber, istrue
from announcer.api import IAnnouncementPreferenceProvider

class UserChangeSubscriber(Component):
    """Allows users to get notified anytime a particular user change or 
    modifies a ticket or wiki page."""
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)

    def subscriptions(self, event):
        if event.realm in ('wiki', 'ticket'):
            if event.category in ('changed', 'created', 'attachment added'):
                for sub in self._get_membership(event.author):
                    yield sub

    def _get_membership(self, author):
        """Check the user's selection.  None means 
        they haven't selected ."""
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid, authenticated, value
              FROM session_attribute
             WHERE name='announcer_watch_users'
        """)
        for result in cursor.fetchall():
            for name in result[2].split(','):
                if name.strip() == author:
                    name, authenticated = result[0], result[1]
                    self.log.debug("UserChangeSubscriber added '%s'"%name)
                    yield ('email', name, authenticated, None)

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymouse" and 'email' not in req.session:
            return
        yield "watch_users", "Watch Users"

    def render_announcement_preference_box(self, req, panel):
        if req.method == "POST":
            names = req.args.get("announcer_watch_users")
            if names:
                req.session['announcer_watch_users'] = names
            elif req.session.get('announcer_watch_users'):
                del req.session['announcer_watch_users']
        return "prefs_announcer_watch_users.html", dict(data=dict(
            announcer_watch_users=req.session.get('announcer_watch_users', '')
        ))
