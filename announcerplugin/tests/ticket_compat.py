import unittest

from trac.core import *
from trac.test import EnvironmentStub

from announcerplugin.subscribers.ticket_compat import *

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
