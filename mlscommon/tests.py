import base64
import tempfile
import json
import time
from datetime import datetime, timedelta

from django.test import TestCase
from django.test.client import Client
from django.core.files import File

from piston.decorator import decorator

from models import *

def make_droplet(*args, **kwargs):
    """
    Support function to easily create droplets with content
    """
    f = tempfile.NamedTemporaryFile()
    f.write('12345')
    f.seek(0)

    d = Droplet(name=kwargs['name'],
                owner=kwargs['owner'],
                cell=kwargs['cell'],
                content_sha256='5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5',
                )
    d.content.save(kwargs['name'], File(f))
    d.save()

    f.close()

    return d

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
            u = None

        user['object'] = u

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

        # print "url", dic['url'] % s

        response = method(dic['url'] % s,
                          postdata,
                          **data['auth'])

        # print response.content

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
        you don't have permission

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
                              'owner': 401,
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

class DropletTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    # @test_multiple_users
    # def test_create_droplet(self):
    #     pass

    @test_multiple_users
    def test_rename_droplet(self):
        """
        Test renaming of a droplet
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]

            d = make_droplet(owner=u, name="test", cell=c)

            return {'d_id': d.id }

        def extra_checks(response):
            self.assertEqual(Droplet.objects.filter(name="bar").count(), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                "name":"bar",
                "number":2,
                },
            'method':'post',
            'url': '/api/droplet/%(d_id)s/revision/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_move_droplet(self):
        """
        Test moving of a droplet
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]

            c1 = Cell(name="new_cell",
                     owner=u,
                     parent=c
                     )
            c1.save()
            d = make_droplet(owner=u, name="test", cell=c)

            return {'d_id': d.id, 'c1_id':c1.id }

        def extra_checks(response):
            c = Cell.objects.get(name="new_cell")
            self.assertEqual(Droplet.objects.filter(cell=c).count(), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                "cell":"%(c1_id)s",
                "number":2,
                },
            'method':'post',
            'url': '/api/droplet/%(d_id)s/revision/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_move_droplet_denied(self):
        """
        Try to move droplet into a cell without permission
        """
        def setup():
            u = self.users['owner']['object']
            u1 = self.users['user']['object']

            u_c = u.cell_set.all()[0]

            u1_c = u1.cell_set.all()[0]
            u1_c1 = Cell(name="new_cell",
                     owner=u1,
                     parent=u1_c
                     )
            u1_c1.save()

            d = make_droplet(owner=u, name="test", cell=u_c)

            return {'d_id': d.id, 'c1_id':u1_c1.id }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 401,
                              },
            'postdata': {
                "cell":"%(c1_id)s",
                "number":2,
                },
            'method':'post',
            'url': '/api/droplet/%(d_id)s/revision/',
            'users': self.users,
            }

        return dic

    @test_multiple_users
    def test_move_rename_droplet(self):
        """
        Test moving and renaming of a droplet
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]

            c1 = Cell(name="new_cell",
                     owner=u,
                     parent=c
                     )
            c1.save()
            d = make_droplet(owner=u, name="test", cell=c)

            return {'d_id': d.id, 'c1_id':c1.id }

        def extra_checks(response):
            c = Cell.objects.get(name="new_cell")
            self.assertEqual(Droplet.objects.filter(name="bar", cell=c).count(), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                "name":"bar",
                "cell":"%(c1_id)s",
                "number":2,
                },
            'method':'post',
            'url': '/api/droplet/%(d_id)s/revision/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic


    @test_multiple_users
    def test_new_content_droplet(self):
        """
        Test posting new content to a droplet
        """
        content = tempfile.NamedTemporaryFile()
        content.write('56789')

        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]

            d = make_droplet(owner=u, name="test", cell=c)

            content.seek(0)
            return {'d_id': d.id}

        def extra_checks(response):
            d = Droplet.objects.get(name="test")
            self.assertEqual(d.content.read(), '56789')
            self.assertEqual(d.content_sha256, 'f76043a74ec33b6aefbb289050faf7aa8d482095477397e3e63345125d49f527')


        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                "content":content,
                "content_sha256":'f76043a74ec33b6aefbb289050faf7aa8d482095477397e3e63345125d49f527',
                "number":2,
                },
            'method':'post',
            'url': '/api/droplet/%(d_id)s/revision/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_revision_conflict(self):
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]

            d = make_droplet(owner=u, name="test", cell=c)
            r = DropletRevision(name="bar",
                                number=2,
                                resource=u.userresource_set.all()[0])
            d.dropletrevision_set.add(r)

            return {'d_id': d.id }

        def extra_checks(response):
            d = Droplet.objects.get(name="foo")
            d1 = Droplet.objects.get(name="bar")
            self.assertNotEqual(d, d1)
            self.assertEqual(d.dropletrevision_set.count(), 2)
            self.assertEqual(d1.dropletrevision_set.count(), 2)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                'number':2,
                'name': 'foo'
                },
            'method':'post',
            'url': '/api/droplet/%(d_id)s/revision/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic


    @test_multiple_users
    def test_delete_only_revision_droplet(self):
        """
        Test the deletion of only revision of a droplet. Must be denied
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]

            d = make_droplet(owner=u, name="test", cell=c)

            return {'d_id': d.id }

        def extra_checks(response):
            self.assertEqual(Droplet.objects.filter(name="test").count(), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 400,
                              },
            'postdata': {
                },
            'method':'delete',
            'url': '/api/droplet/%(d_id)s/revision/1/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic


    @test_multiple_users
    def test_delete_revision_droplet(self):
        """
        Test the deletion of a cell (recursive)
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]

            d = make_droplet(owner=u, name="test", cell=c)
            r = DropletRevision(name="bar",
                                number=2,
                                resource=u.userresource_set.all()[0])
            d.dropletrevision_set.add(r)

            return {'d_id': d.id }

        def extra_checks(response):
            self.assertEqual(Droplet.objects.filter(name="test").count(), 1)

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
            'url': '/api/droplet/%(d_id)s/revision/2/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_delete_droplet(self):
        """
        Test the deletion of a cell (recursive)
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]

            d = make_droplet(owner=u, name="test", cell=c)

            return {'d_id': d.id }

        def extra_checks(response):
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
            'url': '/api/droplet/%(d_id)s/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_read_droplet(self):
        """
        Test the read of a droplet
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]

            d = make_droplet(owner=u, name="test", cell=c)

            return {'d_id': d.id }

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
            'url': '/api/droplet/%(d_id)s/',
            'users': self.users,
            }

        return dic

class ShareTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_create_share(self):
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]
            c1 = Cell(owner=u,
                      parent=c,
                      name="foo")
            c1.save()

            return {'c1_id': c1.id, 'u_id':self.users['user']['object'].id }

        def extra_checks(response):
            c = Cell.objects.get(name="foo")
            self.assertEqual(c.share_set.count(), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 201,
                              },
            'postdata': {
                'mode':1,
                },
            'method':'post',
            'url': '/api/cell/%(c1_id)s/share/%(u_id)s/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_update_share(self):
        """
        Update share mode
        User can update his own mode
        Owner can update user's mode
        Admin is in the share but must fail to update user's mode
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]
            c1 = Cell(owner=u,
                      parent=c,
                      name="foo")
            c1.save()

            c1.share_set.add(Share(user=self.users['user']['object'],
                                   mode=1))
            c1.share_set.add(Share(user=self.users['admin']['object'],
                                   mode=1))
            return {'c1_id': c1.id, 'u_id':self.users['user']['object'].id }

        def extra_checks(response):
            c = Cell.objects.get(name="foo")
            self.assertEqual(c.share_set.count(), 2)
            self.assertEqual(c.share_set.get(user=self.users['user']['object']).mode, 2)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 201,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 201,
                              },
            'postdata': {
                'mode':2,
                },
            'method':'post',
            'url': '/api/cell/%(c1_id)s/share/%(u_id)s/',
            'users': self.users,
            'checks' : { 'owner': extra_checks,
                         'user':  extra_checks}
            }

        return dic


    @test_multiple_users
    def test_delete_all_shares(self):
        """
        Delete all shares
        """

        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]
            c1 = Cell(owner=u,
                      parent=c,
                      name="foo")
            c1.save()

            c1.share_set.add(Share(user=self.users['user']['object'],
                                   mode=1))
            c1.share_set.add(Share(user=self.users['admin']['object'],
                                   mode=1))
            return {'c1_id': c1.id }

        def extra_checks(response):
            c = Cell.objects.get(name="foo")
            self.assertEqual(c.share_set.count(), 0)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 204,
                              },
            'postdata': {
                'mode':2,
                },
            'method':'delete',
            'url': '/api/cell/%(c1_id)s/share/',
            'users': self.users,
            'checks' : { 'owner': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_delete_one_share(self):
        """
        Delete user's share
        Owner must be able to do it
        Admin is in the share but shouldn't be able
        User must be to delete himself
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]
            c1 = Cell(owner=u,
                      parent=c,
                      name="foo")
            c1.save()

            c1.share_set.add(Share(user=self.users['user']['object'],
                                   mode=1))
            c1.share_set.add(Share(user=self.users['admin']['object'],
                                   mode=1))
            return {'c1_id': c1.id, 'u_id':self.users['user']['object'].id }

        def extra_checks(response):
            c = Cell.objects.get(name="foo")
            self.assertEqual(c.share_set.filter(user=self.users['user']['object']).count(), 0)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 204,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 204,
                              },
            'postdata': {
                'mode':2,
                },
            'method':'delete',
            'url': '/api/cell/%(c1_id)s/share/%(u_id)s/',
            'users': self.users,
            'checks' : { 'owner': extra_checks,
                         'user': extra_checks}
            }

        return dic

    @test_multiple_users
    def test_read_share(self):
        """
        Read shares of a cell
        """
        def setup():
            u = self.users['owner']['object']
            c = u.cell_set.all()[0]
            c1 = Cell(owner=u,
                      parent=c,
                      name="foo")
            c1.save()

            c1.share_set.add(Share(user=self.users['user']['object'],
                                   mode=1))

            return {'c1_id': c1.id }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 200,
                              'admin': 401,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                },
            'method':'get',
            'url': '/api/cell/%(c1_id)s/share/',
            'users': self.users,
            }

        return dic

    # @test_multiple_users
    # def test_recursive_share_cell(self):
    #     """
    #     Test recursive share cell
    #     """
    #     def setup():
    #         user_tza = User.objects.get_or_create(username="tza", email="tza@example.com")[0]
    #         owner = self.users['owner']['object']
    #         user = self.users['user']['object']

    #         owner_root = owner.cell_set.all()[0]
    #         user_root = user.cell_set.all()[0]

    #         c0 = Cell(name='0', owner=owner, parent=owner_root)
    #         c0.save()

    #         c1 = Cell(name='1', owner=user, parent=user_root)
    #         c1.save()
    #         c1.share_set.add(Share(mode=1, user=owner, parent=c0))

    #         return { 'u_id': user_tza.id, 'cell_id': c0.id }

    #     def extra_checks(response):
    #         c = Cell.objects.get(name='1')
    #         self.assertEqual(c.share_set.count(), 2)

    #         c1 = Cell.objects.get(name='0')
    #         self.assertEqual(c1.share_set.count(), 0)

    #     dic = {
    #         'setup':setup,
    #         'teardown': self.teardown,
    #         'postdata': {
    #             'user': '%(u_id)s',
    #             'mode': 1,
    #             },
    #         'response_code': { 'user': 401,
    #                            'admin': 401,
    #                            'anonymous': 401,
    #                            'owner': 201,
    #                            },
    #         'users': self.users,
    #         'method': 'post',
    #         'url': '/api/cell/%(cell_id)s/share/%(u_id)s/',
    #         'checks': {'owner': extra_checks }
    #         }

    #     return dic

class StatusTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_read_status(self):
        """
        Read status of user, all entries
        """
        def setup():
            owner = self.users['owner']['object']
            user = self.users['user']['object']

            c = owner.cell_set.all()[0]
            c1 = Cell(owner=owner,
                      parent=c,
                      name="foo")
            c1.save()
            c1.share_set.add(Share(user=user, mode=1))
            d = make_droplet(owner=owner, cell=c1, name="foo")
            d.save()

            c2 = Cell(owner=user,
                      parent=user.cell_set.all()[0],
                      name="bar")
            c2.save()
            d1 = make_droplet(owner=owner, cell=c2, name="foo1")
            d1.save()

            return {'c1_id': c1.id }

        def extra_checks(response):
            response = json.loads(response.content)
            self.assertEqual(len(response['reply']['cells']), 3)
            self.assertEqual(len(response['reply']['droplets']), 2)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 200,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                },
            'method':'get',
            'url': '/api/status/',
            'users': self.users,
            'checks' : { 'user': extra_checks }
            }

        return dic


    @test_multiple_users
    def test_read_status_all(self):
        """
        Read status of user, all entries
        Same test as test_read_status
        Using alternative url /api/status/all/
        """
        def setup():
            owner = self.users['owner']['object']
            user = self.users['user']['object']

            c = owner.cell_set.all()[0]
            c1 = Cell(owner=owner,
                      parent=c,
                      name="foo")
            c1.save()
            c1.share_set.add(Share(user=user, mode=1))
            d = make_droplet(owner=owner, cell=c1, name="foo")
            d.save()

            c2 = Cell(owner=user,
                      parent=user.cell_set.all()[0],
                      name="bar")
            c2.save()
            d1 = make_droplet(owner=owner, cell=c2, name="foo1")
            d1.save()

            return {'c1_id': c1.id }

        def extra_checks(response):
            response = json.loads(response.content)
            self.assertEqual(len(response['reply']['cells']), 3)
            self.assertEqual(len(response['reply']['droplets']), 2)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 200,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                },
            'method':'get',
            'url': '/api/status/all/',
            'users': self.users,
            'checks' : { 'user': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_read_status_timestamp(self):
        """
        Read status of user, with timestamp
        """
        def setup():
            owner = self.users['owner']['object']
            user = self.users['user']['object']

            c = owner.cell_set.all()[0]
            c1 = Cell(owner=owner,
                      parent=c,
                      name="foo")
            c1.save()
            c1.share_set.add(Share(user=user, mode=1))
            d = make_droplet(owner=owner, cell=c1, name="foo")
            d.save()

            time.sleep(1)
            c2 = Cell(owner=user,
                      parent=user.cell_set.all()[0],
                      name="bar")
            c2.save()
            d1 = make_droplet(owner=owner, cell=c2, name="foo1")
            d1.save()

            return {'c1_id': c1.id, 'timestamp':time.mktime(c2.created.timetuple()) }

        def extra_checks(response):
            response = json.loads(response.content)
            self.assertEqual(len(response['reply']['cells']), 1)
            self.assertEqual(len(response['reply']['droplets']), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 200,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                },
            'method':'get',
            'url': '/api/status/after/%(timestamp)s/',
            'users': self.users,
            'checks' : { 'user': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_read_status_timestamp_share(self):
        """
        Read status of user, with timestamp
        Adding a share after timestamp
        """
        def setup():
            owner = self.users['owner']['object']
            user = self.users['user']['object']

            c = owner.cell_set.all()[0]
            c1 = Cell(owner=owner,
                      parent=c,
                      name="foo")
            c1.save()
            d = make_droplet(owner=owner, cell=c1, name="foo")
            d.save()

            time.sleep(1)
            c2 = Cell(owner=user,
                      parent=user.cell_set.all()[0],
                      name="bar")
            c2.save()
            d1 = make_droplet(owner=owner, cell=c2, name="foo1")
            d1.save()

            c1.share_set.add(Share(user=user, mode=1))

            return {'c1_id': c1.id, 'timestamp':time.mktime(c2.created.timetuple()) }

        def extra_checks(response):
            response = json.loads(response.content)
            self.assertEqual(len(response['reply']['cells']), 2)
            self.assertEqual(len(response['reply']['droplets']), 2)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 200,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                },
            'method':'get',
            'url': '/api/status/after/%(timestamp)s/',
            'users': self.users,
            'checks' : { 'user': extra_checks }
            }

        return dic


class UserTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_create_user(self):
        """
        Test user creation
        """

        def teardown():
            User.objects.filter(username="testuser").delete()

        def extra_checks(response):
            self.assertEqual(User.objects.filter(username="testuser").count(), 1)

        dic = {
            'teardown': teardown,
            'response_code': {'user': 401,
                              'admin': 200,
                              'anonymous':200,
                              'owner': 401,
                              },
            'postdata': {
                "first_name":"first_name",
                "last_name":"last_name",
                "email":"test@example.com",
                "username":"testuser",
                "password":"123"
                },
            'method':'post',
            'url': '/api/user/',
            'users': self.users,
            'checks' : { 'anonymous': extra_checks,
                         'admin': extra_checks}
            }

        return dic


    @test_multiple_users
    def test_delete_user(self):
        """
        Test user deletion
        """
        def setup():
            u, created = User.objects.get_or_create(username="melisi")

            if created:
                u.set_password("123")
                u.save()

            return { 'u_id': u.id }

        def extra_checks(response):
            self.assertEqual(User.objects.filter(username="testuser").count(), 0)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 204,
                              'admin': 204,
                              'anonymous':401,
                              'owner': 401,
                              },
            'postdata': {
                },
            'method':'delete',
            'url': '/api/user/%(u_id)s/',
            'users': self.users,
            'checks' : { 'user': extra_checks,
                         'admin': extra_checks}
            }

        return dic

    @test_multiple_users
    def test_read_user(self):
        """
        Test user details read
        """
        def setup():
            u = self.users['user']['object']
            return { 'u_id' : u.id }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 200,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 401,
                              },
            'postdata': {
                },
            'method':'get',
            'url': '/api/user/%(u_id)s/',
            'users': self.users,
            }

        return dic

    @test_multiple_users
    def test_user_update_password(self):
        """
        Test update user's password
        """
        def setup():
            u = self.users['user']['object']
            u.set_password("123")
            u.save()

            return { 'u_id' : u.id }

        def extra_checks(response):
            u = User.objects.get(pk=self.users['user']['object'].id)
            self.assertEqual(u.check_password("456"), True)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 200,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 401,
                              },
            'postdata': {
                'password': '456'
                },
            'method':'put',
            'url': '/api/user/%(u_id)s/',
            'users': self.users,
            'checks' : { 'user': extra_checks,
                         'admin': extra_checks}
            }

        return dic
