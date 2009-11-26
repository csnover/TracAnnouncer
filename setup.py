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
    version = '1.0-a1',
    author = 'Robert Corsaro',
    author_email = 'doki_pen@doki-pen.org',
    description = 'Customizable notification system',
    license = \
    """Copyright (c) 2008, Stephen Hansen. Copyright (c) 2009, Robert Corsaro.  All rights reserved. Released under the 3-clause BSD license. """,
    url = "http://www.trac-hacks.org/wiki/AnnouncerPlugin",
    packages = find_packages(exclude=['*.tests*']),
    package_data = {'announcerplugin': ['templates/*.html', 'templates/*.txt', 'htdocs/*.*', 'htdocs/css/*.*']},
    install_requires = [
        #'trac>=0.11',
    ],
    entry_points = {
        'trac.plugins': [
            'announcerplugin.api = announcerplugin.api',
            'announcerplugin.distributors.email_distributor = announcerplugin.distributors.email_distributor',
            'announcerplugin.formatters.ticket_email = announcerplugin.formatters.ticket_email',
            'announcerplugin.formatters.wiki_email = announcerplugin.formatters.wiki_email',
            'announcerplugin.pref = announcerplugin.pref',
            'announcerplugin.producers.attachment = announcerplugin.producers.attachment',
            'announcerplugin.producers.ticket = announcerplugin.producers.ticket',
            'announcerplugin.producers.wiki = announcerplugin.producers.wiki',
            'announcerplugin.resolvers.defaultdomain = announcerplugin.resolvers.defaultdomain',
            'announcerplugin.resolvers.sessionemail = announcerplugin.resolvers.sessionemail',
            'announcerplugin.resolvers.specified = announcerplugin.resolvers.specified',
    #        'announcerplugin.subscribers.rulefilters = announcerplugin.subscribers.rulefilters',
            'announcerplugin.subscribers.ticket_compat = announcerplugin.subscribers.ticket_compat',
            'announcerplugin.subscribers.ticket_components = announcerplugin.subscribers.ticket_components',
            'announcerplugin.subscribers.ticket_custom = announcerplugin.subscribers.ticket_custom',
            'announcerplugin.subscribers.ticket_groups = announcerplugin.subscribers.ticket_groups',
            'announcerplugin.subscribers.watchers = announcerplugin.subscribers.watchers',
            'announcerplugin.subscribers.watch_users = announcerplugin.subscribers.watch_users',
            'announcerplugin.subscribers.wiki = announcerplugin.subscribers.wiki',
        ]    
    },
    test_suite = 'announcerplugin.tests',
)
