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

    # def __init__(self):
    #     from pymongo.connection import Connection
    #     self.connection = Connection()
    #     self.db = connection['melisi-example']

    #     super(AuthTestCase, self).__init__()

    def _dropdb(self):
        self.connection.drop_database("melisi-example")

    def _fixture_setup(self):
        self.teardown(full=True)

    def _fixture_teardown(self):
        pass

    def teardown(self, full=False):
        map(lambda x: x.delete(), Cell.objects.all())

        # from pymongo.connection import Connection
        # self.connection = Connection()
        # self.db = self.connection['melisi-example']

        if full:
            map(lambda x: x.delete(), User.objects.all())

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

        response = method(dic['url'] % s,
                          postdata,
                          **data['auth'])

        # print response.content

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
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_create_root_cell(self):
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
    def test_create_child_cell(self):
        # Prepare
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="foo", owner=u)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
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

        dic = {
            'setup':setup,
            'teardown':self.teardown,
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

        dic = {
            'setup':setup,
            'teardown':self.teardown,
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

        dic = {
            'setup':setup,
            'teardown':self.teardown,
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
    def test_denied_update_name_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="foo", owner=u)
            c.save()
            c1 = Cell(name="bar", owner=u)
            c1.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'put',
            'url':'/api/cell/%(cell_id)s/',
            'users': self.users,
            'postdata': { 'name': 'bar' },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 400,
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

        def extra_checks():
            # do more detailed tests
            c2 = Cell.objects.get(name="bar")
            c4 = Cell.objects.get(name="child-bar")
            c3 = Cell.objects.get(name="new-root")

            self.assertEqual(c2.roots, [c3])
            self.assertEqual(c4.roots, [c2,c3])


        dic = {
            'setup':setup,
            'teardown':self.teardown,
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

        dic = {
            'setup':setup,
            'teardown':self.teardown,
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

        def extra_checks():
            self.assertEqual(Cell.objects.count(), 0)
            self.assertEqual(Droplet.objects.count(), 0)

        dic = {
            'setup':setup,
            'teardown':self.teardown,
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

        dic = {
            'setup':setup,
            'teardown':self.teardown,
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

class DropletTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_read_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="foo", owner=u)
            c.save()
            d = Droplet(name="drop", owner=u, cell=c)
            d.save()

            return { 'droplet_id': d.pk }

        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'get',
            'url':'/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'content': '%(droplet_id)s',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }
        return dic

    @test_multiple_users
    def test_create_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="bar", owner=u)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'post',
            'url': '/api/droplet/',
            'users': self.users,
            'content': '%(cell_id)s',
            'postdata': {'name':'drop',
                         'cell':'%(cell_id)s'
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_create_duplicate_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="bar", owner=u)
            c.save()
            d = Droplet(name='drop', owner=u, cell=c)
            d.save()
            return { 'cell_id': c.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'post',
            'url': '/api/droplet/',
            'users': self.users,
            'content': '%(cell_id)s',
            'postdata': {'name':'drop',
                         'cell':'%(cell_id)s'
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 400,
                              }
            }

        return dic

    @test_multiple_users
    def test_update_name_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="bar", owner=u)
            c.save()
            d = Droplet(name='drop', owner=u, cell=c)
            d.save()
            return { 'droplet_id':d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'url': '/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'content': 'newname',
            'postdata': {'name':'newname',
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_denied_update_name_droplet(self):
        """ Duplicate name """
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="bar", owner=u)
            c.save()
            d = Droplet(name='drop', owner=u, cell=c)
            d.save()
            d2 = Droplet(name='newname', owner=u, cell=c)
            d2.save()
            return { 'droplet_id':d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'url': '/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'postdata': {'name':'newname',
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 400,
                              }
            }

        return dic

    @test_multiple_users
    def test_delete_droplet(self):
        """ Duplicate name """
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="bar", owner=u)
            c.save()
            d = Droplet(name='drop', owner=u, cell=c)
            d.save()
            return { 'droplet_id':d.pk }

        def extra_checks():
            self.assertEqual(Droplet.objects.count(), 0)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'delete',
            'url': '/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'postdata': {'name':'newname',
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              },
            'checks':{'owner': extra_checks},
            }

        return dic


    @test_multiple_users
    def test_move_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="bar", owner=u)
            c.save()
            c1 = Cell(name="foo", owner=u)
            c1.save()
            d = Droplet(name='drop', owner=u, cell=c)
            d.save()
            return { 'droplet_id':d.pk, 'cell_id':c1.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'url': '/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'content': '%(cell_id)s',
            'postdata': {'cell':'%(cell_id)s',
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_denied_move_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="melisi")
            c = Cell(name="bar", owner=u)
            c.save()
            c1 = Cell(name="foo", owner=u1)
            c1.save()
            d = Droplet(name='drop', owner=u, cell=c)
            d.save()
            return { 'droplet_id':d.pk, 'cell_id':c1.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'url': '/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'content': '%(cell_id)s',
            'postdata': {'cell':'%(cell_id)s',
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 401,
                              }
            }

        return dic

class RevisionTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_read_latest_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewing file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            # create revision
            r = Revision(user=u)
            r.content.put(content)
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/latest/',
            'users': self.users,
            'content': 'created',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_read_specific_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewing file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            # create revision
            r = Revision(user=u)
            r.content.new_file()
            r.content.write(content.read())
            r.content.close()
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/1/',
            'users': self.users,
            'content': 'created',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_create_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            #rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'post',
            'url': '/api/droplet/%(droplet_id)s/revision/',
            'users': self.users,
            'content': 'created',
            'postdata': { 'number': '1',
                          'md5': md5,
                          'content': content,
                          },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_denied_create_revision(self):
        """ Invalid md5 / data combination """
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = 'foobar-fake-md5'
        content.seek(0)

        def setup():
            #rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'post',
            'url': '/api/droplet/%(droplet_id)s/revision/',
            'users': self.users,
            'postdata': { 'number': '1',
                          'md5': md5,
                          'content': content,
                          },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 400,
                              }
            }

        return dic


    @test_multiple_users
    def test_delete_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            # create revision
            r = Revision(user=u)
            r.content.put(content)
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        def extra_checks():
            d = Droplet.objects.get(name="d1")
            self.assertEqual(len(d.revisions), 0)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'delete',
            'url': '/api/droplet/%(droplet_id)s/revision/1/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              },
            'checks': {'owner': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_read_latest_revision_content(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            # create revision
            r = Revision(user=u, content=content)
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/latest/content/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              },
            }

        return dic


    @test_multiple_users
    def test_read_latest_revision_patch(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            # create revision
            r = Revision(user=u, patch=content)
            d.revisions.append(r)
            d.revisions.append(r)

            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/latest/patch/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              },
            }

        return dic


    @test_multiple_users
    def test_read_specific_revision_content(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            # create revision
            r = Revision(user=u, content=content)
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/1/content/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              },
            }

        return dic

    @test_multiple_users
    def test_read_specific_revision_patch(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            # create revision
            r = Revision(user=u, patch=content)
            d.revisions.append(r)
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/2/patch/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              },
            }

        return dic


    @test_multiple_users
    def test_update_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('123456')
        content.seek(0)
        delta = tempfile.TemporaryFile()
        delta.write('72730236410b303132333435363738390a00'.decode('HEX'))
        delta.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)
            delta.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            # create revision
            r = Revision(user=u, content=content)
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'url': '/api/droplet/%(droplet_id)s/revision/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              },
            'postdata': { 'number': '1',
                          'md5': '3749f52bb326ae96782b42dc0a97b4c1', # md5 of '0123456789'
                          'content': delta,
                          },
            'content': 'created'
            }

        return dic


    @test_multiple_users
    def test_denied_update_revision(self):
        """ Invalid md5 / data combination """
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('123456')
        content.seek(0)
        delta = tempfile.TemporaryFile()
        delta.write('72730236410b303132333435363738390a00'.decode('HEX'))
        delta.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)
            delta.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            c1 = Cell(name="c1", owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1)
            d.save()

            # create revision
            r = Revision(user=u, content=content)
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'url': '/api/droplet/%(droplet_id)s/revision/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 400,
                              },
            'postdata': { 'number': '2',
                          'md5': 'foo-bar-wrong-md5',
                          'patch': delta,
                          },
            'content': 'created'
            }

        return dic



class ShareTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com"),
            'partner': self.create_user("bar", "bar@example.com"),
            }

    @test_multiple_users
    def test_share_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            c = Cell(name="c1", owner=u)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup':setup,
            'teardown': self.teardown,
            'postdata': { 'user': 'bar',
                          'mode': 'wara',
                          },
            'response_code': { 'user': 401,
                               'admin': 401,
                               'anonymous': 401,
                               'owner': 201,
                               'partner': 401,
                               },
            'users': self.users,
            'method': 'post',
            'url': '/api/cell/%(cell_id)s/share/'
            }

        return dic

    @test_multiple_users
    def test_denied_share_cell(self):
        """ deny double share root """
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            c = Cell(name="c1", owner=u)
            s = Share(user=u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            c1 = Cell(name="c2", owner=u, roots= [c])
            c1.save()

            return { 'cell_id': c1.pk }

        dic = {
            'setup':setup,
            'teardown': self.teardown,
            'postdata': { 'user': 'bar',
                          'mode': 'wara',
                          },
            'response_code': { 'user': 401,
                               'admin': 401,
                               'anonymous': 401,
                               'owner': 400,
                               'partner': 401,
                               },
            'users': self.users,
            'method': 'post',
            'url': '/api/cell/%(cell_id)s/share/'
            }

        return dic


    @test_multiple_users
    def test_read_shares(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            c = Cell(name="c1", owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/share/',
            'response_code': { 'user': 401,
                               'admin': 401,
                               'anonymous': 401,
                               'owner': 200,
                               'partner': 401,
                               },
            'content': 'bar',
            }

        return dic

    @test_multiple_users
    def test_read_shared_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            c = Cell(name="c1", owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            c1 = Cell(name="c2", owner=u, roots=[c])
            c1.save()

            return { 'cell_id': c1.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              'partner': 200,
                              },
            'content': '%(cell_id)s'
            }

        return dic

    @test_multiple_users
    def test_read_shared_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            c = Cell(name="c1", owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            c1 = Cell(name="c2", owner=u, roots=[c])
            c1.save()

            d = Droplet(owner=u, cell=c1, name="lala")
            d.save()

            return { 'droplet_id': d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'users': self.users,
            'url': '/api/droplet/%(droplet_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              'partner': 200,
                              },
            'content': '%(droplet_id)s'
            }

        return dic

    @test_multiple_users
    def test_write_shared_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            c = Cell(name="c1", owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'users': self.users,
            'postdata': { 'name':'newname' },
            'url': '/api/cell/%(cell_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              'partner': 200,
                              },
            'content': 'newname'
            }

        return dic

    @test_multiple_users
    def test_write_shared_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            c = Cell(name="c1", owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            d = Droplet(owner=u, cell=c, name="lala")
            d.save()

            return { 'droplet_id': d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'users': self.users,
            'postdata': { 'name':'newname' },
            'url': '/api/droplet/%(droplet_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              'partner': 200,
                              },
            'content': 'newname'
            }

        return dic


    @test_multiple_users
    def test_delete_share_cell(self):
        """ delete all """
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            c = Cell(name="c1", owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            return { 'cell_id': c.pk }

        def extra_checks():
            # c = Cell.objects.get(name="c1")
            # self.assertEqual(len(c.shared_with), 0)
            pass

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'delete',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/share/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              'partner': 401,
                              },
            'checks': { 'owner' : extra_checks },
            }

        return dic

    @test_multiple_users
    def test_delete_share_user(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            c = Cell(name="c1", owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            return { 'cell_id': c.pk, 'username': u1.username }

        def extra_checks():
            c = Cell.objects.get(name="c1")
            self.assertEqual(len(c.shared_with), 0)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'delete',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/share/%(username)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              'partner': 204,
                              },
            'checks': { 'owner' : extra_checks },
            }

        return dic


    @test_multiple_users
    def test_delete_share_user2(self):
        """ User who is in shared_with list and his not owner
        tries to delete another user in shared_with list
        """
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            u2 = User.create_user("sharetest", "123", "test@example.com")
            c = Cell(name="c1", owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            s1 = Share(user = u2, mode='wara')
            c.shared_with.append(s1)
            c.save()

            return { 'cell_id': c.pk }

        def teardown():
            User.objects(username="sharetest").delete()
            self.teardown()

        def extra_checks():
            c = Cell.objects.get(name="c1")
            self.assertEqual(len(c.shared_with), 1)

        dic = {
            'setup': setup,
            'teardown': teardown,
            'method': 'delete',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/share/sharetest/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              'partner': 401,
                              },
            'checks': { 'owner' : extra_checks },
            }

        return dic

    @test_multiple_users
    def test_update_share_cell(self):
        """ update mode for user """
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            c = Cell(name="c1", owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            return { 'cell_id': c.pk }

        def extra_checks():
            c = Cell.objects.get(name="c1")
            self.assertEqual(len(c.shared_with), 1)
            self.assertEqual(c.shared_with[0].mode, 'wnra')

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'post',
            'users': self.users,
            'postdata': { 'user':'bar',
                          'mode':'wnra'
                          },
            'url': '/api/cell/%(cell_id)s/share/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 201,
                              'partner': 401,
                              },
            'checks': { 'owner' : extra_checks },
            }

        return dic
