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
from announcer.api import IAnnouncementFormatter
from trac.config import Option, IntOption, BoolOption
from genshi.template import NewTextTemplate, MarkupTemplate
from genshi import HTML
from trac.web.href import Href
from trac.web.chrome import Chrome
from trac.wiki.model import WikiPage
from genshi.template import TemplateLoader
from trac.util.text import wrap
from trac.versioncontrol.diff import diff_blocks, unified_diff
import difflib

def diff_cleanup(gen):
    for value in gen:
        if value.startswith('---'):
            continue
        if value.startswith('+++'):
            continue
        if value.startswith('@@'):
            yield '\n'
        else:
            yield value

def lineup(gen):
    for value in gen:
        yield ' ' + value

diff_header = """Index: %(name)s
==============================================================================
--- %(name)s (version: %(oldversion)s)
+++ %(name)s (version: %(version)s)
"""

class WikiFormatter(Component):
    implements(IAnnouncementFormatter)
        
    wiki_email_diff = BoolOption('announcer', 'wiki_email_diff', 
            "true",
            """Should a wiki diff be sent with emails?""")

    def styles(self, transport, realm):
        if realm == "wiki":
            yield "text/plain"
        
    def alternative_style_for(self, transport, realm, style):
        if realm == "wiki" and style != "text/plain":
            return "text/plain"
        
    def format(self, transport, realm, style, event):
        if realm == "wiki" and style == "text/plain":
            return self._format_plaintext(event)

    def _format_plaintext(self, event):
        page = event.target
        data = dict(
            action = event.category,
            attachment = event.attachment,
            page = page,
            author = event.author,
            comment = event.comment,
            category = event.category,
            page_link = self.env.abs_href('wiki', page.name),
            project_name = self.env.project_name,
            project_desc = self.env.project_description,
            project_link = self.env.project_url or self.env.abs_href(),
        )
        old_page = WikiPage(self.env, page.name, page.version - 1)
        if page.version:
            data["changed"] = True
            data["diff_link"] = self.env.abs_href('wiki', page.name, 
                    action="diff", version=page.version)
            if self.wiki_email_diff:
                diff = "\n"
                diff += diff_header % { 'name': page.name,
                                       'version': page.version,
                                       'oldversion': page.version - 1
                                     }
                for line in unified_diff(old_page.text.splitlines(),
                                         page.text.splitlines(), context=3):
                    diff += "%s\n" % line
                data["diff"] = diff
        chrome = Chrome(self.env)        
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()
        templates = TemplateLoader(dirs, variable_lookup='lenient')
        template = templates.load('wiki_email_plaintext.txt', 
                cls=NewTextTemplate)
        if template:
            stream = template.generate(**data)
            output = stream.render('text')
        return output
        
