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

from trac.core import Component, implements, TracError
from trac.web.chrome import add_stylesheet

from announcer.api import IAnnouncementSubscriber
from announcer.api import INewAnnouncementSubscriber
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import _
from announcer.query import *

class RuleBasedTicketSubscriber(Component):
    
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
    
    # IAnnouncementSubscriber
    def subscriptions(self, event):
        terms = self._get_basic_terms(event)
        db = self.env.get_db_ctx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT id, sid, authenticated, rule
              FROM subscriptions
             WHERE enabled=1 AND managed=''
               AND realm=%s
               AND category=%s
        """, (event.realm, event.category))
        for rule_id, session_id, authenticated, rule in cursor.fetchall():
            query = Query(rule)
            print "For", session_id, "Rule:", rule
            if query(terms + self._get_session_terms(session_id, event)):
                print True
            else:
                print False

    def _get_basic_terms(self, event):
        terms = [event.realm, event.category]
        try:
            terms.extend(event.get_basic_terms())
        except:
            pass
        print "Basic terms", terms
        return terms
        
    def _get_session_terms(self, session_id, event):
        terms = []
        try:
            terms.extend(event.get_session_terms(session_id))
        except:
            pass
        print "Session terms", terms
        return terms
        
    # IAnnouncementPreferenceProvider
    def get_announcement_preference_boxes(self, req):
        yield ('rules', _('Rule-based subscriptions'))
        
    def render_announcement_preference_box(self, req, box):
        add_stylesheet(req, 'announcer/css/rulediv.css')
        categories = {
            'ticket': ('created', 'changed', 'attachment added', 'deleted'),
            'wiki': ('created', 'changed', 'attachment added', 'deleted')
        }
        rules = [
            dict(
                id=1,
                enabled=True,
                realm="ticket",
                category="changed",
                value="this or that",
            ),
            dict(
                id=3,
                enabled=False,
                realm="wiki",
                category="created",
                value="this or that",
            ),
            dict(
                id=5,
                enabled=True,
                realm="ticket",
                category="changed",
                value="this or that",
            ),
        ]
        data = dict(
            categories=categories,
            rules=rules,
        )
        return "prefs_announcer_rules.html", data 
