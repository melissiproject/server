"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

import base64
import json

from django.test import TestCase
from django.test.client import Client

from piston.utils import rc
from mlscommon.entrytypes import *
from api.handlers import CellHandler

from piston.decorator import decorator


# TODO mongoengine errors should be fixed
import warnings
warnings.filterwarnings("ignore")


class AuthTestCase(TestCase):
    # def _pre_setup(self):
    #     print "Hi _pre_setup"
    #     super(TestCase, self)._pre_setup()

    def _dropdb(self):
        from pymongo.connection import Connection
        connection = Connection()
        connection.drop_database("melisi-example")

    def _fixture_setup(self):
        self._dropdb()

    def _fixture_teardown(self):
        self._dropdb()

    def auth(self, username, password):
        auth = '%s:%s' % (username, password)
        auth = 'Basic %s' % base64.encodestring(auth)
        auth = auth.strip()

        extra = {'HTTP_AUTHORIZATION' : auth}

        return extra

    def create_superuser(self):
        user = { 'username': 'admin',
                 'password': '123',
                 'email': 'admin@example.com',
                 }
        user['auth'] = self.auth(user['username'], user['password'])

        try:
            u = User.create_user(user['username'], user['password'], user['email'])
            u.is_superuser = True
            u.is_staff = True
            u.save()
        except OperationError:
            pass

        return user

    def create_user(self):
        user = { 'username': 'melisi',
                 'password': '123',
                 'email': 'melisi@example.com',
                 }
        user['auth'] = self.auth(user['username'], user['password'])

        try:
            User.create_user(user['username'], user['password'], user['email'])
        except OperationError:
            pass

        return user

    def create_anonymous(self):
        user = {'auth': {}}
        return user

@decorator
def test_multiple_users(function, self, *args, **kwargs):
    dic = function(self, *args, **kwargs)
    # Test
    for user, data in dic['users'].iteritems():
        if dic.get('setup'):
            dic['setup']()

        method = getattr(self.client, dic['method'])
        postdata = dic.get('postdata', {})

        response = method(dic['url'],
                          postdata,
                          **data['auth'])

        self.assertEqual(response.status_code, dic['response_code'][user])

        if response.status_code == 200 and 'content' in dic:
            self.assertContains(response, dic['content'])

        if dic.get('teardown'):
            dic['teardown']()


class UserTest(AuthTestCase):
    def setUp(self):
        self.username = 'testuser'
        self.password = '123'
        self.email = 'testuser@example.com'

        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': { 'username' : self.username,
                       'password' : self.password,
                       'email' : self.email,
                       'auth' : self.auth(self.username, self.password)
                       }
            }

    @test_multiple_users
    def test_create_user(self):
        def teardown():
            User.objects(username='testuser').delete()

        users = self.users.copy()
        users.pop('owner')
        dic = {
            'teardown': teardown,
            'response_code': {'user': 401,
                              'admin': 200,
                              'anonymous':200,
                              },
            'postdata': {'username':'testuser',
                         'password':'123',
                         'email':'foo@example.com'
                         },
            'method':'post',
            'url': '/api/user/',
            'users': users
            }
        return dic

    @test_multiple_users
    def test_get_user(self):
        # Prepare
        User.create_user(self.username, self.password, self.email)

        dic = {
            'response_code': {'user': 401,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'method':'get',
            'url': '/api/user/testuser/',
            'users': self.users
            }
        return dic

    @test_multiple_users
    def test_update_user(self):
        # Prepare
        def setup():
            User.create_user(self.username, self.password, self.email)

        def teardown():
            User.objects(username=self.username).delete()
            User.objects(username='usertest').delete()

        # Test
        dic = {
            'setup': setup,
            'teardown': teardown,
            'response_code': {'user': 401,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {'username':'usertest',
                         'password':'123'
                         },
            'content': 'usertest',
            'method':'put',
            'url': '/api/user/testuser/',
            'users': self.users
            }

        return dic

    @test_multiple_users
    def test_delete_user(self):
        # Prepare
        def setup():
            User.create_user(self.username, self.password, self.email)

        def teardown():
            User.objects(username=self.username).delete()

        dic = {
            'setup': setup,
            'teardown': teardown,
            'response_code': {'user': 401,
                              'admin': 204,
                              'anonymous':401,
                              'owner': 204,
                              },
            'method':'delete',
            'url': '/api/user/testuser/',
            'users': self.users
            }
        return dic
