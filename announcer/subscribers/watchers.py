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

import re
from trac.core import *
from trac.config import ListOption
from trac.web.api import IRequestFilter, IRequestHandler, Href
from trac.web.chrome import ITemplateProvider, add_ctxtnav, add_stylesheet, \
                            add_script
from trac.resource import get_resource_url
from trac.ticket.api import ITicketChangeListener
from trac.wiki.api import IWikiChangeListener
from trac.util.text import to_unicode
from genshi.builder import tag
from announcer.api import IAnnouncementSubscriber

class WatchSubscriber(Component):

    implements(IRequestFilter, IRequestHandler, IAnnouncementSubscriber,
        ITicketChangeListener, IWikiChangeListener)

    watchable_paths = ListOption('announcer', 'watchable_paths', 
        'wiki/*,ticket/*',
        doc='List of URL paths to allow watching. Globs are supported.')
    ctxtnav_names = ListOption('announcer', 'ctxtnav_names',
        ['Watch This','Unwatch This'],
        doc="Text of context navigation entries. "
            "An empty list removes them from the context navigation bar.")

    path_match = re.compile(r'/watch/(.*)')

    # IRequestHandler methods
    def match_request(self, req):
        if self.path_match.match(req.path_info):
            realm = self.normalise_resource(req.path_info).split('/')[1]
            return "%s_VIEW" % realm.upper() in req.perm
        return False

    def process_request(self, req):
        match = self.path_match.match(req.path_info)
        resource = self.normalise_resource(match.groups()[0])
        realm, _ = resource.split('/', 1)
        req.perm.require('%s_VIEW' % realm.upper())
        self.toggle_watched(req.session.sid, (not req.authname == \
                'anonymous') and 1 or 0, resource, req)
        req.redirect(req.href(resource))

    def toggle_watched(self, sid, authenticated, resource, req=None):
        realm, resource = resource.split('/', 1)
        if self.is_watching(sid, authenticated, realm, resource):
            self.set_unwatch(sid, authenticated, realm, resource)
            self._schedule_notice(req, 'You are no longer receiving ' \
                    'change notifications about this resource.')
        else:
            self.set_watch(sid, authenticated, realm, resource)
            self._schedule_notice(req, 'You are now receiving ' \
                    'change notifications about this resource.')
            
    def _schedule_notice(self, req, message):
        req.session['_announcer_watch_message_'] = message
                    
    def _add_notice(self, req):
        if '_announcer_watch_message_' in req.session:
            from trac.web.chrome import add_notice
            add_notice(req, req.session['_announcer_watch_message_'])
            del req.session['_announcer_watch_message_']
                    
    def is_watching(self, sid, authenticated, realm, resource):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT id
              FROM subscriptions
             WHERE sid=%s AND authenticated=%s
               AND enabled=1 AND managed=%s
               AND realm=%s
               AND category=%s
               AND rule=%s
        """, (sid, int(authenticated), 'watcher', realm, '*', 
                to_unicode(resource)))
        result = cursor.fetchone()
        if result:
            return True
        else:
            return False
    
    def set_watch(self, sid, authenticated, realm, resource):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        self.set_unwatch(sid, authenticated, realm, resource, use_db=db)
        cursor.execute("""
            INSERT INTO subscriptions
                        (sid, authenticated, 
                         enabled, managed, 
                         realm, category, 
                         rule, transport)
                 VALUES
                        (%s, %s, 
                         1, %s, 
                         %s, %s,
                         %s, %s)
        """, (
                sid, int(authenticated), 
                'watcher', realm, '*', 
                resource, 'email'
            )
        )
        db.commit()
        
    def set_unwatch(self, sid, authenticated, realm, resource, use_db=None):
        if not use_db:
            db = self.env.get_db_cnx()
        else:
            db = use_db
        cursor = db.cursor()
        cursor.execute("""
            DELETE
              FROM subscriptions
             WHERE sid=%s AND authenticated=%s
               AND enabled=1 AND managed=%s
               AND realm=%s
               AND category=%s
               AND rule=%s
        """, (sid, int(authenticated), 'watcher', realm, '*', 
            to_unicode(resource)))
        if not use_db:
            db.commit()
            
    # IRequestFilter methods
    def pre_process_request(self, req, handler):
        return handler
        
    def post_process_request(self, req, template, data, content_type):
        self._add_notice(req)
        
        if req.authname != "anonymous" or (req.authname == 'anonymous' and \
                'email' in req.session):
            for pattern in self.watchable_paths:
                path = self.normalise_resource(req.path_info)
                if re.match(pattern, path):
                    realm, _ = path.split('/', 1)
                    if '%s_VIEW'%realm.upper() not in req.perm:
                        return (template, data, content_type)
                    self.render_watcher(req)
                    break
        return (template, data, content_type)

    # Internal methods
    def render_watcher(self, req):
        if not self.ctxtnav_names:
          return
        resource = self.normalise_resource(req.path_info)
        realm, resource = resource.split('/', 1)
        if self.is_watching(req.session.sid, not req.authname == 'anonymous', 
                realm, resource):
            action_name = len(self.ctxtnav_names) >= 2 and \
                    self.ctxtnav_names[1] or 'Unwatch This'
        else:
            action_name = len(self.ctxtnav_names) and \
                    self.ctxtnav_names[0] or 'Watch This'
        add_ctxtnav(req, 
            tag.a(
                action_name, href=req.href.watch(realm, resource)
            )
        )

    def normalise_resource(self, resource):
        if isinstance(resource, basestring):
            resource = resource.strip('/')
            # Special-case start page
            if not resource:
                resource = "wiki/WikiStart"
            elif resource == 'wiki':
                resource += '/WikiStart'
            return resource
        return get_resource_url(self.env, resource, Href('')).strip('/')
        
    # IWikiChangeListener
    def wiki_page_added(*args):
        pass
        
    def wiki_page_changed(*args):
        pass
        
    def wiki_page_deleted(self, page):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            DELETE
              FROM subscriptions
             WHERE managed=%s
               AND realm=%s
               AND rule=%s
        """, ('watcher', 'wiki', to_unicode(page.name)))
        db.commit()

    def wiki_page_version_deleted(*args):
        pass

    # ITicketChangeListener
    def ticket_created(*args):
        pass
        
    def ticket_changed(*args):
        pass
        
    def ticket_deleted(self, ticket):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            DELETE
              FROM subscriptions
             WHERE managed=%s
               AND realm=%s
               AND rule=%s
        """, ('watcher', 'ticket', to_unicode(ticket.id)))
        db.commit()
    
    # IAnnouncementSubscriber    
    def get_subscription_realms(self):
        return ('wiki', 'ticket')
        
    def get_subscription_categories(self, realm):
        return ('created', 'changed', 'attachment added')
        
    def get_subscriptions_for_event(self, event):
        if event.realm in self.get_subscription_realms():
            if event.category in self.get_subscription_categories(event.realm):
                db = self.env.get_db_cnx()
                cursor = db.cursor()
                cursor.execute("""
                    SELECT transport, sid, authenticated
                      FROM subscriptions
                     WHERE enabled=1 AND managed=%s
                       AND realm=%s
                       AND category=%s
                       AND rule=%s
                """, ('watcher', event.realm, '*', 
                    to_unicode(self._get_target_identifier(event.realm, 
                    event.target))))
            
                for transport, sid, authenticated in cursor.fetchall():
                    self.log.debug("WatchSubscriber added '%s (%s)' because " \
                        "of rule: watched"%(sid,authenticated and \
                        'authenticated' or 'not authenticated'))
                    yield (transport, sid, authenticated, None)
                    
    def _get_target_identifier(self, realm, target):
        if realm == "wiki":
            return target.name
        elif realm == "ticket":
            return target.id

