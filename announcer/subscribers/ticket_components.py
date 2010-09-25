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

from trac.core import Component, implements
from trac.ticket import model
from trac.web.chrome import add_warning
from trac.config import ListOption

from announcer.api import IAnnouncementSubscriber, istrue
from announcer.api import INewAnnouncementSubscriber
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import _
from announcer.model import Subscription

from announcer.util.settings import BoolSubscriptionSetting

class TicketComponentSubscriber(Component):
    implements(IAnnouncementSubscriber)
    implements(INewAnnouncementSubscriber)
    implements(IAnnouncementPreferenceProvider)

    def subscriptions(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return
        settings = self._settings()
        setting = settings.get(event.target['component'])
        if setting:
            for result in setting.get_subscriptions():
                self.log.debug("TicketComponentSubscriber added '%s " \
                        "(%s)' for component '%s'"%(
                        result[1], result[2], event.target['component']))
                yield result + (None,)

    def new_subscriptions(self, event):
        if event.realm != 'ticket':
            return
        if event.category not in ('changed', 'created', 'attachment added'):
            return

        component = event.target['component']
        if not component:
            return

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid
              FROM subscription_attribute
             WHERE value=%s
               AND class=%s
        """, (component,self.__class__.__name__))
        sids = map(lambda x: x[0], cursor.fetchall())

        klass = self.__class__.__name__
        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return "notify me when a ticket associated with a component I'm watching changes"

    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "joinable_components", _("Ticket Component Subscriptions")

    def render_announcement_preference_box(self, req, panel):
        settings = self._settings()
        if req.method == "POST":
            for attr, setting in settings.items():
                setting.set_user_setting(req.session, 
                    value=req.args.get('component_%s'%attr), save=False)
            req.session.save()
            @self.env.with_transaction()
            def update(db):
                cursor = db.cursor()
                cursor.execute("""
                DELETE FROM subscription_attribute
                      WHERE sid = %s
                        AND class = %s
                """, (req.session.sid,self.__class__.__name__))
                for i in req.args.keys():
                    g = re.match('^component_(.*)', i)
                    if g:
                        if istrue(req.args.get(i)):
                            cursor.execute("""
                            INSERT INTO subscription_attribute
                                        (sid, class, value)
                                 VALUES (%s, %s, %s)
                            """, (req.session.sid,
                                self.__class__.__name__, g.groups()[0]))

        d = {}
        for attr, setting in settings.items():
            d[attr]= setting.get_user_setting(req.session.sid)[1]
        return "prefs_announcer_joinable_components.html", dict(components=d)

    def _settings(self):
        settings = {}
        for component in model.Component.select(self.env):
            settings[component.name] = BoolSubscriptionSetting(
                self.env,
                'component_%s'%component.name
            )
        return settings

