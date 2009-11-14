from trac.core import Component, implements, ExtensionPoint
from trac.prefs.api import IPreferencePanelProvider
from trac.web.chrome import ITemplateProvider, add_stylesheet
from trac.web import IRequestHandler
from pkg_resources import resource_filename
from announcerplugin.api import IAnnouncementPreferenceProvider
from trac.web.chrome import Chrome

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
        
        
