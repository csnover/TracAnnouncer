from announcerplugin.api import IAnnouncementFormatter
from genshi import HTML
from genshi.template import NewTextTemplate, MarkupTemplate
from genshi.template import TemplateLoader
from trac.config import Option, IntOption, ListOption
from trac.core import Component, implements
from trac.util.text import wrap, to_unicode
from trac.ticket.api import TicketSystem
from trac.versioncontrol.diff import diff_blocks
from trac.web.chrome import Chrome
from trac.web.href import Href
from trac.wiki.formatter import wiki_to_html
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

class TicketEmailFormatter(Component):
    implements(IAnnouncementFormatter)
        
    ticket_email_subject = Option('announcer', 'ticket_email_subject', 
        "Ticket #${ticket.id}: ${ticket['summary']} " \
                "{% if action %}[${action}]{% end %}",
            """Format string for ticket email subject.  This is 
               a mini genshi template that is passed the ticket
               event and action objects.""")
    
    ticket_email_header_fields = ListOption('announcer', 
            'ticket_email_header_fields', 
            'owner, reporter, milestone, priority, severity',
            doc="""Comma seperated list of fields to appear in tickets.  
            Use * to include all headers.""")
    
    def get_format_transport(self):
        return "email"
        
    def get_format_realms(self, transport):
        if transport == "email":
            yield "ticket"
        return
        
    def get_format_styles(self, transport, realm):
        if transport == "email":
            if realm == "ticket":
                yield "text/plain"
                yield "text/html"
        
    def get_format_alternative(self, transport, realm, style):
        if transport == "email":
            if realm == "ticket":
                if style == "text/html":
                    return "text/plain"
        return None
        
    def format_headers(self, transport, realm, style, event):
        ticket = event.target
        return dict(
            realm=realm,
            ticket=ticket.id,
            priority=ticket['priority'],
            severity=ticket['severity']            
        )
        
    def format_subject(self, transport, realm, style, event):
        action = None
        if transport == "email":
            if realm == "ticket":
                if event.changes:
                    if 'status' in event.changes:
                        action = 'Status -> %s' % (event.target['status'])
                template = NewTextTemplate(self.ticket_email_subject)
                return template.generate(ticket=event.target, event=event, 
                        action=action).render()
                
    def format(self, transport, realm, style, event):
        if transport == "email":
            if realm == "ticket":
                if style == "text/plain":
                    return self._format_plaintext(event)
                elif style == "text/html":
                    return self._format_html(event)

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
            ticket_link = self.env.abs_href('ticket', ticket.id),
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
        if len(headers) and headers[0].strip() == '*':
            tsystem = TicketSystem(self.env)
            headers = tsystem.get_ticket_fields()
        return headers 
        
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

        try:
            temp = wiki_to_html(event.comment, self.env, None)
        except:
            temp = 'Comment in plain text: %s'%event.comment
        data = dict(
            ticket = ticket,
            author = event.author,
            fields = self._header_fields(ticket),
            comment = temp,
            category = event.category,
            ticket_link = self.env.abs_href('ticket', ticket.id),
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

