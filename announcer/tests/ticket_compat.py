# -*- coding: utf-8 -*-
#
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

import unittest

from trac.core import *
from trac.test import EnvironmentStub

from announcer.subscribers.ticket_compat import *

class StaticTicketSubscriberTestCase(unittest.TestCase):
    def setUp(self):
        self.env = EnvironmentStub()
        self.env.config.set('announcer', 'smtp_always_cc', 'u1, u2, u3')
        self.env.config.set('announcer', 'smtp_always_bcc', 'bu1, bu2, bu3')
        self.out = StaticTicketSubscriber(self.env)

    def test_realms(self):
        self.assertEquals(('*',), self.out.get_subscription_realms())
        self.env.config.set('announcer', 'smtp_always_cc', None)
        self.env.config.set('announcer', 'smtp_always_bcc', None)
        self.assertEquals(tuple(), self.out.get_subscription_realms())

    def test_categories(self):
        self.assertEquals(('*',), self.out.get_subscription_categories('wiki'))
        self.assertEquals(('*',), self.out.get_subscription_categories('ticket'))
        self.env.config.set('announcer', 'smtp_always_cc', None)
        self.env.config.set('announcer', 'smtp_always_bcc', None)
        self.assertEquals(tuple(), self.out.get_subscription_categories('wiki'))
        self.assertEquals(tuple(), self.out.get_subscription_categories('ticket'))

    def test_cc(self):
        subs = [s for s in self.out.get_subscriptions_for_event(None)]
        self.assertTrue(('email', None, False, 'u1') in subs)
        self.assertTrue(('email', None, False, 'u2') in subs)
        self.assertTrue(('email', None, False, 'u3') in subs)
        self.env.config.set('announcer', 'smtp_always_bcc', None)
        subs = [s for s in self.out.get_subscriptions_for_event(None)]
        self.assertTrue(('email', None, False, 'u1') in subs)
        self.assertTrue(('email', None, False, 'u2') in subs)
        self.assertTrue(('email', None, False, 'u3') in subs)

    def test_bcc(self):
        subs = [s for s in self.out.get_subscriptions_for_event(None)]
        self.assertTrue(('email', None, False, 'bu1') in subs)
        self.assertTrue(('email', None, False, 'bu2') in subs)
        self.assertTrue(('email', None, False, 'bu3') in subs)
        self.env.config.set('announcer', 'smtp_always_cc', None)
        subs = [s for s in self.out.get_subscriptions_for_event(None)]
        self.assertTrue(('email', None, False, 'bu1') in subs)
        self.assertTrue(('email', None, False, 'bu2') in subs)
        self.assertTrue(('email', None, False, 'bu3') in subs)

    def test_list_size(self):
        subs = [s for s in self.out.get_subscriptions_for_event(None)]
        self.assertEquals(6, len(subs))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(StaticTicketSubscriberTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
