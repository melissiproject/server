import base64

from django.test import TestCase
from django.test.client import Client

from piston.decorator import decorator

from models import *

class AuthTestCase(TestCase):
    def _fixture_setup(self):
        pass

    def _fixture_teardown(self):
        self.teardown(full=True)

    def teardown(self, full=False):
        if full:
            Droplet.objects.all().delete()
            Cell.objects.all().delete()
            User.objects.all().delete()
        else:
            Droplet.objects.all().delete()
            Cell.objects.all().exclude(name='melissi',
                                       parent=None).delete()

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
            u = User.objects.create_user(user['username'], user['email'], user['password'])
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
            u = User.objects.create_user(user['username'], user['email'], user['password'])
        except OperationError:
            u = None

        user['object'] = u

        return user


    def create_anonymous(self):
        user = {'auth': {}}
        return user


@decorator
def test_multiple_users(function, self, *args, **kwargs):
    dic = function(self, *args, **kwargs)
    # Test
    for user, data in dic['users'].iteritems():
        print "Testing", user
        s = {}
        if dic.get('setup'):
            s = dic['setup']() or {}

        method = getattr(self.client, dic['method'])

        postdata = {}
        for key, value in dic.get('postdata', {}).iteritems():
            if isinstance(dic['postdata'][key], basestring):
                postdata[key] = value % s
            else:
                postdata[key] = value

        print "url", dic['url'] % s

        response = method(dic['url'] % s,
                          postdata,
                          **data['auth'])

        print response.content

        self.assertEqual(response.status_code, dic['response_code'][user])

        if response.status_code == 200 and 'content' in dic:
            self.assertContains(response, dic['content'] % s)

        if dic.get('checks') and dic['checks'].get(user):
            dic['checks'][user](response)

        if dic.get('teardown'):
            dic['teardown']()

class CellTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_create_root_cell(self):
        """
        Test the creation of a root cell (i.e. a cell without parents)
        """
        dic = {
            'teardown': self.teardown,
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
    def test_deny_root_cell(self):
        """
        Test the creation of a root cell (i.e. a cell without parents)
        with a name that already exists
        """
        dic = {
            'teardown': self.teardown,
            'response_code': {'user': 400,
                              'admin': 400,
                              'anonymous':401,
                              'owner': 400,
                              },
            'postdata': {
                'name':'melissi',
                },
            'method':'post',
            'url': '/api/cell/',
            'users': self.users
            }

        return dic

    @test_multiple_users
    def test_create_cell(self):
        """
        Test the creation of a cell (i.e. a cell without parents)
        """
        def setup():
            return {'owner_id': self.users['owner']['object'].id,
                    'owner_root_id': self.users['owner']['object'].cell_set.all()[0].id}

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                'name':'test',
                'parent': '%(owner_root_id)s',
                },
            'content': 'test',
            'method':'post',
            'url': '/api/cell/',
            'users': self.users
            }

        return dic


    @test_multiple_users
    def test_update_cell_name(self):
        """
        Test the update of a cell by changing name
        """
        def setup():
            u = self.users['owner']['object']
            c = Cell(name="test",
                     owner=u,
                     parent = u.cell_set.all()[0],
                     )
            c.save()
            return {'c_id': c.id }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                'name':'test2',
                'number':2,
                },
            'content': 'test2',
            'method':'put',
            'url': '/api/cell/%(c_id)s/',
            'users': self.users
            }

        return dic


    @test_multiple_users
    def test_update_cell_parent(self):
        """
        Test the update of a cell by changing parent
        """
        def setup():
            u = self.users['owner']['object']
            c = Cell(name="test",
                     owner=u,
                     )
            c.save()
            return {'c_id': c.id, 'parent_id': u.cell_set.all()[0].id}

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                'parent':'%(parent_id)s',
                'number':2,
                },
            'content': '%(parent_id)s',
            'method':'put',
            'url': '/api/cell/%(c_id)s/',
            'users': self.users
            }

        return dic

    @test_multiple_users
    def test_update_cell_parent_name(self):
        """
        Test the update of a cell by changing parent and name
        """
        def setup():
            u = self.users['owner']['object']
            c = Cell(name="test",
                     owner=u,
                     )
            c.save()
            return {'c_id': c.id, 'parent_id': u.cell_set.all()[0].id}

        def extra_checks(response):
            c = Cell.objects.get(name="test2",
                                 owner=self.users['owner']['object'])
            self.assertEqual(c.parent,
                             self.users['owner']['object'].cell_set.all()[0])

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                'name': 'test2',
                'parent':'%(parent_id)s',
                'number':2,
                },
            'content': '%(parent_id)s',
            'method':'put',
            'url': '/api/cell/%(c_id)s/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic


    @test_multiple_users
    def test_delete_cell(self):
        """
        Test the deletion of a cell (recursive)
        """
        def setup():
            u = self.users['owner']['object']
            c = Cell(name="test",
                     owner=u,
                     )
            c.save()

            c1 = Cell(name="test-1",
                      owner=u,
                      parent = c)
            c1.save()

            d1 = Droplet(name="drop",
                         owner=u,
                         cell=c1)
            d1.save()

            return {'c_id': c.id }

        def extra_checks(response):
            self.assertEqual(Cell.objects.filter(deleted=True).count(), 2)
            self.assertEqual(Droplet.objects.filter(deleted=True).count(), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 204,
                              },
            'postdata': {
                },
            'method':'delete',
            'url': '/api/cell/%(c_id)s/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic


    @test_multiple_users
    def test_read_cell(self):
        """
        Test the read of a cell
        """
        def setup():
            u = self.users['owner']['object']
            c = Cell(name="test",
                     owner=u,
                     )
            c.save()

            return {'c_id': c.id }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                },
            'method':'get',
            'url': '/api/cell/%(c_id)s/',
            'users': self.users,
            }

        return dic


    @test_multiple_users
    def test_update_cell_parent_denied(self):
        """
        Test the update of a cell by changing parent to a parent that
        you don't have permissin

        u1 tries to save into u 's folder
        """
        def setup():
            u = self.users['owner']['object']
            u1 = self.users['user']['object']
            c = Cell(name="test",
                     owner=u1,
                     )
            c.save()

            return {'c_id': c.id, 'parent_id': u.cell_set.all()[0].id}


        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                'parent':'%(parent_id)s',
                'number':2,
                },
            'method':'put',
            'url': '/api/cell/%(c_id)s/',
            'users': self.users,
            }

        return dic

