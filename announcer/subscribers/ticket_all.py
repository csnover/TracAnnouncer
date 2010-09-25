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

class AllTicketSubscriber(Component):
    """Subscriber for all ticket changes."""
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)

    def get_announcement_preference_boxes(self, req):
        yield "tickets", _("Ticket Subscriptions")

    def render_announcement_preference_box(self, req, panel):
        setting = BoolSubscriptionSetting(self.env, "all_tickets")
        if req.method == "POST":
            value = req.args.get('ticket_all', False)
            setting.set_user_setting(req.session, value=value)
        vars = {}
        vars['ticket_all'] = setting.get_user_setting(req.session.sid)[1]
        return "prefs_announcer_ticket_all.html", dict(data=vars)

    def subscriptions(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid
              FROM session_attribute
             WHERE name='sub_all_tickets'
        """)
        for row in cursor.fetchall():
            sid = row[0]
            b = BoolSubscriptionSetting(self.env, 'all_tickets')
            dist, value, authed = b.get_user_setting(sid)
            if value:
                self.log.debug(_("AllTicketSubscriber added '%s" \
                    "'."%sid))
                yield (dist, sid, authed, None, None)

