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
from announcer.api import IAnnouncementFormatter, IAnnouncementSubscriber
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import _
from announcer.distributors.mail import IAnnouncementEmailDecorator
from announcer.util.mail import set_header, next_decorator
from announcer.util.settings import BoolSubscriptionSetting

from bitten.api import IBuildListener
from bitten.model import Build, BuildStep, BuildLog


class BittenAnnouncedEvent(AnnouncementEvent):
    def __init__(self, build, category):
        AnnouncementEvent.__init__(self, 'bitten', category, build)

class BittenAnnouncement(Component):
    """Send announcements on build status."""

    implements(
        IBuildListener,
        IAnnouncementSubscriber, 
        IAnnouncementFormatter,
        IAnnouncementEmailDecorator,
        IAnnouncementPreferenceProvider
    )

    readable_states = {
        Build.SUCCESS: _('Successful'),
        Build.FAILURE: _('Failed'),
    }

    # IBuildListener interface
    def build_started(self, build):
        """build started"""
        self._notify(build, 'started')

    def build_aborted(self, build):
        """build aborted"""
        self._notify(build, 'aborted')

    def build_completed(self, build):
        """build completed"""
        self._notify(build, 'completed')

    # IAnnouncementSubscriber interface
    def subscriptions(self, event):
        if event.realm == 'bitten':
            settings = self._settings()
            if event.category in settings.keys():
                for subscriber in settings[event.category].get_subscriptions():
                    self.log.debug("BittenAnnouncementSubscriber added '%s " \
                            "(%s)'", subscriber[1], subscriber[2])
                    yield subscriber

    # IAnnouncementFormatter interface
    def styles(self, transport, realm):
        if realm == 'bitten':
            yield 'text/plain'

    def alternative_style_for(self, transport, realm, style):
        if realm == 'bitten' and style != 'text/plain':
            return 'text/plain'

    def format(self, transport, realm, style, event):
        if realm == 'bitten' and style == 'text/plain':
            return self._format_plaintext(event)

    # IAnnouncementEmailDecorator
    def decorate_message(self, event, message, decorates=None):
        if event.realm == "bitten":
            build_id = str(event.target.id)
            build_link = self._build_link(event.target)
            subject = '[%s Build] %s [%s] %s' % (
                self.readable_states.get(
                    event.target.status, 
                    event.target.status
                ),
                self.env.project_name,
                event.target.rev,
                event.target.config
            )
            set_header(message, 'X-Trac-Build-ID', build_id)
            set_header(message, 'X-Trac-Build-URL', build_link)
            set_header(message, 'Subject', subject) 
        return next_decorator(event, message, decorates)

    # IAnnouncementPreferenceProvider interface
    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "bitten_subscription", _("Bitten Subscription")

    def render_announcement_preference_box(self, req, panel):
        settings = self._settings()
        if req.method == "POST":
            for k, setting in settings.items():
                setting.set_user_setting(req.session, 
                    value=req.args.get('bitten_%s_subscription'%k), save=False)
            req.session.save()
        data = {}
        for k, setting in settings.items():
            data[k] = setting.get_user_setting(req.session.sid)[1]
        return "prefs_announcer_bitten.html", data

    # private methods
    def _notify(self, build, category):
        self.log.info('BittenAnnouncedEventProducer invoked for build %r', build)
        self.log.debug('build status: %s', build.status)
        self.log.info('Creating announcement for build %r', build)
        try:
            announcer = AnnouncementSystem(self.env)
            announcer.send(BittenAnnouncedEvent(build, category))
        except Exception, e:
            self.log.exception("Failure creating announcement for build "
                               "%s: %s", build.id, e)

    def _settings(self):
        ret = {}
        for p in ('started', 'aborted', 'completed'):
            ret[p] = BoolSubscriptionSetting(self.env, 'bitten_%s'%p)
        return ret

    def _format_plaintext(self, event):
        failed_steps = BuildStep.select(self.env, build=event.target.id,
                                        status=BuildStep.FAILURE)
        change = self._get_changeset(event.target)
        data = {
            'build': {
                'id': event.target.id,
                'status': self.readable_states.get(
                    event.target.status, event.target.status
                ),
                'link': self._build_link(event.target),
                'config': event.target.config,
                'slave': event.target.slave,
                'failed_steps': [{
                    'name': step.name,
                    'description': step.description,
                    'errors': step.errors,
                    'log_messages': 
                       self._get_all_log_messages_for_step(event.target, step),
                } for step in failed_steps],
            },
            'change': {
                'rev': change.rev,
                'link': self.env.abs_href.changeset(change.rev),
                'author': change.author,
            },
            'project': {
                'name': self.env.project_name,
                'url': self.env.project_url or self.env.abs_href(),
                'descr': self.env.project_description
            }
        }
        chrome = Chrome(self.env)
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()
        templates = TemplateLoader(dirs, variable_lookup='lenient')
        template = templates.load('bitten_plaintext.txt', 
                cls=NewTextTemplate)
        if template:
            stream = template.generate(**data)
            output = stream.render('text')
        return output

    def _build_link(self, build):
        return self.env.abs_href.build(build.config, build.id)

    def _get_all_log_messages_for_step(self, build, step):
        messages = []
        for log in BuildLog.select(self.env, build=build.id,
                                   step=step.name):
            messages.extend(log.messages)
        return messages

    def _get_changeset(self, build):
        return self.env.get_repository().get_changeset(build.rev)

