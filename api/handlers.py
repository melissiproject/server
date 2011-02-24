from piston.handler import BaseHandler, AnonymousBaseHandler
from piston.utils import rc, FormValidationError
from django.shortcuts import get_object_or_404, get_list_or_404
# TODO
# from django.core.files.storage import default_storage
from django import forms
from mongoengine.queryset import DoesNotExist
from mongoengine.base import ValidationError as MongoValidationError
from django.db import IntegrityError, transaction
from mongoengine import Q
from django.http import Http404
from mongoengine.django.auth import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.core.validators import MinValueValidator

import time
import re

from piston.decorator import decorator

from mlscommon.entrytypes import Droplet, Cell, Revision, Share
from mlscommon.common import calculate_md5, patch_file

import settings

def validate(v_form, operations):
    # We don't use piston.utils.validate function
    # because it does not support request.FILES
    # and it's not according to documentation
    # i.e. when a form is valid it does not populate
    # request.form
    @decorator
    def wrap(function, self, request, *args, **kwargs):
        form = v_form(*tuple( getattr(request, operation) for operation in operations))

        if form.is_valid():
            request.form = form
            return function(self, request, *args, **kwargs)
        else:
            raise FormValidationError(form)
    return wrap

@decorator
def add_server_timestamp(function, self, request, *args, **kwargs):
    r = function(self, request, *args, **kwargs)
    return {'timestamp':time.time(), 'reply': r}

@decorator
def watchdog_notfound(function, self, request, *args, **kwargs):
    try:
        return function(self, request, *args, **kwargs)

    # object does not exist
    except DoesNotExist, error:
        if getattr(settings, 'DEBUG', True):
            print error
        return rc.NOT_FOUND

    # object id not valid
    except MongoValidationError, error:
        if getattr(settings, 'DEBUG', True):
            print error
        return rc.BAD_REQUEST


def _check_read_permission_obj(obj, user):
    if isinstance(obj, Cell):
        if not obj.owner.pk == user.pk and not \
               Cell.objects.filter(pk__in = obj.roots + [obj],
                                   shared_with__user = user).count():
               return False

    return True

@decorator
@watchdog_notfound
def check_read_permission(function, self, request, *args, **kwargs):
    """Check that the user has read permission

    """

    cell = None

    if isinstance(self, CellHandler):
        cell = Cell.objects.get(pk=args[0])
        if not _check_read_permission_obj(cell, request.user):
            return rc.FORBIDDEN

    elif isinstance(self, CellShareHandler):
        cell = Cell.objects.get(pk=args[0])
        if not cell.owner.pk == request.user.pk:
            return rc.FORBIDDEN

    elif isinstance(self, DropletHandler) or \
             isinstance(self, RevisionHandler) or \
             isinstance(self, RevisionContentHandler) or \
             isinstance(self, RevisionPatchHandler):
        droplet = Droplet.objects.get(pk=args[0])
        if not _check_read_permission_obj(droplet.cell, request.user):
            return rc.FORBIDDEN

    return function(self, request, *args, **kwargs)


def _check_write_permission_obj(obj, user):
    if isinstance(obj, Cell):
        if obj.owner.pk != user.pk and not \
               Cell.objects.filter(pk__in = obj.roots + [obj],
                                   shared_with__user = user,
                                   shared_with__mode = 'wara'
                                   ).count():
            return False

    return True

@decorator
@watchdog_notfound
def check_write_permission(function, self, request, *args, **kwargs):
    """Check that the user has read permission

    """
    cell = None
    if isinstance(self, CellHandler):
        if request.META['REQUEST_METHOD'] == 'PUT':
            # check cell
            cell = Cell.objects.get(pk = args[0])
            if not _check_write_permission_obj(cell, request.user):
                return rc.FORBIDDEN

        if 'parent' in request.POST:
            # check parent
            parent = Cell.objects.get(pk = request.POST['parent'])
            if not _check_write_permission_obj(parent, request.user):
                return rc.FORBIDDEN

    elif isinstance(self, CellShareHandler):
        cell = Cell.objects.get(pk = args[0])
        root = Cell.objects.get(pk__in = cell.roots + [cell],
                                shared_with__not__size = 0)
        if root.owner.pk != request.user.pk:
            return rc.FORBIDDEN

    elif isinstance(self, DropletHandler):
        if request.META['REQUEST_METHOD'] == 'DELETE':
            droplet = Droplet.objects.get(pk = args[0])
            cell = droplet.cell
        elif request.META['REQUEST_METHOD'] == 'POST':
            cell = Cell.objects.get(pk = request.POST['cell'])

        if not _check_write_permission_obj(cell, request.user):
                return rc.FORBIDDEN

    elif isinstance(self, RevisionHandler):
        droplet = Droplet.objects.get(pk = args[0])
        if not _check_write_permission_obj(droplet.cell, request.user):
            return rc.FORBIDDEN

    return function(self, request, *args, **kwargs)


class RevisionCreateForm(forms.Form):
    number = forms.IntegerField(required=True, validators=[MinValueValidator(1)])
    md5 = forms.CharField(max_length=200, min_length=1, required=True)
    content = forms.FileField(required=True)

    def clean(self):
        super(RevisionCreateForm, self).clean()

        # check hash
        if self.is_valid() and \
           self.cleaned_data['md5'] != calculate_md5(self.cleaned_data['content']):
            raise ValidationError("Hash does not match data")

        return self.cleaned_data

class RevisionUpdateForm(forms.Form):
    number = forms.IntegerField(required=True, validators=[MinValueValidator(1)])
    md5 = forms.CharField(max_length=200, min_length=1, required=True)
    patch = forms.FileField(required=True)

class RevisionHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    fields = ('user', 'created')
    model = Revision

    @add_server_timestamp
    @check_read_permission
    @watchdog_notfound
    def read(self, request, droplet_id, revision_id=None):
        droplet = Droplet.objects.get(pk=droplet_id)
        if not revision_id:
            # return last revision
            return droplet.revisions[-1]
        else:
            revision_id = int(revision_id) - 1
            if revision_id < 0:
                return rc.BAD_REQUEST

            try:
                return droplet.revisions[revision_id]
            except IndexError:
                return rc.NOT_FOUND


    @add_server_timestamp
    @check_write_permission
    @validate(RevisionCreateForm, ('POST', 'FILES'))
    @watchdog_notfound
    def create(self, request, droplet_id):
        """ TODO validate number """
        revision = Revision()
        revision.user = request.user
        revision.content.put(request.form.cleaned_data['content'].file)
        revision.content.seek(0)

        droplet = Droplet.objects.get(pk=droplet_id)
        droplet.no_revisions += 1
        droplet.revisions.append(revision)
        droplet.save()

        return revision


    @add_server_timestamp
    @check_write_permission
    @validate(RevisionUpdateForm, ('POST', 'FILES'))
    @watchdog_notfound
    def update(self, request, droplet_id, revision_id):
        droplet = Droplet.objects.get(pk=droplet_id)

        try:
            previous_revision = droplet.revisions[int(revision_id)-1]
        except IndexError:
            return rc.BAD_REQUEST

        revision = Revision()
        revision.user = request.user
        revision.content.put(patch_file(previous_revision.content,
                                        request.form.cleaned_data['patch'])
                            )

        # rewing the file
        request.form.cleaned_data['patch'].file.seek(0)
        revision.patch.put(request.form.cleaned_data['patch'])

        droplet.revisions.append(revision)
        droplet.no_revisions += 1
        droplet.save()

    @check_write_permission
    @watchdog_notfound
    def delete(self, request, droplet_id, revision_id):
        droplet = Droplet.objects.get(pk=droplet_id)
        try:
            droplet.revisions.pop(int(revision_id))
        except IndexError:
            return rc.NOT_FOUND

        droplet.no_revisions -= 1
        droplet.save()

        return rc.DELETED


class RevisionContentHandler(BaseHandler):
    allowed_methods = ('GET',)

    @check_read_permission
    @watchdog_notfound
    def read(self, request, droplet_id, revision_id=None):
        droplet = Droplet.objects.get(pk=droplet_id)
        if not revision_id:
            return droplet.revisions[-1].content.read()
        else:
            revision_id = int(revision_id) -1
            if revision_id < 0:
                return rc.BAD_REQUEST

            try:
                return droplet.revisions[revision_id].content.read()
            except IndexError:
                return rc.NOT_FOUND

class RevisionPatchHandler(BaseHandler):
    allowed_methods = ('GET',)

    @check_read_permission
    @watchdog_notfound
    def read(self, request, droplet_id, revision_id=None):
        droplet = Droplet.objects.get(pk=droplet_id)
        if not revision_id:
            return droplet.revisions[-1].patch.read()
        else:
            revision_id = int(revision_id) -1
            if revision_id < 1:
                # this is < 1 because revision 1 does not have a
                # patch!
                return rc.BAD_REQUEST

            try:
                return droplet.revisions[revision_id].patch.read()
            except IndexError:
                return rc.NOT_FOUND


class DropletCreateForm(forms.Form):
    name = forms.CharField(max_length=500, min_length=1, required=True)
    cell = forms.CharField(max_length=500, required=True)

class DropletHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'DELETE')
    model = Droplet
    fields = ('id', 'owner', 'created', 'no_revisions', 'revisions')

    @add_server_timestamp
    @check_read_permission
    @watchdog_notfound
    def read(self, request, droplet_id):
        droplet = Droplet.objects.get(pk=droplet_id)
        return droplet

    @add_server_timestamp
    @check_write_permission
    @validate(DropletCreateForm, ('POST',))
    @watchdog_notfound
    def create(self, request):
        cell = Cell.objects.get(pk = request.form.cleaned_data['cell'])
        d = Droplet(owner = request.user,
                    name = request.form.cleaned_data['name'],
                    cell = cell)
        d.save()
        return d

    @check_write_permission
    @watchdog_notfound
    def delete(self, request, droplet_id):
        Droplet.objects(pk=droplet_id).delete()
        return rc.DELETED

class CellShareUpdateForm(forms.Form):
    user = forms.CharField(max_length=500, required=False)
    mode = forms.CharField(required=True)

class CellShareDeleteForm(forms.Form):
    user = forms.CharField(max_length=500, required=False)

class CellShareHandler(BaseHandler):
    model = Share
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    depth = 2

    @add_server_timestamp
    @check_read_permission
    @watchdog_notfound
    def read(self, request, cell_id):
        cell = Cell.objects.get(pk=cell_id)
        root = Cell.objects.get(pk__in = cell.roots + [cell],
                                shared_with__not__size = 0)
        if root:
            return root.shared_with
        else:
            return {}

    def create(self, request):
        pass

    @add_server_timestamp
    @check_write_permission
    @validate(CellShareUpdateForm, ('POST',))
    @watchdog_notfound
    def update(self, request, cell_id):
        """ Currntly only one user per time """
        cell = Cell.objects.get(pk=cell_id)


    @add_server_timestamp
    @check_write_permission
    @validate(CellShareDeleteForm, ('POST',))
    @watchdog_notfound
    def delete(self, request, cell_id):
        """ Currently only owner can change stuff

        TODO We cannot POST data probably due to a django bug.
        So everytime we use this function we delete the whole shared_with set

        """
        cell = Cell.objects.get(pk=cell_id)
        root = Cell.objects.get(pk__in = cell.roots + [cell],
                                shared_with__not__size = 0)

        if root:
            if request.form.cleaned_data.get('user'):
                if Cell.objects(pk=root.pk).update(pull__shared_with = \
                                                   Share(user=request.form.cleaned_data.get('user'))) != 1:
                    return rc.NOT_FOUND
            else:
                Cell.objects(pk=root.pk).update(set__shared_with=[])
        else:
            return rc.NOT_FOUND

        return rc.DELETED

class CellCreateForm(forms.Form):
    name = forms.CharField(max_length=500, min_length=1, required=True)
    parent = forms.CharField(max_length=500, required=False)

class CellUpdateForm(forms.Form):
    name = forms.CharField(max_length=500, min_length=1, required=False)
    parent = forms.CharField(max_length=500, required=False)

class CellHandler(BaseHandler):
    model = Cell
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    fields = ('pk','name', 'roots')
    depth = 2

    @add_server_timestamp
    @check_read_permission
    @watchdog_notfound
    def read(self, request, cell_id):
        cell = Cell.objects.get(pk=cell_id)

        return {'cell': cell}

    @add_server_timestamp
    @check_write_permission
    @validate(CellCreateForm, ('POST',))
    @watchdog_notfound
    def create(self, request):
        parent_id = request.form.cleaned_data.get('parent', None)
        if parent_id:
            parent_cell = Cell.objects.get(pk=parent_id)
            owner = parent_cell.owner
            roots = [parent_cell] + parent_cell.roots
        else:
            owner = request.user
            roots = []

        c = Cell(owner = owner,
                 name = request.form.cleaned_data['name'],
                 roots = roots
                 )
        c.save()
        return c

    @add_server_timestamp
    @check_write_permission
    @validate(CellUpdateForm, ('POST',))
    @watchdog_notfound
    def update(self, request, cell_id):
        cell = Cell.objects.get(pk=cell_id)
        cell.name = request.form.cleaned_data.get('name', cell.name)
        cell.save()

        if len(request.form.cleaned_data.get('parent', '')):
            parent = Cell.objects.get(pk = request.form.cleaned_data['parent'])
            q = Cell.objects.filter(Q(roots__contains = cell) | Q(pk = cell.pk))
            q.update(pull_all__roots = cell.roots)
            q.update(push_all__roots = parent.roots + [parent])

        return cell

    @add_server_timestamp
    @check_write_permission
    @watchdog_notfound
    def delete(self, request, cell_id):
        cell = Cell.objects.get(pk = cell_id)
        cell.delete()

        return rc.DELETED


class UserCreateForm(forms.Form):
    username = forms.CharField(max_length=30, min_length=3)
    password = forms.CharField(max_length=30, min_length=3)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(max_length=30)

    def clean(self):
        super(UserCreateForm, self).clean()

        # check hash
        if self.is_valid() and not re.match("\w+$", self.cleaned_data['username']):
            raise ValidationError("Not valid username")

        return self.cleaned_data

class UserUpdateForm(forms.Form):
    username = forms.CharField(max_length=30, min_length=3, required=False)
    password = forms.CharField(max_length=30, min_length=3, required=False)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(max_length=30, required=False)

    def clean(self):
        super(UserUpdateForm, self).clean()

        # check hash
        if self.is_valid() and not re.match("\w+$", self.cleaned_data['username']):
            raise ValidationError("Not valid username")

        return self.cleaned_data


class AnonymousUserHandler(AnonymousBaseHandler):
    model = User
    allowed_methods = ('POST', )

    @add_server_timestamp
    @validate(UserCreateForm, ('POST',))
    def create(self, request):
        if getattr(settings, 'MELISI_REGISTRATIONS_OPEN', False):
            user = User.create_user(request.form.cleaned_data['username'],
                                    request.form.cleaned_data['password'],
                                    request.form.cleaned_data['email']
                                    )
            user.first_name = request.form.cleaned_data['first_name']
            user.last_name = request.form.cleaned_data['last_name']
            user.save()
            return user
        else:
            return rc.FORBIDDEN

class UserHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    model = User
    anonymous = AnonymousUserHandler
    fields = ('id', 'username', 'email', 'first_name', 'last_name', 'last_login')

    @add_server_timestamp
    @watchdog_notfound
    def read(self, request, username=None):
        if username == None:
            user = request.user
        else:
            user = User.objects.get(username=username)

        if request.user.is_staff or request.user.is_superuser or request.user == user:
            return user
        else:
            return rc.FORBIDDEN

    @add_server_timestamp
    @validate(UserCreateForm, ('POST',))
    def create(self, request):
        if request.user.is_staff or request.user.is_superuser:
            user = User.create_user(request.form.cleaned_data['username'],
                                    request.form.cleaned_data['password'],
                                    request.form.cleaned_data['email']
                                    )
            user.first_name = request.form.cleaned_data['first_name']
            user.last_name = request.form.cleaned_data['last_name']
            user.save()
            return user
        else:
            return rc.FORBIDDEN

    @add_server_timestamp
    @validate(UserUpdateForm, ('POST',))
    def update(self, request, username):
        user = User.objects.get(username=username)

        if request.user.is_staff or request.user.is_superuser or request.user == user:
            user.username = request.form.cleaned_data.get('username') or user.username
            user.password = request.form.cleaned_data.get('password') or user.password
            user.email = request.form.cleaned_data.get('email') or user.email
            user.first_name = request.form.cleaned_data.get('first_name') or user.first_name
            user.last_name = request.form.cleaned_data.get('last_name') or user.last_name
            user.save()
            return user
        else:
            return rc.FORBIDDEN

    def delete(self, request, username):

        user = User.objects.get(username=username)
        if request.user.is_staff or request.user.is_superuser or request.user == user:
            user.delete()
            return rc.DELETED
        else:
            return rc.FORBIDDEN
