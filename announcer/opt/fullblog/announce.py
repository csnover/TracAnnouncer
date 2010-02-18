#-*- coding: utf-8 -*-
#
# Copyright (C) 2007 Ole Trenner, <ole@jayotee.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

from trac.config import BoolOption, Option
from trac.core import *
from trac.web.chrome import Chrome

from genshi.template import NewTextTemplate, TemplateLoader

from announcer.api import AnnouncementSystem, AnnouncementEvent
from announcer.api import IAnnouncementFormatter, IAnnouncementSubscriber
from announcer.api import IAnnouncementPreferenceProvider, istrue
from announcer.distributors.mail import IAnnouncementEmailDecorator
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
            doc="""Notify the blog author
            of any changes to her blogs, including changes to comments.
            """)

    blog_email_subject = Option('fullblog-announcement', 'blog_email_subject',
            "Blog: ${blog.name} ${action}",
            """Format string for the blog email subject.  This is a
            mini genshi template and it is passed the blog_post and action
            objects.
            """)

    # IBlogChangeListener interface
    def blog_post_changed(self, postname, version):
        """Called when a new blog post 'postname' with 'version' is added .
        version==1 denotes a new post, version>1 is a new version on existing 
        post."""
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
        contents."""
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
            the values of the fields as they existed pre-delete."""
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

        if event.category.startswith('post'):
            for user, authed, rule in self._members('post', event):
                self.log.debug("BlogSubscriber added '%s (%s)' for '%s'"%(
                        user, authed, rule))
                yield ("email", user, authed, None)
        else:
            for user, authed, rule in self._members('comment', event):
                self.log.debug("BlogSubscriber added '%s (%s)' for '%s'"%(
                        user, authed, rule))
                yield ("email", user, authed, None)

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
        if req.method == "POST":
            for option in ('my_posts', 'new_posts', 'all'):
                if req.args.get('announcer_blog_%s'%option):
                    req.session['announcer_blog_%s'%option] = '1'
                else:
                    req.session['announcer_blog_%s'%option] = '0'
            authors = req.args.get('announcer_blog_author_posts', '')
            req.session['announcer_blog_author_posts'] = authors
                
        my_posts = req.session.get('announcer_blog_my_posts')
        if my_posts is None:
            my_posts = self.always_notify_author and '1'
        new_posts = req.session.get('announcer_blog_new_posts')
        all = req.session.get('announcer_blog_all')
        author_posts = req.session.get('announcer_blog_author_posts')

        data = dict(
            announcer_blog_my_posts = my_posts == '1' or None, 
            announcer_blog_new_posts = new_posts == '1' or None,
            announcer_blog_all = all == '1' or None,
            announcer_blog_author_posts = author_posts
        )
        return "prefs_announcer_blog.html", dict(data=data)

    # private methods
    def _members(self, type, event):
        name = event.blog_post.name
        db = self.env.get_db_cnx()
        cursor = db.cursor()

        # My Posts
        cursor.execute("""
            SELECT value, authenticated
              FROM session_attribute 
             WHERE name='announcer_blog_my_posts'
               AND sid=%s
        """, (event.blog_post.author,))
        result = cursor.fetchone()
        if (result and istrue(result[0])) or self.always_notify_author:
            yield (
                event.blog_post.author, 
                result and istrue(result[1]) or None,
                'My Post Subscription'
            )

        if event.category == 'post created':
            # New Posts
            cursor.execute("""
                SELECT sid, authenticated
                  FROM session_attribute 
                 WHERE name='announcer_blog_new_posts'
                   AND value='1'
            """)
            for result in cursor.fetchall():
                yield (result[0], istrue(result[1]), 'New Blog Subscription')

            # Watched Author Posts
            cursor.execute("""
                SELECT sid, authenticated, value
                  FROM session_attribute 
                 WHERE name='announcer_blog_author_posts'
            """)
            for result in cursor.fetchall():
                for name in [i.strip() for i in result[2].split(',')]:
                    if name == event.blog_post.author:
                        yield (
                            result[0], 
                            istrue(result[1]), 
                            'Blog Author Subscription'
                        )

        # All
        cursor.execute("""
            SELECT sid, authenticated
              FROM session_attribute 
             WHERE name='announcer_blog_all'
               AND value='1'
        """)
        for result in cursor.fetchall():
            yield (result[0], istrue(result[1]), 'All Blog Subscription')

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

