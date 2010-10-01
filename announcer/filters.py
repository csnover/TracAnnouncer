# -*- coding: utf-8 -*-
#
# Copyright (c) 2009, Robert Corsaro
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

"""Filters can remove subscriptions after they are collected.
"""
import re

from trac.core import *
from trac.config import ListOption
from trac.perm import PermissionSystem

from announcer.api import IAnnouncementSubscriptionFilter
from announcer.api import _

class DefaultPermissionFilter(Component):
    """DefaultPermissionFilter simply checks that each subscription
    has ${REALM}_VIEW permissions before allow the subscription notice
    to be sent.
    """
    implements(IAnnouncementSubscriptionFilter)

    exception_realms = ListOption('announcer', 'filter_exception_realms', '',
            """The PermissionFilter will filter an announcements for with the
            user doesn't have ${REALM}_VIEW permission.  If there is some
            realm that doesn't use a permission called ${REALM}_VIEW then
            you should add it to this list and create a custom filter to
            enforce it's permissions.  Be careful because permissions can be
            bypassed using the AnnouncerPlugin.
            """)

    def filter_subscriptions(self, event, subscriptions):
        permsys = PermissionSystem(self.env)
        permitted_users = permsys.get_users_with_permission('%s_VIEW'%event.realm.upper())
        for subscription in subscriptions:
            sid = subscription[1]
            if sid not in permitted_users:
                self.log.debug(
                    "Filtering %s because of rule: DefaultPermissionFilter"\
                    %sid
                )
                pass
            else:
                yield subscription
