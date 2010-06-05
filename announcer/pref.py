# -*- coding: utf-8 -*-
#
# Copyright (c) 2008, Stephen Hansen
# Copyright (c) 2009, Robert Corsaro
# Copyright (c) 2010, Robert Corsaro
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

from trac.core import Component, implements, ExtensionPoint
from trac.prefs.api import IPreferencePanelProvider
from trac.web.chrome import ITemplateProvider, add_stylesheet, Chrome
from trac.web import IRequestHandler

from pkg_resources import resource_filename

from announcer.api import IAnnouncementPreferenceProvider, \
                          _, tag_, N_

def truth(v):
    if v in (False, 'False', 'false', 0, '0', ''):
        return None
    return True

class AnnouncerPreferences(Component):
    implements(IPreferencePanelProvider, ITemplateProvider)
    
    preference_boxes = ExtensionPoint(IAnnouncementPreferenceProvider)
    
    def get_htdocs_dirs(self):
        return [('announcer', resource_filename(__name__, 'htdocs'))]

    def get_templates_dirs(self):
        resource_dir = resource_filename(__name__, 'templates')
        return [resource_dir]
        
    def get_preference_panels(self, req):
        yield ('announcer', 'Announcements')
        
    def _get_boxes(self, req):
        for pr in self.preference_boxes:
            boxes = pr.get_announcement_preference_boxes(req)
            boxdata = {}
            if boxes:
                for boxname, boxlabel in boxes:
                    if boxname == 'general_wiki' and not req.perm.has_permission('WIKI_VIEW'):
                        continue
                    if (boxname == 'legacy' or boxname == 'joinable_groups') and not req.perm.has_permission('TICKET_VIEW'):
                        continue
                    yield ((boxname, boxlabel) + 
                        pr.render_announcement_preference_box(req, boxname))

    def render_preference_panel(self, req, panel, path_info=None):
        streams = []
        chrome = Chrome(self.env)
        for name, label, template, data in self._get_boxes(req):
            streams.append((label, chrome.render_template(
                req, template, data, content_type='text/html', fragment=True
            )))
        add_stylesheet(req, 'announcer/css/announcer_prefs.css')
        return 'prefs_announcer.html', {"boxes": streams}
        
        
