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

# Maintained by doki_pen <doki_pen@doki-pen.org>

from setuptools import find_packages, setup

setup(
    name = 'AnnouncerPlugin', 
    version = '0.11',
    author = 'Robert Corsaro',
    author_email = 'doki_pen@doki-pen.org',
    description = 'Customizable notification system',
    license = """
    Copyright (c) 2008, Stephen Hansen. 
    Copyright (c) 2009, Robert Corsaro.  
    All rights reserved. Released under the 3-clause BSD license. 
    """,
    url = "http://www.trac-hacks.org/wiki/AnnouncerPlugin",
    packages = find_packages(exclude=['*.tests*']),
    package_data = {
        'announcer': [
            'templates/*.html', 
            'templates/*.txt', 
            'htdocs/*.*', 
            'htdocs/css/*.*'
        ]
    },
    install_requires = [
        'trac>=0.11',
    ],
    entry_points = {
        'trac.plugins': [
            'announcer.api = announcer.api',
            'announcer.distributors.mail = announcer.distributors.mail',
            'announcer.email_decorators.generic = announcer.email_decorators.generic',
            'announcer.email_decorators.ticket = announcer.email_decorators.ticket',
            'announcer.email_decorators.wiki = announcer.email_decorators.wiki',
            'announcer.filters.change_author = announcer.filters.change_author',
            'announcer.filters.unsubscribe = announcer.filters.unsubscribe',
            'announcer.formatters.ticket = announcer.formatters.ticket',
            'announcer.formatters.wiki = announcer.formatters.wiki',
            'announcer.pref = announcer.pref',
            'announcer.producers.attachment = announcer.producers.attachment',
            'announcer.producers.ticket = announcer.producers.ticket',
            'announcer.producers.wiki = announcer.producers.wiki',
            'announcer.resolvers.defaultdomain = announcer.resolvers.defaultdomain',
            'announcer.resolvers.sessionemail = announcer.resolvers.sessionemail',
            'announcer.resolvers.specified = announcer.resolvers.specified',
    #        'announcer.subscribers.rulefilters = announcer.subscribers.rulefilters',
            'announcer.subscribers.ticket_compat = announcer.subscribers.ticket_compat',
            'announcer.subscribers.ticket_components = announcer.subscribers.ticket_components',
            'announcer.subscribers.ticket_custom = announcer.subscribers.ticket_custom',
            'announcer.subscribers.ticket_groups = announcer.subscribers.ticket_groups',
            'announcer.subscribers.watchers = announcer.subscribers.watchers',
            'announcer.subscribers.watch_users = announcer.subscribers.watch_users',
            'announcer.subscribers.wiki = announcer.subscribers.wiki',
            'announcer.util.mail = announcer.util.mail',
        ]    
    },
    test_suite = 'announcer.tests',
)
