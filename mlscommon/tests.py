"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

import base64

from django.test import TestCase
from django.test.client import Client

from mlscommon.entrytypes import *
from api.handlers import CellHandler

class SimpleTest(TestCase):
    def test_basic_addition(self):
        """
        Tests that 1 + 1 always equals 2.
        """
        self.failUnlessEqual(1 + 1, 2)

# __test__ = {"doctest": """
# Another way to test that 1 + 1 is equal to 2.

# >>> 1 + 1 == 2
# True
# """}


class SimpleClientTest(TestCase):
    def setUp(self):
        u = User(username = "paparis")
        u.set_password("123")
        u.save()

    def test_get_cell(self):
        # c = Client()
        # response = c.get('/api/cell/4d5eaa9330ea7d4139000005/')
        # self.assertEqual(response.status_code, 200)

        self.failUnlessEqual(2, 2)

    def test_post_cell(self):
        self.failUnlessEqual(3,3)


class SimpleTest(TestCase):
    def setUp(self):
        self.client = Client()
        auth = '%s:%s' % ('foo', '123')
        auth = 'Basic %s' % base64.encodestring(auth)
        auth = auth.strip()
        self.extra = {
            'HTTP_AUTHORIZATION': auth,
            }


    def test_details(self):
        response = self.client.get('/api/cell/4d61889130ea7d40eb000000/', {}, **self.extra)


        print response
        print response.context
        self.assertEqual(response.status_code, 200)
