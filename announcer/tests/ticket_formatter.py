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

from announcer.formatters.ticket import *

class TicketFormatTestCase(unittest.TestCase):
    def setUp(self):
        self.env = EnvironmentStub()
        self.out = TicketFormatter(self.env)

    def test_styles(self):
        self.assertTrue('text/html' in self.out.format_styles('email', 'ticket'))
        self.assertTrue('text/plain' in self.out.format_styles('email', 'ticket'))
        self.assertFalse('text/plain' in self.out.format_styles('email', 'wiki'))
        self.assertEqual('text/plain', self.out.alternative_style('email', 'ticket', 'text/blah'))
        self.assertEqual('text/plain', self.out.alternative_style('email', 'ticket', 'text/html'))
        self.assertEqual(None, self.out.alternative_style('email', 'ticket', 'text/plain'))
        self.assertEqual(0, len([i for i in self.out.format_styles('email', 'wiki')]))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TicketFormatTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
