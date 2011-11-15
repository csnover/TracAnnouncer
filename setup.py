# -*- coding: utf-8 -*-
#
# Copyright (c) 2008, Stephen Hansen
# Copyright (c) 2009, Robert Corsaro
# Copyright (c) 2010,2011 Steffen Hoffmann
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

extra = {}

try:
    from trac.util.dist  import  get_l10n_cmdclass
    cmdclass = get_l10n_cmdclass()
    if cmdclass:
        extra['cmdclass'] = cmdclass
        extractors = [
            ('**.py',                'python', None),
            ('**/templates/**.html', 'genshi', None),
            ('**/templates/**.txt',  'genshi', {
                'template_class': 'genshi.template:TextTemplate'
            }),
        ]
        extra['message_extractors'] = {'announcer': extractors}
# i18n is implemented to be optional here.
except ImportError:
    pass


setup(
    name = 'TracAnnouncer',
    version = '0.12.1',
    author = 'Robert Corsaro',
    author_email = 'rcorsaro@gmail.com',
    description = 'Customizable notification system',
    license = """
    Copyright (c) 2008, Stephen Hansen.
    Copyright (c) 2009, Robert Corsaro.
    All rights reserved. Released under the 3-clause BSD license.
    """,
    url = 'http://www.trac-hacks.org/wiki/AnnouncerPlugin',
    packages = find_packages(exclude=['*.tests*']),
    package_data = {
        'announcer': [
            'htdocs/*.*',
            'htdocs/css/*.*',
            'locale/*/LC_MESSAGES/*.mo',
            'locale/.placeholder',
            'templates/*.html',
            'templates/*.txt'
        ]
    },
    install_requires = ['Genshi >= 0.5', 'Trac >= 0.11'],
    extras_require={
        'Babel': 'Babel>= 0.9.5',
        'Trac': 'Trac >= 0.12',
        'acct_mgr': 'TracAccountManager',
        'bitten': 'Bitten',
        'fullblog': 'TracFullBlogPlugin',
        'xmpp': 'xmpppy',
    },
    entry_points = {
        'trac.plugins': [
            'announcer.api = announcer.api',
            'announcer.distributors.mail = announcer.distributors.mail',
            'announcer.distributors.xmppd = announcer.distributors.xmppd[xmpp]',
            'announcer.email_decorators = announcer.email_decorators',
            'announcer.filters = announcer.filters',
            'announcer.formatters = announcer.formatters',
            'announcer.model = announcer.model',
            'announcer.pref = announcer.pref',
            'announcer.producers = announcer.producers',
            'announcer.resolvers = announcer.resolvers',
            'announcer.subscribers = announcer.subscribers',
            'announcer.util.mail = announcer.util.mail',
            'announcer.opt.acct_mgr.announce = announcer.opt.acct_mgr.announce[acct_mgr]',
            'announcer.opt.bitten.announce = announcer.opt.bitten.announce[bitten]',
            'announcer.opt.fullblog.announce = announcer.opt.fullblog.announce[fullblog]',
        ]
    },
    test_suite = 'announcer.tests',
    **extra
)
