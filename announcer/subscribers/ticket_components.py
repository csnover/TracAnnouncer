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

from trac.core import Component, implements
from announcer.api import IAnnouncementSubscriber, istrue
from announcer.api import IAnnouncementPreferenceProvider
from trac.ticket import model
from trac.web.chrome import add_warning
from trac.config import ListOption
import re

class TicketComponentSubscriber(Component):
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
    
    def get_subscription_realms(self):
        return ('ticket',)
    
    def get_subscription_categories(self, realm):
        if realm == "ticket":
            return('changed', 'created', 'attachment added')
        else:
            ()
    
    def get_subscriptions_for_event(self, event):
        if event.realm == 'ticket':
            ticket = event.target
            if event.category in ('changed', 'created', 'attachment added'):
                for subscriber in self._get_membership(ticket['component']):
                    self.log.debug("TicketComponentSubscriber added '%s " \
                            "(%s)' for component '%s'"%(
                            subscriber[1], subscriber[2], ticket['component']))
                    yield subscriber

    def _get_membership(self, component):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid, authenticated
              FROM session_attribute 
             WHERE name=%s
               AND value=%s
        """, ('announcer_joinable_component_' + component, "1"))
        for result in cursor.fetchall():
            if result[1] in (1, '1', True):
                authenticated = True
            else:
                authenticated = False
            yield ("email", result[0], authenticated, None)

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "joinable_components", "Ticket Component Subscriptions"
        
    def render_announcement_preference_box(self, req, panel):
        cfg = self.config
        sess = req.session
        if req.method == "POST":
            for component in model.Component.select(self.env):
                component_opt = 'joinable_component_%s' % component.name
                result = req.args.get(component_opt, None)
                if result:
                    sess["announcer_" + component_opt] = '1'
                else:                    
                    if "announcer_" + component_opt in sess:
                        del sess["announcer_" + component_opt]
        components = {}
        for component in model.Component.select(self.env):
            components[component.name] = sess.get(
                    'announcer_joinable_component_%s' % component.name, None)
        data = dict(joinable_components = components)
        return "prefs_announcer_joinable_components.html", data

