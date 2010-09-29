# -*- coding: utf-8 -*-
#
# Copyright (c) 2010, Robert Corsaro
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

from trac.config import BoolOption, Option
from trac.core import *
from trac.web.api import IRequestFilter, IRequestHandler
from trac.web.chrome import Chrome, add_notice, add_ctxtnav

from genshi.builder import tag
from genshi.template import NewTextTemplate, TemplateLoader

from announcer.api import AnnouncementSystem, AnnouncementEvent
from announcer.api import IAnnouncementFormatter, IAnnouncementSubscriber
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import _
from announcer.distributors.mail import IAnnouncementEmailDecorator
from announcer.model import Subscription, SubscriptionAttribute
from announcer.util.mail import set_header, next_decorator

from tracfullblog.api import IBlogChangeListener
from tracfullblog.model import BlogPost, BlogComment

class BlogChangeEvent(AnnouncementEvent):
    def __init__(self, blog_post, category, url, blog_comment=None):
        AnnouncementEvent.__init__(self, 'blog', category, blog_post)
        if blog_comment:
            if 'comment deleted' == category:
                self.comment = blog_comment['comment']
                self.author = blog_comment['author']
                self.timestamp = blog_comment['time']
            else:
                self.comment = blog_comment.comment
                self.author = blog_comment.author
                self.timestamp = blog_comment.time
        else:
            self.comment = blog_post.version_comment
            self.author = blog_post.version_author
            self.timestamp = blog_post.version_time
        self.remote_addr = url
        self.version = blog_post.version
        self.blog_post = blog_post
        self.blog_comment = blog_comment

class FullBlogAllSubscriber(Component):
    """Subscriber for any blog changes."""

    implements(IAnnouncementSubscriber)

    def matches(self, event):
        if event.realm != 'blog':
            return
        if not event.category in ('post created',
                                  'post changed',
                                  'post deleted',
                                  'comment created',
                                  'comment changed',
                                  'comment deleted'):
            return

        klass = self.__class__.__name__
        for i in Subscription.find_by_class(self.env, klass):
            yield i.subscription_tuple()

    def description(self):
        return _("notify me when any blog is modified, "
                "changed, deleted or commented on.")


class FullBlogNewSubscriber(Component):
    """Subscriber for any blog post creation."""

    implements(IAnnouncementSubscriber)

    def matches(self, event):
        if event.realm != 'blog':
            return
        if event.category != 'post created':
            return

        klass = self.__class__.__name__
        for i in Subscription.find_by_class(self.env, klass):
            yield i.subscription_tuple()

    def description(self):
        return "notify me when any blog post is created."


class FullBlogMyPostSubscriber(Component):
    """Subscriber for any blog changes to my posts."""

    implements(IAnnouncementSubscriber)

    always_notify_author = BoolOption('fullblog-announcement',
            'always_notify_author', 'true',
            """Notify the blog author of any changes to her blogs,
            including changes to comments.
            """)

    def matches(self, event):
        if event.realm != 'blog':
            return
        if not event.category in ('post changed',
                                  'post deleted',
                                  'comment created',
                                  'comment changed',
                                  'comment deleted'):
            return

        sids = (event.blog_post.author,)
        klass = self.__class__.__name__
        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return _("notify me when any blog that I posted "
            "is modified or commented on.")

class FullBlogWatchSubscriber(Component):
    """Subscriber to watch individual blogs."""

    implements(IAnnouncementSubscriber)
    implements(IRequestFilter)
    implements(IRequestHandler)

    # IAnnouncementSubscriber
    def matches(self, event):
        if event.realm != 'blog':
            return
        if not event.category in ('post created',
                                  'post changed',
                                  'post deleted',
                                  'comment created',
                                  'comment changed',
                                  'comment deleted'):
            return

        klass = self.__class__.__name__

        attrs = SubscriptionAttribute.find_by_class_realm_and_target(self.env,
                klass, 'blog', event.blog_post.name)
        sids = set(map(lambda x: x['sid'], attrs))

        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return "notify me when a blog that I'm watching changes."

    # IRequestFilter
    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, content_type):
        if 'BLOG_VIEW' not in req.perm:
            return (template, data, content_type)

        if '_blog_watch_message_' in req.session:
            add_notice(req, req.session['_blog_watch_message_'])
            del req.session['_blog_watch_message_']

        if req.authname == "anonymous":
            return (template, data, content_type)

        # FullBlogPlugin sets the blog_path arg in pre_process_request
        name = req.args.get('blog_path')
        if not name:
            return (template, data, content_type)

        klass = self.__class__.__name__

        attrs = SubscriptionAttribute.find_by_sid_class_and_target(
                self.env, req.session.sid, klass, name)
        if attrs:
            add_ctxtnav(req, tag.a(_('Unwatch This'),
                href=req.href.blog_watch(name)))
        else:
            add_ctxtnav(req, tag.a(_('Watch This'),
                href=req.href.blog_watch(name)))

        return (template, data, content_type)

    # IRequestHandler
    def match_request(self, req):
        return re.match(r'^/blog_watch/(.*)', req.path_info)

    def process_request(self, req):
        klass = self.__class__.__name__

        m = re.match(r'^/blog_watch/(.*)', req.path_info)
        (name,) = m.groups()

        @self.env.with_transaction()
        def do_update(db):
            attrs = SubscriptionAttribute.find_by_sid_class_and_target(
                    self.env, req.session.sid, klass, name)
            if attrs:
                SubscriptionAttribute.delete_by_sid_class_and_target(
                        self.env, req.session.sid, klass, name)
                req.session['_blog_watch_message_'] = \
                    _('You are no longer watching this blog post.')
            else:
                SubscriptionAttribute.add(
                        self.env, req.session.sid, klass, 'blog', (name,))
                req.session['_blog_watch_message_'] = \
                        _('You are now watching this blog post.')
        req.redirect(req.href.blog(name))


class FullBlogBloggerSubscriber(Component):
    """Subscriber for any blog changes to bloggers that I follow."""

    implements(IAnnouncementSubscriber)
    implements(IAnnouncementPreferenceProvider)

    def matches(self, event):
        if event.realm != 'blog':
            return
        if not event.category in ('post created',
                                  'post changed',
                                  'post deleted',
                                  'comment created',
                                  'comment changed',
                                  'comment deleted'):
            return

        klass = self.__class__.__name__

        sids = set(map(lambda x: x['sid'],
            SubscriptionAttribute.find_by_class_realm_and_target(
                self.env, klass, 'blog', event.blog_post.author)))

        for i in Subscription.find_by_sids_and_class(self.env, sids, klass):
            yield i.subscription_tuple()

    def description(self):
        return "notify me when any blogger that I follow has a blog update."

    # IAnnouncementPreferenceProvider interface
    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "bloggers", _("Followed Bloggers")

    def render_announcement_preference_box(self, req, panel):
        klass = self.__class__.__name__

        if req.method == "POST":
            @self.env.with_transaction()
            def do_update(db):
                SubscriptionAttribute.delete_by_sid_and_class(
                        self.env, req.session.sid, klass)
                blogs = set(map(lambda x: x.strip(),
                    req.args.get('announcer_watch_bloggers').split(',')))
                SubscriptionAttribute.add(self.env, req.session.sid,
                        klass, 'blog', blogs)

        attrs = SubscriptionAttribute.find_by_sid_and_class(self.env,
                req.session.sid, klass)
        data = {'sids': ','.join(set(map(lambda x: x['sid'], attrs)))}
        return "prefs_announcer_watch_bloggers.html", dict(data=data)


class FullBlogAnnouncement(Component):
    """Send announcements on blog events."""

    implements(IBlogChangeListener)
    implements(IAnnouncementFormatter)
    implements(IAnnouncementEmailDecorator)

    blog_email_subject = Option('fullblog-announcement', 'blog_email_subject',
            _("Blog: ${blog.name} ${action}"),
            """Format string for the blog email subject.

            This is a mini genshi template and it is passed the blog_post and
            action objects.
            """)

    # IBlogChangeListener interface
    def blog_post_changed(self, postname, version):
        """Called when a new blog post 'postname' with 'version' is added.

        version==1 denotes a new post, version>1 is a new version on existing
        post.
        """
        blog_post = BlogPost(self.env, postname, version)
        action = 'post created'
        if version > 1:
            action = 'post changed'
        announcer = AnnouncementSystem(self.env)
        announcer.send(
            BlogChangeEvent(
                blog_post,
                action,
                self.env.abs_href.blog(blog_post.name)
            )
        )

    def blog_post_deleted(self, postname, version, fields):
        """Called when a blog post is deleted:

        version==0 means all versions (or last remaining) version is deleted.
        Any version>0 denotes a specific version only.
        Fields is a dict with the pre-existing values of the blog post.
        If all (or last) the dict will contain the 'current' version
        contents.
        """
        blog_post = BlogPost(self.env, postname, version)
        announcer = AnnouncementSystem(self.env)
        announcer.send(
            BlogChangeEvent(
                blog_post,
                'post deleted',
                self.env.abs_href.blog(blog_post.name)
            )
        )

    def blog_comment_added(self, postname, number):
        """Called when Blog comment number N on post 'postname' is added."""
        blog_post = BlogPost(self.env, postname, 0)
        blog_comment = BlogComment(self.env, postname, number)
        announcer = AnnouncementSystem(self.env)
        announcer.send(
            BlogChangeEvent(
                blog_post,
                'comment created',
                self.env.abs_href.blog(blog_post.name),
                blog_comment
            )
        )

    def blog_comment_deleted(self, postname, number, fields):
        """Called when blog post comment 'number' is deleted.

        number==0 denotes all comments is deleted and fields will be empty.
        (usually follows a delete of the blog post).

        number>0 denotes a specific comment is deleted, and fields will contain
        the values of the fields as they existed pre-delete.
        """
        blog_post = BlogPost(self.env, postname, 0)
        announcer = AnnouncementSystem(self.env)
        announcer.send(
            BlogChangeEvent(
                blog_post,
                'comment deleted',
                self.env.abs_href.blog(blog_post.name),
                fields
            )
        )


    # IAnnouncementEmailDecorator
    def decorate_message(self, event, message, decorates=None):
        if event.realm == "blog":
            template = NewTextTemplate(self.blog_email_subject.encode('utf8'))
            subject = template.generate(
                blog=event.blog_post,
                action=event.category
            ).render('text', encoding=None)
            set_header(message, 'Subject', subject)
        return next_decorator(event, message, decorates)

    # IAnnouncementFormatter interface
    def styles(self, transport, realm):
        if realm == 'blog':
            yield 'text/plain'

    def alternative_style_for(self, transport, realm, style):
        if realm == 'blog' and style != 'text/plain':
            return 'text/plain'

    def format(self, transport, realm, style, event):
        if realm == 'blog' and style == 'text/plain':
            return self._format_plaintext(event)


    def _format_plaintext(self, event):
        blog_post = event.blog_post
        blog_comment = event.blog_comment
        data = dict(
            name = blog_post.name,
            author = event.author,
            time = event.timestamp,
            category = event.category,
            version = event.version,
            link = event.remote_addr,
            title = blog_post.title,
            body = blog_post.body,
            comment = event.comment,
        )
        chrome = Chrome(self.env)
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()
        templates = TemplateLoader(dirs, variable_lookup='lenient')
        template = templates.load(
            'fullblog_plaintext.txt',
            cls=NewTextTemplate
        )
        if template:
            stream = template.generate(**data)
            output = stream.render('text')
        return output

