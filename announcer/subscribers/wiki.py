# -*- coding: utf-8 -*-
#
# Copyright (c) 2008, Stephen Hansen
# Copyright (c) 2009-2010, Robert Corsaro
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

class GeneralWikiSubscriber(Component):
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
        
    def subscriptions(self, event):
        if event.realm == 'wiki':
            if event.category in ('changed', 'created', 'attachment added', 
                    'deleted', 'version deleted'):
                page = event.target
                for name, authenticated in self._get_membership(page.name):
                    yield ('email', name, authenticated, None)
        
    def _get_membership(self, name):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid, authenticated, value
              FROM session_attribute
             WHERE name=%s
        """, ('announcer_wiki_interests', ))
        for sid, authenticated, value in cursor.fetchall():
            for raw in value.split(' '):
                pat = urllib.unquote(raw).replace('*', '.*')
                if re.match(pat, name):
                    self.log.debug(
                        "GeneralWikiSubscriber added '%s (%s)' because name "\
                        "'%s' matches pattern: %s"%(sid, authenticated and \
                        'authenticated' or 'not authenticated', name, pat))
                    yield sid, authenticated
                    
    def get_announcement_preference_boxes(self, req):
        yield "general_wiki", "General Wiki Announcements"
        
    def render_announcement_preference_box(self, req, panel):
        sess = req.session
        if req.method == "POST":
            results = req.args.get('wiki_interests', '')
            if results:
                options = results.splitlines()
                sess['announcer_wiki_interests'] = ' '.join(
                    urllib.quote(x) for x in options
                )
        if 'announcer_wiki_interests' in sess:
            interests = sess['announcer_wiki_interests']
        else:
            interests = ''
        return "prefs_announcer_wiki.html", dict(
            wiki_interests = '\n'.join(
                urllib.unquote(x) for x in interests.split(' ')
            )
        )

