# -*- coding: utf-8 -*-
#
# Copyright (c) 2008, Stephen Hansen
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
from trac.util.compat import sorted

from announcer.api import IAnnouncementAddressResolver
from announcer.api import IAnnouncementPreferenceProvider

class SpecifiedEmailResolver(Component):
    implements(IAnnouncementAddressResolver, IAnnouncementPreferenceProvider)
    
    def get_address_for_name(self, name, authenticated):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT value
              FROM session_attribute
             WHERE sid=%s
               AND authenticated=1
               AND name=%s
        """, (name,'announcer_specified_email'))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None    

    # IAnnouncementDistributor
    def get_announcement_preference_boxes(self, req):
        if req.authname != "anonymous":
            yield "emailaddress", "Announcement Email Address"
        
    def render_announcement_preference_box(self, req, panel):
        cfg = self.config
        sess = req.session
        if req.method == "POST":
            opt = req.args.get('specified_email', '')
            sess['announcer_specified_email'] = opt
        specified = sess.get('announcer_specified_email', '')
        data = dict(specified_email = specified,)
        return "prefs_announcer_emailaddress.html", data    
