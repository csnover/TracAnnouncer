from trac.core import Component, implements
from announcerplugin.api import IAnnouncementFormatter
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

class WikiEmailFormatter(Component):
    implements(IAnnouncementFormatter)
        
    wiki_email_subject = Option('announcer', 'wiki_email_subject', 
            "Page: ${page.name} ${action}",
            """Format string for the wiki email subject.  This is a
               mini genshi template and it is passed the page, event
               and action objects.""")
    wiki_email_diff = BoolOption('announcer', 'wiki_email_diff', 
            "true",
            """Should a wiki diff be sent with emails?""")
    
    def get_format_transport(self):
        return "email"
        
    def get_format_realms(self, transport):
        if transport == "email":
            yield "wiki"
        return
        
    def get_format_styles(self, transport, realm):
        if transport == "email":
            if realm == "wiki":
                yield "text/plain"
        
    def get_format_alternative(self, transport, realm, style):
        return None
        
    def format_headers(self, transport, realm, style, event):
        return {}
        
    def format_subject(self, transport, realm, style, event):
        if transport == "email":
            if realm == "wiki":
                template = NewTextTemplate(self.wiki_email_subject)
                return template.generate(page=event.target, event=event, 
                        action=event.category).render()
                
    def format(self, transport, realm, style, event):
        if transport == "email":
            if realm == "wiki":
                if style == "text/plain":
                    return self._format_plaintext(event)

    def _format_plaintext(self, event):
        page = event.target
        data = dict(
            action = event.category,
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
        
