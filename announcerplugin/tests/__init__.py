import unittest
def suite():
    suite = unittest.TestSuite()
    suite.addTest(ticket_compate.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest="suite")
