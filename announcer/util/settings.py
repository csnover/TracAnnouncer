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

from announcer.api import istrue

class SubscriptionSetting(object):
    """Encapsulate user text subscription and filter settings.
    
    Subscription settings have default values, usually trac properties,
    and user session attribute settings.  If the user setting is unset,
    then the default value will be returned.
    """

    def __init__(self, env, name, default=None):
        self.default = default
        self.env = env
        self.name = name

    def set_user_setting(self, session, value, save=True):
        """Sets session attribute to 1 or 0."""
        session[self._attr_name()] = value
        if save:
            session.save()

    def get_user_setting(self, sid):
        """Returns tuple of (value, authenticated)."""
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT value, authenticated
              FROM session_attribute
             WHERE sid=%s
               AND name=%s
        """, (sid, self._attr_name()))
        row = cursor.fetchone()
        if row:
            value = row[0]
            authenticated = istrue(row[1])
        else:
            value = self.default
            authenticated = False

        # We use None here so that Genshi templates check their checkboxes 
        # properly and without confusion.
        return (value, authenticated)

    def get_subscriptions(self, match):
        """Generates tuples of (distributor, sid, authenticated, email).  

        `match` should is passed the string value of the setting and should
        return true or false depending on whether the subscription matches.

        Tuples are suitable for yielding from IAnnouncementSubscriber's 
        subscriptions method.
        """
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid, authenticated, value
              FROM session_attribute
             WHERE name=%s
        """, (self._attr_name(),))
        for result in cursor.fetchall():
            if match(result[2]):
                authenticated = istrue(result[1])
                yield  ('email', result[0], authenticated, None)

    def _attr_name(self):
        return "sub_%s"%(self.name)


class BoolSubscriptionSetting(object):
    """Encapsulate boolean user subscription and filter settings.
    
    Subscription settings have default values, usually trac properties,
    and user session attribute settings.  If the user setting is unset,
    then the default value will be returned.
    """

    def __init__(self, env, name, default=None):
        self.default = default
        self.env = env
        self.name = name

    def set_user_setting(self, session, value, save=True):
        """Sets session attribute to 1 or 0."""
        if istrue(value):
            session[self._attr_name()] = '1'
        else:
            session[self._attr_name()] = '0'
        if save:
            session.save()

    def get_user_setting(self, sid):
        """Returns tuple of (value, authenticated).  

        Value is always True or None.  This will work with Genshi template
        checkbox logic.
        """
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT value, authenticated
              FROM session_attribute
             WHERE sid=%s
               AND name=%s
        """, (sid, self._attr_name()))
        row = cursor.fetchone()
        if row:
            value = istrue(row[0])
            authenticated = istrue(row[1])
        else:
            value = istrue(self.default)
            authenticated = False

        # We use None here so that Genshi templates check their checkboxes 
        # properly and without confusion.
        return (value and True or None, authenticated)

    def get_subscriptions(self):
        """Generates tuples of (distributor, sid, authenticated, email).  

        Tuples are suitable for yielding from IAnnouncementSubscriber's 
        subscriptions method.
        """
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid, authenticated, value
              FROM session_attribute
             WHERE name=%s
        """, (self._attr_name(),))
        for result in cursor.fetchall():
            if istrue(result[2]):
                authenticated = istrue(result[1])
                yield  ('email', result[0], authenticated, None)

    def _attr_name(self):
        return "sub_%s"%(self.name)

