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

__all__ = ['Subscription', 'SubscriptionAttribute']

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
            int(priority), subscription['adverb'],
            subscription['class']))

    @classmethod
    def delete(cls, env, rule_id, db=None):
        @env.with_transaction(db)
        def do_delete(db):
            cursor = db.cursor()
            cursor.execute("""
            SELECT sid, distributor
              FROM subscription
             WHERE id=%s
            """, (rule_id,))
            sid, distributor = cursor.fetchone()
            cursor.execute("""
            DELETE FROM subscription
                  WHERE id = %s
            """, (rule_id,))
            i = 1
            for s in cls.find_by_sid_and_distributor(env, sid, distributor, db):
                s['priority'] = i
                s._update_priority(db)
                i += 1

    @classmethod
    def move(cls, env, rule_id, priority, db=None):
        env.log.debug('moving %s to %s'%(rule_id, priority))
        @env.with_transaction(db)
        def do_delete(db):
            cursor = db.cursor()
            cursor.execute("""
            SELECT sid, distributor
              FROM subscription
             WHERE id=%s
            """, (rule_id,))
            sid, distributor = cursor.fetchone()
            if priority > len(cls.find_by_sid_and_distributor(env, sid, distributor, db)):
                return
            i = 1
            for s in cls.find_by_sid_and_distributor(env, sid, distributor, db):
                env.log.error("testing rule: %s, i: %s"%(s['class'], i))
                if int(s['id']) == int(rule_id):
                    env.log.error("rule_id match")
                    s['priority'] = priority
                    s._update_priority(db)
                    i -= 1
                elif i == priority:
                    env.log.error("priority match")
                    i += 1
                    env.log.error("rule: %s, i: %s"%(s['class'], i))
                    s['priority'] = i
                    s._update_priority(db)
                else:
                    env.log.error("no match")
                    env.log.error("rule: %s, i: %s"%(s['class'], i))
                    s['priority'] = i
                    s._update_priority(db)
                i+=1

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
                sub['priority'] = int(i[5])
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
                sub['priority'] = int(i[5])
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
                sub['priority'] = int(i[5])
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
            int(self.values['priority']),
            self.values['adverb']
        )

    def _update_priority(self, db=None):
        @self.env.with_transaction(db)
        def do_update(db):
            cursor = db.cursor()
            cursor.execute("""
            UPDATE subscription
               SET changetime=datetime(),
                   priority=%s
             WHERE id=%s
            """, (int(self.values['priority']), self.values['id']))

class SubscriptionAttribute(object):

    fields = ('id', 'sid', 'class', 'realm', 'target')

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
    def add(cls, env, sid, klass, realm, attributes, db=None):
        """id and priority overwritten."""
        @env.with_transaction(db)
        def do_insert(db):
            cursor = db.cursor()
            for a in attributes:
                cursor.execute("""
                INSERT INTO subscription_attribute
                            (sid, class, realm, target)
                     VALUES (%s, %s, %s, %s)
                """, (sid, klass, realm, a))

    @classmethod
    def delete(cls, env, attribute_id, db=None):
        @env.with_transaction(db)
        def do_delete(db):
            cursor = db.cursor()
            cursor.execute("""
            DELETE FROM subscription_attribute
                  WHERE id = %s
            """, (attribute_id,))

    @classmethod
    def delete_by_sid_and_class(cls, env, sid, klass, db=None):
        @env.with_transaction(db)
        def do_delete(db):
            cursor = db.cursor()
            cursor.execute("""
            DELETE FROM subscription_attribute
                  WHERE sid = %s
                    AND class = %s
            """, (sid, klass))

    @classmethod
    def delete_by_sid_class_and_target(cls, env, sid, klass, target, db=None):
        @env.with_transaction(db)
        def do_delete(db):
            cursor = db.cursor()
            cursor.execute("""
            DELETE FROM subscription_attribute
                  WHERE sid = %s
                    AND class = %s
                    AND target = %s
            """, (sid, klass, target))

    @classmethod
    def delete_by_class_realm_and_target(cls, env, klass, realm, target, db=None):
        @env.with_transaction(db)
        def do_delete(db):
            cursor = db.cursor()
            cursor.execute("""
            DELETE FROM subscription_attribute
                  WHERE realm = %s
                    AND class = %s
                    AND target = %s
            """, (realm, klass, target))

    @classmethod
    def find_by_sid_and_class(cls, env, sid, klass, db=None):
        attrs = []

        @env.with_transaction(db)
        def do_select(db):
            cursor = db.cursor()
            cursor.execute("""
              SELECT id, sid, class, realm, target
                FROM subscription_attribute
               WHERE sid=%s
                 AND class=%s
            ORDER BY target
            """, (sid,klass))
            for i in cursor.fetchall():
                attr = SubscriptionAttribute(env)
                attr['id'] = i[0]
                attr['sid'] = i[1]
                attr['class'] = i[2]
                attr['realm'] = i[3]
                attr['target'] = i[4]
                attrs.append(attr)

        return attrs

    @classmethod
    def find_by_sid_class_and_target(cls, env, sid, klass, target, db=None):
        attrs = []

        @env.with_transaction(db)
        def do_select(db):
            cursor = db.cursor()
            cursor.execute("""
              SELECT id, sid, class, realm, target
                FROM subscription_attribute
               WHERE sid=%s
                 AND class=%s
                 AND target=%s
            ORDER BY target
            """, (sid,klass,target))
            for i in cursor.fetchall():
                attr = SubscriptionAttribute(env)
                attr['id'] = i[0]
                attr['sid'] = i[1]
                attr['class'] = i[2]
                attr['realm'] = i[3]
                attr['target'] = i[4]
                attrs.append(attr)

        return attrs

    @classmethod
    def find_by_sid_class_realm_and_target(cls, env, sid, klass, realm, target, db=None):
        attrs = []

        @env.with_transaction(db)
        def do_select(db):
            cursor = db.cursor()
            cursor.execute("""
              SELECT id, sid, class, realm, target
                FROM subscription_attribute
               WHERE sid=%s
                 AND class=%s
                 AND realm=%s
                 AND target=%s
            ORDER BY target
            """, (sid,klass,realm,target))
            for i in cursor.fetchall():
                attr = SubscriptionAttribute(env)
                attr['id'] = i[0]
                attr['sid'] = i[1]
                attr['class'] = i[2]
                attr['realm'] = i[3]
                attr['target'] = i[4]
                attrs.append(attr)

        return attrs

    @classmethod
    def find_by_class_realm_and_target(cls, env, klass, realm, target, db=None):
        attrs = []

        @env.with_transaction(db)
        def do_select(db):
            cursor = db.cursor()
            cursor.execute("""
                SELECT id, sid, class, realm, target
                  FROM subscription_attribute
                 WHERE class=%s
                   AND realm=%s
                   AND target=%s
            """, (klass, realm, target))
            for i in cursor.fetchall():
                attr = SubscriptionAttribute(env)
                attr['id'] = i[0]
                attr['sid'] = i[1]
                attr['class'] = i[2]
                attr['realm'] = i[3]
                attr['target'] = i[4]
                attrs.append(attr)

        return attrs

    @classmethod
    def find_by_class_and_realm(cls, env, klass, realm, db=None):
        attrs = []

        @env.with_transaction(db)
        def do_select(db):
            cursor = db.cursor()
            cursor.execute("""
                SELECT id, sid, class, realm, target
                  FROM subscription_attribute
                 WHERE class=%s
                   AND realm=%s
            """, (klass, realm))
            for i in cursor.fetchall():
                attr = SubscriptionAttribute(env)
                attr['id'] = i[0]
                attr['sid'] = i[1]
                attr['class'] = i[2]
                attr['realm'] = i[3]
                attr['target'] = i[4]
                attrs.append(attr)

        return attrs
