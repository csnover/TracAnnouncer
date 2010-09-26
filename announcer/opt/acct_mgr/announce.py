#-*- coding: utf-8 -*-
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
from trac.core import *
from trac.web.chrome import Chrome

from genshi.template import NewTextTemplate, TemplateLoader

from announcer.api import AnnouncementSystem, AnnouncementEvent
from announcer.api import IAnnouncementFormatter, IAnnouncementSubscriberDeprecated
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import _
from announcer.distributors.mail import IAnnouncementEmailDecorator
from announcer.util.mail import set_header, next_decorator
from announcer.util.settings import BoolSubscriptionSetting

from acct_mgr.api import IAccountChangeListener

class AccountChangeEvent(AnnouncementEvent):
    def __init__(self, category, username, password=None, token=None):
        AnnouncementEvent.__init__(self, 'acct_mgr', category, None)
        self.username = username
        self.password = password
        self.token = token

class AccountManagerAnnouncement(Component):
    """Send announcements on account changes."""

    implements(
        IAccountChangeListener,
        IAnnouncementSubscriberDeprecated,
        IAnnouncementFormatter,
        IAnnouncementEmailDecorator,
        IAnnouncementPreferenceProvider
    )

    # IAccountChangeListener interface
    def user_created(self, username, password):
        self._notify('created', username, password)

    def user_password_changed(self, username, password):
        self._notify('change', username, password)

    def user_deleted(self, username):
        self._notify('delete', username)

    def user_password_reset(self, username, email, password):
        self._notify('reset', username, password)

    def user_email_verification_requested(self, username, token):
        self._notify('verify', username, token=token)

    # IAnnouncementSubscriber interface
    def subscriptions(self, event):
        if event.realm == 'acct_mgr':
            for subscriber in self._get_membership(event):
                self.log.debug("AccountManagerAnnouncement added '%s " \
                        "(%s)'", subscriber[1], subscriber[2])
                yield subscriber

    # IAnnouncementFormatter interface
    def styles(self, transport, realm):
        if realm == 'acct_mgr':
            yield 'text/plain'

    def alternative_style_for(self, transport, realm, style):
        if realm == 'acct_mgr' and style != 'text/plain':
            return 'text/plain'

    def format(self, transport, realm, style, event):
        if realm == 'acct_mgr' and style == 'text/plain':
            return self._format_plaintext(event)

    # IAnnouncementEmailDecorator
    def decorate_message(self, event, message, decorates=None):
        if event.realm == "acct_mgr":
            prjname = self.env.project_name
            subject = '[%s] %s: %s' % (prjname, event.category, event.username)
            set_header(message, 'Subject', subject) 
        return next_decorator(event, message, decorates)

    # IAnnouncementPreferenceProvider interface
    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "acct_mgr_subscription", _("Account Manager Subscription")

    def render_announcement_preference_box(self, req, panel):
        settings = self._settings()
        if req.method == "POST":
            for k, setting in settings.items():
                setting.set_user_setting(req.session, 
                        value=req.args.get('acct_mgr_%s_subscription'%k),
                        save=False)
            req.session.save()
        data = {}
        for k, setting in settings.items():
            data[k] = setting.get_user_setting(req.session.sid)[1]
        return "prefs_announcer_acct_mgr_subscription.html", data

    # private methods
    def _notify(self, category, username, password=None, token=None):
        try:
            announcer = AnnouncementSystem(self.env)
            announcer.send(
                AccountChangeEvent(category, username, password, token)
            )
        except Exception, e:
            self.log.exception("Failure creating announcement for account "
                               "event %s: %s", username, category)

    def _settings(self):
        ret = {}
        for n in ('created', 'change', 'delete'):
            ret[n] = BoolSubscriptionSetting(self.env, "acct_mgr_%s"%n, None)
        return ret

    def _get_membership(self, event):
        settings = self._settings()
        if event.category in settings.keys():
            for result in settings[event.category].get_subscriptions():
                yield result
        elif event.category in ('verify', 'reset'):
            yield ('email', event.username, True, None)

    def _format_plaintext(self, event):
        acct_templates = {
            'created': 'acct_mgr_user_change_plaintext.txt', 
            'change': 'acct_mgr_user_change_plaintext.txt', 
            'delete': 'acct_mgr_user_change_plaintext.txt', 
            'reset': 'acct_mgr_reset_password_plaintext.txt', 
            'verify': 'acct_mgr_verify_plaintext.txt'
        }
        data = {
            'account': {
                'action': event.category,
                'username': event.username,
                'password': event.password,
                'token': event.token
            },
            'project': {
                'name': self.env.project_name,
                'url': self.env.abs_href(),
                'descr': self.env.project_description
            },
            'login': {
                'link': self.env.abs_href.login()
            }
        }
        if event.category == 'verify':
            data['verify'] = {
                'link': self.env.abs_href.verify_email(token=event.token)
            }
        chrome = Chrome(self.env)
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()
        templates = TemplateLoader(dirs, variable_lookup='lenient')
        template = templates.load(acct_templates[event.category], 
                cls=NewTextTemplate)
        if template:
            stream = template.generate(**data)
            output = stream.render('text')
        return output
