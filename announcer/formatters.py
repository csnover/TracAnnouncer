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

import difflib

from genshi import HTML
from genshi.template import NewTextTemplate, MarkupTemplate, TemplateLoader

from trac.config import Option, IntOption, ListOption, BoolOption
from trac.core import *
from trac.mimeview import Context
from trac.test import Mock, MockPerm
from trac.ticket.api import TicketSystem
from trac.util.text import wrap, to_unicode
from trac.versioncontrol.diff import diff_blocks, unified_diff
from trac.web.chrome import Chrome
from trac.web.href import Href
from trac.wiki.formatter import HtmlFormatter
from trac.wiki.model import WikiPage

from announcer.api import IAnnouncementFormatter
from announcer.util.mail import exception_to_unicode


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

class TicketFormatter(Component):
    implements(IAnnouncementFormatter)

    ticket_email_header_fields = ListOption('announcer',
            'ticket_email_header_fields',
            'owner, reporter, milestone, priority, severity',
            doc="""Comma seperated list of fields to appear in tickets.
            Use * to include all headers.""")

    ticket_link_with_comment = BoolOption('announcer',
            'ticket_link_with_comment',
            'false',
            """Include last change anchor to the ticket URL.""")

    def styles(self, transport, realm):
        if realm == "ticket":
            yield "text/plain"
            yield "text/html"

    def alternative_style_for(self, transport, realm, style):
        if realm == "ticket" and style != 'text/plain':
            return "text/plain"

    def format(self, transport, realm, style, event):
        if realm == "ticket":
            if style == "text/plain":
                return self._format_plaintext(event)
            elif style == "text/html":
                return self._format_html(event)

    def _ticket_link(self, ticket):
        ticket_link = self.env.abs_href('ticket', ticket.id)
        if self.ticket_link_with_comment == False:
            return ticket_link

        cnum = self._ticket_last_comment(ticket)
        if cnum != None:
            ticket_link += "#comment:%s" % str(cnum)

        return ticket_link

    def _ticket_last_comment(self, ticket):
        cnum = -1

        for entry in ticket.get_changelog():
            (time, author, field, oldvalue, newvalue, permanent) = entry
            if field != "comment":
                continue

            try:
                n = int(oldvalue)
            except:
                continue

            if cnum < n:
                cnum = n

        if cnum == -1:
            return None
        else:
            return cnum

    def _format_plaintext(self, event):
        ticket = event.target
        short_changes = {}
        long_changes = {}
        changed_items = [(field, to_unicode(old_value)) for \
                field, old_value in event.changes.items()]
        for field, old_value in changed_items:
            new_value = to_unicode(ticket[field])
            if ('\n' in new_value) or ('\n' in old_value):
                long_changes[field.capitalize()] = '\n'.join(
                    lineup(wrap(new_value, cols=67).split('\n')))
            else:
                short_changes[field.capitalize()] = (old_value, new_value)

        data = dict(
            ticket = ticket,
            author = event.author,
            comment = event.comment,
            fields = self._header_fields(ticket),
            category = event.category,
            ticket_link = self._ticket_link(ticket),
            project_name = self.env.project_name,
            project_desc = self.env.project_description,
            project_link = self.env.project_url or self.env.abs_href(),
            has_changes = short_changes or long_changes,
            long_changes = long_changes,
            short_changes = short_changes,
            attachment= event.attachment
        )
        chrome = Chrome(self.env)
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()
        templates = TemplateLoader(dirs, variable_lookup='lenient')
        template = templates.load('ticket_email_plaintext.txt',
                cls=NewTextTemplate)
        if template:
            stream = template.generate(**data)
            output = stream.render('text')
        return output

    def _header_fields(self, ticket):
        headers = self.ticket_email_header_fields
        fields = TicketSystem(self.env).get_ticket_fields()
        if len(headers) and headers[0].strip() != '*':
            def _filter(i):
                return i['name'] in headers
            fields = filter(_filter, fields)
        return fields

    def _format_html(self, event):
        ticket = event.target
        short_changes = {}
        long_changes = {}
        chrome = Chrome(self.env)
        for field, old_value in event.changes.items():
            new_value = ticket[field]
            if (new_value and '\n' in new_value) or \
                    (old_value and '\n' in old_value):
                long_changes[field.capitalize()] = HTML(
                    "<pre>\n%s\n</pre>" % (
                        '\n'.join(
                            diff_cleanup(
                                difflib.unified_diff(
                                    wrap(old_value, cols=60).split('\n'),
                                    wrap(new_value, cols=60).split('\n'),
                                    lineterm='', n=3
                                )
                            )
                        )
                    )
                )

            else:
                short_changes[field.capitalize()] = (old_value, new_value)

        def render_wiki_to_html_without_req(event, wikitext):
            if wikitext is None:
                return ""
            try:
                req = Mock(
                    href=Href(self.env.abs_href()),
                    abs_href=self.env.abs_href,
                    authname=event.author,
                    perm=MockPerm(),
                    chrome=dict(
                        warnings=[],
                        notices=[]
                    ),
                    args={}
                )
                context = Context.from_request(req, event.realm, event.target.id)
                formatter = HtmlFormatter(self.env, context, wikitext)
                return formatter.generate(True)
            except Exception, e:
                raise
                self.log.error("Failed to render %s", repr(wikitext))
                self.log.error(exception_to_unicode(e, traceback=True))
                return wikitext

        description = render_wiki_to_html_without_req(event, ticket['description'])
        temp        = render_wiki_to_html_without_req(event, event.comment)

        data = dict(
            ticket = ticket,
            description = description,
            author = event.author,
            fields = self._header_fields(ticket),
            comment = temp,
            category = event.category,
            ticket_link = self._ticket_link(ticket),
            project_name = self.env.project_name,
            project_desc = self.env.project_description,
            project_link = self.env.project_url or self.env.abs_href(),
            has_changes = short_changes or long_changes,
            long_changes = long_changes,
            short_changes = short_changes,
            attachment = event.attachment,
            attachment_link = self.env.abs_href('attachment/ticket',ticket.id)
        )
        chrome = Chrome(self.env)
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()
        templates = TemplateLoader(dirs, variable_lookup='lenient')
        template = templates.load('ticket_email_mimic.html',
                cls=MarkupTemplate)
        if template:
            stream = template.generate(**data)
            output = stream.render()
        return output

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
