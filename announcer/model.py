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

from trac.util.datefmt import utc

__all__ = ['Subscription']

class Subscription(object):

    fields = ('id', 'sid', 'authenticated', 'distributor', 'format',
            'priority', 'adverb', 'class')

    def __init__(self, env):
        self.env = env
        self.values = {}

    def __getitem__(self, name):
        if name not in self.fields:
            raise KeyError(name)
        return self.values.get(name)

    def __setitem__(self, name, value):
        if name not in self.fields:
            raise KeyError(name)
        self.values[name] = value

    @classmethod
    def add(cls, env, subscription, db=None):
        """id and priority overwritten."""
        @env.with_transaction(db)
        def do_insert(db):
            cursor = db.cursor()
            priority = len(cls.find_by_sid_and_distributor(env, subscription['sid'], subscription['distributor'], db))+1
            cursor.execute("""
            INSERT INTO subscription
                        (time, changetime, sid, authenticated, distributor,
                        format, priority, adverb, class)
                 VALUES (datetime(), datetime(), %s, %s, %s, %s, %s, %s, %s)
            """, (subscription['sid'], subscription['authenticated'],
            subscription['distributor'], subscription['format'],
            priority, subscription['adverb'],
            subscription['class']))

    @classmethod
    def delete(cls, env, rule_id, db=None):
        @env.with_transaction(db)
        def do_delete(db):
            cursor = db.cursor()
            cursor.execute("""
            DELETE FROM subscription
                  WHERE id = %s
            """, (rule_id,))


    @classmethod
    def update_by_sid(cls, env, subscriptions, db=None):
        sid = None
        subs = []
        for i in subscriptions:
            if sid:
                if i[0] != sid:
                    raise Error('you crazy?!')
            else:
                sid = i[0]

            sub = Subscription(env)
            sub['sid'] = i[0]
            sub['authenticated'] = i[1]
            sub['distributor'] = i[2]
            sub['format'] = i[3]
            sub['priority'] = i[4]
            sub['adverb'] = i[5]
            sub['class'] = i[6]
            subs.append(sub)

        @env.with_transaction(db)
        def do_update(db):
            cursor = db.cursor()
            cursor.execute("""
            DELETE FROM subscription
                  WHERE sid=%s
            """, (sid,))

            for sub in subs:
                sub._insert(db)

    @classmethod
    def find_by_sid_and_distributor(cls, env, sid, distributor, db=None):
        subs = []

        @env.with_transaction(db)
        def do_select(db):
            cursor = db.cursor()
            cursor.execute("""
              SELECT id, sid, authenticated, distributor,
                     format, priority, adverb, class
                FROM subscription
               WHERE sid=%s
                 AND distributor=%s
            ORDER BY priority
            """, (sid,distributor))
            for i in cursor.fetchall():
                sub = Subscription(env)
                sub['id'] = i[0]
                sub['sid'] = i[1]
                sub['authenticated'] = i[2]
                sub['distributor'] = i[3]
                sub['format'] = i[4]
                sub['priority'] = i[5]
                sub['adverb'] = i[6]
                sub['class'] = i[7]
                subs.append(sub)

        return subs

    @classmethod
    def find_by_sids_and_class(cls, env, sids, klass, db=None):
        if not sids:
            return []

        subs = []

        @env.with_transaction(db)
        def do_select(db):
            cursor = db.cursor()
            cursor.execute("""
                SELECT id, sid, authenticated, distributor,
                       format, priority, adverb, class
                  FROM subscription
                 WHERE class=%s
                   AND sid IN (%s)
            """%('%s', ','.join(['%s']*len(sids))), (klass,)+tuple(sids))
            for i in cursor.fetchall():
                sub = Subscription(env)
                sub['id'] = i[0]
                sub['sid'] = i[1]
                sub['authenticated'] = i[2]
                sub['distributor'] = i[3]
                sub['format'] = i[4]
                sub['priority'] = i[5]
                sub['adverb'] = i[6]
                sub['class'] = i[7]
                subs.append(sub)

        return subs

    @classmethod
    def find_by_class(cls, env, klass, db=None):
        subs = []

        @env.with_transaction(db)
        def do_select(db):
            cursor = db.cursor()
            cursor.execute("""
                SELECT id, sid, authenticated, distributor,
                       format, priority, adverb, class
                  FROM subscription
                 WHERE class=%s
            """, (klass,))
            for i in cursor.fetchall():
                sub = Subscription(env)
                sub['id'] = i[0]
                sub['sid'] = i[1]
                sub['authenticated'] = i[2]
                sub['distributor'] = i[3]
                sub['format'] = i[4]
                sub['priority'] = i[5]
                sub['adverb'] = i[6]
                sub['class'] = i[7]
                subs.append(sub)

        return subs

    def subscription_tuple(self):
        return (
            self.values['class'],
            self.values['distributor'],
            self.values['sid'],
            self.values['authenticated'] == 1,
            None,
            self.values['format'],
            self.values['priority'],
            self.values['adverb']
        )

    def _insert(self, db=None):
        self.values['time'] = datetime.now(utc)
        self.values['changetime'] = datetime.now(utc)

        @self.env.with_transaction(db)
        def do_insert(db):
            cursor = db.cursor()
            cursor.execute("""
            INSERT INTO subscription (%s)
                 VALUES (%s)
            """%(','.join(self.values.names()),
                    ','.join(['%s'] * len(self.values.keys()))
                ), [self.values[name] for name in self.keys()]
            )

