# -*- coding: utf-8 -*-
#
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
from trac.config import BoolOption, Option
from trac.core import *
from trac.web.chrome import Chrome

from genshi.template import NewTextTemplate, TemplateLoader

from announcer.api import AnnouncementSystem, AnnouncementEvent
from announcer.api import IAnnouncementFormatter, IAnnouncementSubscriber
from announcer.api import IAnnouncementPreferenceProvider, istrue
from announcer.distributors.mail import IAnnouncementEmailDecorator
from announcer.util.mail import set_header, next_decorator
from announcer.util.settings import BoolSubscriptionSetting 
from announcer.util.settings import SubscriptionSetting

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


class FullBlogAnnouncement(Component):
    """Send announcements on build status."""

    implements(
        IBlogChangeListener,
        IAnnouncementSubscriber, 
        IAnnouncementFormatter,
        IAnnouncementEmailDecorator,
        IAnnouncementPreferenceProvider
    )

    always_notify_author = BoolOption('fullblog-announcement', 
            'always_notify_author', 'true', 
            """Notify the blog author of any changes to her blogs,
            including changes to comments.
            """)

    blog_email_subject = Option('fullblog-announcement', 'blog_email_subject',
            "Blog: ${blog.name} ${action}",
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

    # IAnnouncementSubscriber interface
    def subscriptions(self, event):
        if event.realm != 'blog':
            return
        if not event.category in ('post created',
                                  'post changed',
                                  'post deleted',
                                  'comment created',
                                  'comment changed',
                                  'comment deleted'):
            return

        category = event.category.startswith('post') and 'post' or 'comment'
        for result in self._members(category, event):
            self.log.debug("BlogSubscriber added '%s (%s)' for '%s'"%(
                    result[1], result[2], result[4]))
            yield result[:-1]

    # IAnnouncementEmailDecorator
    def decorate_message(self, event, message, decorates=None):
        if event.realm == "blog":
            template = NewTextTemplate(self.blog_email_subject)
            subject = template.generate(
                blog=event.blog_post, 
                action=event.category
            ).render()
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

    # IAnnouncementPreferenceProvider interface
    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "blog", "Blog Subscriptions"
        
    def render_announcement_preference_box(self, req, panel):
        settings = self._settings()
        if req.method == "POST":
            for attr, setting in settings.items():
                setting.set_user_setting(req.session, 
                        req.args.get('announcer_blog_%s'%attr), save=False)
            req.session.save()
        data = {}
        for attr, setting in settings.items():
            data[attr] = setting.get_user_setting(req.session.sid)[0]
        return "prefs_announcer_blog.html", dict(data=data)

    # private methods
    def _settings(self):
        settings = {}
        for p in ('new_posts', 'all'):
            settings[p] = BoolSubscriptionSetting(self.env, 'fullblog_%s'%p)
        settings['my_posts'] = BoolSubscriptionSetting(
            self.env, 
            'fullblog_my_posts', 
            self.always_notify_author
        )
        settings['author_posts'] = SubscriptionSetting(
            self.env,
            'fullblog_author_posts'
        )
            
        return settings

    def _members(self, type, event):
        settings = self._settings()

        # My Posts
        result = settings['my_posts'].get_user_setting(event.blog_post.author)
        if result[0]:
            yield (
                'email',
                event.blog_post.author, 
                result[1],
                None,
                'My Post'
            )

        if event.category == 'post created':
            for result in settings['new_posts'].get_subscriptions():
                yield result + ('New Post',)

            # Watched Author Posts
            def match(value):
                for name in [i.strip() for i in value.split(',')]:
                    if name == event.blog_post.author:
                        return True
                return False
            for result in settings['author_posts'].get_subscriptions(match):
                yield result + ('Author Post',)

        # All
        for result in settings['all'].get_subscriptions():
            yield result + ('All Blog Events',)

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

