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

    def create_user(self, username='melisi', email='melisi@example.com'):
        user = { 'username': username,
                 'password': '123',
                 'email': email,
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
        # print "Testing", user
        if dic.get('setup'):
            s = dic['setup']() or {}
        else:
            s = {}

        method = getattr(self.client, dic['method'])

        postdata = {}
        for key, value in dic.get('postdata', {}).iteritems():
            postdata[key] = value % s

        response = method(dic['url'] % s,
                          postdata,
                          **data['auth'])

        self.assertEqual(response.status_code, dic['response_code'][user])

        if response.status_code == 200 and 'content' in dic:
            self.assertContains(response, dic['content'] % s)

        if dic.get('checks') and dic['checks'].get(user):
            dic['checks'][user]()

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


class CellTest(AuthTestCase):
    def setUp(self):
        self.username = 'testuser'
        self.password = '123'
        self.email = 'testuser@example.com'

        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_create_root_cell(self):
        def teardown():
            Cell.objects(name="test").delete()

        dic = {
            'teardown': teardown,
            'response_code': {'user': 200,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                'name':'test',
                },
            'content': 'test',
            'method':'post',
            'url': '/api/cell/',
            'users': self.users
            }

        return dic

    @test_multiple_users
    def test_create_child_cell(self):
        # Prepare
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="foo", owner=u)
            c.save()

            return { 'cell_id': c.pk }

        def teardown():
            Cell.objects(name="foo").delete()
            Cell.objects(name="test").delete()

        dic = {
            'setup': setup,
            'teardown': teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner':200,
                              },
            'postdata': {
                'name':'test',
                'parent':'%(cell_id)s',
                },
            'content': 'test',
            'method':'post',
            'url': '/api/cell/',
            'users': self.users
            }

        return dic


    @test_multiple_users
    def test_create_duplicate_child_cell(self):
        def setup():
            # Prepare
            u = User.objects.get(username="foo")
            # create root cell
            c1 = Cell(name="foo", owner=u)
            c1.save()
            # create child cell
            c2 = Cell(name='test', owner=u, roots=[c1])
            c2.save()

            return { 'cell_id': c1.pk }

        def teardown():
            Cell.objects(name="foo").delete()
            Cell.objects(name="test").delete()


        dic = {
            'setup':setup,
            'teardown':teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner':400,
                              },
            'postdata': {
                'name':'test',
                'parent': "%(cell_id)s"
                },
            'content': 'test',
            'method':'post',
            'url': '/api/cell/',
            'users': self.users
            }

        return dic

    @test_multiple_users
    def test_read_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="foo", owner=u)
            c.save()

            return { 'cell_id': c.pk }

        def teardown():
            Cell.objects(name="foo").delete()

        dic = {
            'setup':setup,
            'teardown':teardown,
            'method':'get',
            'url':'/api/cell/%(cell_id)s/',
            'users': self.users,
            'content': '%(cell_id)s',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }
        return dic

    @test_multiple_users
    def test_update_name_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="foo", owner=u)
            c.save()

            return { 'cell_id': c.pk }

        def teardown():
            Cell.objects(name="foo").delete()

        dic = {
            'setup':setup,
            'teardown':teardown,
            'method':'put',
            'url':'/api/cell/%(cell_id)s/',
            'users': self.users,
            'postdata': { 'name': 'bar' },
            'content': 'bar',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }
        return dic

    @test_multiple_users
    def test_move_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            c1 = Cell(name="foo", owner=u)
            c1.save()

            c2 = Cell(name="bar", owner=u, roots=[c1])
            c2.save()

            c3 = Cell(name="new-root", owner=u)
            c3.save()

            c4 = Cell(name="child-bar", owner=u, roots=[c2,c1])
            c4.save()

            return { 'c2': c2.pk, 'c3': c3.pk }

        def teardown():
            Cell.objects(name="child-bar").delete()
            Cell.objects(name="bar").delete()
            Cell.objects(name="new-root").delete()
            Cell.objects(name="foo").delete()

        def extra_checks():
            # do more detailed tests
            c2 = Cell.objects.get(name="bar")
            c4 = Cell.objects.get(name="child-bar")
            c3 = Cell.objects.get(name="new-root")

            self.assertEqual(c2.roots, [c3])
            self.assertEqual(c4.roots, [c2,c3])


        dic = {
            'setup':setup,
            'teardown':teardown,
            'method':'put',
            'url':'/api/cell/%(c2)s/',
            'users': self.users,
            'postdata': { 'parent': '%(c3)s' },
            'content': '%(c3)s',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              },
            'checks' : { 'owner': extra_checks }
            }
        return dic

    @test_multiple_users
    def test_denied_move_cell(self):
        """ Try to move a cell into another cell without permission """
        def setup():
            u1 = User.objects.get(username="foo")
            u2 = User.objects.get(username="melisi")
            c1 = Cell(name="foo", owner=u1)
            c1.save()

            c2 = Cell(name="bar", owner=u1, roots=[c1])
            c2.save()

            c3 = Cell(name="new-root", owner=u2)
            c3.save()

            c4 = Cell(name="child-bar", owner=u1, roots=[c2,c1])
            c4.save()

            return { 'c2': c2.pk, 'c3': c3.pk }

        def teardown():
            Cell.objects(name="child-bar").delete()
            Cell.objects(name="bar").delete()
            Cell.objects(name="new-root").delete()
            Cell.objects(name="foo").delete()

        dic = {
            'setup':setup,
            'teardown':teardown,
            'method':'put',
            'url':'/api/cell/%(c2)s/',
            'users': self.users,
            'postdata': { 'parent': '%(c3)s' },
            'content': '%(c3)s',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 401,
                              },
            }
        return dic

    @test_multiple_users
    def test_delete_cascade(self):
        """ Delete a cell and check that all children cells and
        droplets have been deleted """

        def setup():
            u = User.objects.get(username="foo")
            c1 = Cell(name="root", owner=u)
            c1.save()
            c2 = Cell(name="child1", owner=u, roots=[c1])
            c2.save()
            c3 = Cell(name="child2", owner=u, roots=[c2,c1])
            c3.save()
            d1 = Droplet(name="drop1", owner=u, cell=c1)
            d1.save()
            d2 = Droplet(name="drop2", owner=u, cell=c3)
            d2.save()
            return { 'cell_id': c1 }

        def teardown():
            Droplet.drop_collection()
            Cell.drop_collection()

        def extra_checks():
            self.assertEqual(Cell.objects.count(), 0)
            self.assertEqual(Droplet.objects.count(), 0)

        dic = {
            'setup':setup,
            'teardown':teardown,
            'method':'delete',
            'url':'/api/cell/%(cell_id)s/',
            'users':self.users,
            'response_code': {'user': 401,
                              'admin':401,
                              'owner':204,
                              'anonymous':401
                              },
            'checks':{'owner':extra_checks}
            }

        return dic

    @test_multiple_users
    def test_delete_cell(self):
        # Prepare
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="foo", owner=u)
            c.save()

            return { 'cell_id': c.pk }

        def teardown():
            Cell.objects(name="foo").delete()

        dic = {
            'setup':setup,
            'teardown':teardown,
            'method':'delete',
            'url':'/api/cell/%(cell_id)s/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              }
            }
        return dic
