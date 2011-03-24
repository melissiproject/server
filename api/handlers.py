from piston.handler import BaseHandler, AnonymousBaseHandler
from piston.utils import rc, FormValidationError
from django.shortcuts import get_object_or_404, get_list_or_404
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
from datetime import datetime, timedelta
import re

from piston.decorator import decorator

from mlscommon.entrytypes import Droplet, Cell, Revision, Share
from mlscommon.common import calculate_md5, patch_file, sendfile, myFileField

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
        if request.META['REQUEST_METHOD'] in ('PUT', 'DELETE'):
            # check cell
            cell = Cell.objects.get(pk = args[0])
            if not _check_write_permission_obj(cell, request.user):
                return rc.FORBIDDEN

        # for create and update. in general when 'parent' is present
        # we must check that we can write to him
        if 'parent' in request.POST:
            # check parent
            parent = Cell.objects.get(pk = request.POST['parent'])
            if not _check_write_permission_obj(parent, request.user):
                return rc.FORBIDDEN

    elif isinstance(self, CellShareHandler):
        cell = Cell.objects.get(pk = args[0])
        try:
            root = Cell.objects.get(pk__in = cell.roots + [cell],
                                    shared_with__not__size = 0)
        except DoesNotExist, error:
            if cell.owner.pk != request.user.pk:
                return rc.FORBIDDEN
        else:
            if root.owner.pk != request.user.pk and \
                   request.META['REQUEST_METHOD'] != 'DELETE':
                # DELETE is special case, because user can delete himself
                # from a share, without being owner of the root cell
                # Permission checks MUST be done at ShareHandler delete()
                return rc.FORBIDDEN

    elif isinstance(self, DropletHandler):
        if request.META['REQUEST_METHOD'] in ('DELETE', 'PUT') :
            droplet = Droplet.objects.get(pk = args[0])
            cell = droplet.cell
            if not _check_write_permission_obj(cell, request.user):
                return rc.FORBIDDEN

        if 'cell' in request.POST:
            cell = Cell.objects.get(pk = request.POST['cell'])
            if not _check_write_permission_obj(cell, request.user):
                return rc.FORBIDDEN

    elif isinstance(self, RevisionHandler):
        droplet = Droplet.objects.get(pk = args[0])
        if not _check_write_permission_obj(droplet.cell, request.user):
            return rc.FORBIDDEN

    return function(self, request, *args, **kwargs)


class RevisionCreateForm(forms.Form):
    number = forms.IntegerField(required=True, validators=[MinValueValidator(0)])
    md5 = forms.CharField(max_length=200, min_length=1, required=True)
    # caution we use our home breweded FileField form item
    # to allow empty files. this is only for CreateForm
    # to be changed when this code gets merged into django main
    # http://code.djangoproject.com/ticket/13584
    content = myFileField(required=True, allow_empty_file=True)

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
    content = forms.FileField(required=True)

class RevisionHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    fields = ('user', 'created', 'content_md5', 'patch_md5')
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
        droplet.revisions.append(revision)
        droplet.save()

        return {'revision': revision, 'number': len(droplet.revisions)}


    @add_server_timestamp
    @check_write_permission
    @validate(RevisionUpdateForm, ('POST', 'FILES'))
    @watchdog_notfound
    def update(self, request, droplet_id):
        droplet = Droplet.objects.get(pk=droplet_id)
        try:
            previous_revision = droplet.revisions[request.form.cleaned_data['number'] - 1]
        except IndexError:
            return rc.BAD_REQUEST

        revision = Revision()
        revision.user = request.user
        revision.content.put(patch_file(previous_revision.content,
                                        request.form.cleaned_data['content'])
                            )

        # verify integrity
        if revision.content.md5 != request.form.cleaned_data['md5']:
            revision.content.delete()
            return rc.BAD_REQUEST

        # rewinding the file
        request.form.cleaned_data['content'].file.seek(0)
        revision.patch.put(request.form.cleaned_data['content'])

        droplet.revisions.append(revision)
        droplet.save()

        return {'revision': revision, 'number': len(droplet.revisions)}

    @check_write_permission
    @watchdog_notfound
    def delete(self, request, droplet_id, revision_id):
        droplet = Droplet.objects.get(pk=droplet_id)
        revision_id = int(revision_id) - 1
        if revision_id < 0:
            return rc.BAD_REQUEST

        try:
            droplet.revisions.pop(revision_id)
        except IndexError:
            return rc.NOT_FOUND

        droplet.save()

        return rc.DELETED

class RevisionContentHandler(BaseHandler):
    @check_read_permission
    @watchdog_notfound
    def read(self, request, droplet_id, revision_id=None):
        droplet = Droplet.objects.get(pk=droplet_id)
        if not revision_id:
            revision_id = len(droplet.revisions)

        revision_id = int(revision_id) -1
        if revision_id < 0:
            return rc.BAD_REQUEST

        try:
            return sendfile(droplet.revisions[revision_id].content, droplet.name)
        except IndexError:
            return rc.NOT_FOUND


class RevisionPatchHandler(BaseHandler):
    allowed_methods = ('GET',)

    @check_read_permission
    @watchdog_notfound
    def read(self, request, droplet_id, revision_id=None):
        droplet = Droplet.objects.get(pk=droplet_id)
        if not revision_id:
            revision_id = len(droplet.revisions)

        revision_id = int(revision_id) -1
        if revision_id < 1:
            # this is < 1 because revision 1 does not have a
            # patch!
            return rc.BAD_REQUEST

        try:
            return sendfile(droplet.revisions[revision_id].patch, "%s.patch" % droplet.name)
        except IndexError:
            return rc.NOT_FOUND


class DropletCreateForm(forms.Form):
    name = forms.CharField(max_length=500, min_length=1, required=True)
    cell = forms.CharField(max_length=500, required=True)

class DropletUpdateForm(forms.Form):
    name = forms.CharField(max_length=500, min_length=1, required=False)
    cell = forms.CharField(max_length=500, required=False)

    def clean(self):
        super(DropletUpdateForm, self).clean()

        if not self.cleaned_data['name'] and not self.cleaned_data['cell']:
            raise ValidationError("At leat name or cell must be given")

        if self.is_valid() and self.cleaned_data['cell']:
            self.cleaned_data['cell'] = Cell.objects.get(pk=self.cleaned_data['cell'])

        return self.cleaned_data

class DropletHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    model = Droplet
    fields = ('pk', 'name', 'owner', 'cell', 'created', 'updated', 'revisions', 'deleted')

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

    @add_server_timestamp
    @check_write_permission
    @validate(DropletUpdateForm, ('POST',))
    @watchdog_notfound
    def update(self, request, droplet_id):

        droplet = Droplet.objects.get(pk=droplet_id)
        droplet.name = request.form.cleaned_data.get('name') or droplet.name
        droplet.cell = request.form.cleaned_data.get('cell') or droplet.cell
        droplet.save()

        return droplet

    @check_write_permission
    @watchdog_notfound
    def delete(self, request, droplet_id):
        droplet = Droplet.objects.get(pk=droplet_id)
        droplet.set_deleted()

        return rc.DELETED

class CellShareForm(forms.Form):
    def clean(self):
        if self.data.get('mode') and self.data['mode'] not in ['wara', 'wnra']:
            raise ValidationError("invalid share mode")

        super(CellShareForm, self).clean()

        if self.cleaned_data.get('user'):
            self.cleaned_data['user'] = User.objects.get(
                username=self.cleaned_data['user']
                )

        return self.cleaned_data

class CellShareCreateForm(CellShareForm):
    user = forms.CharField(max_length=500, required=True)
    mode = forms.CharField(required=True)

class CellShareUpdateForm(CellShareForm):
    user = forms.CharField(max_length=500, required=True)
    mode = forms.CharField(required=True)

class CellShareHandler(BaseHandler):
    model = Share
    allowed_methods = ('GET', 'POST', 'DELETE')
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

    @add_server_timestamp
    @check_write_permission
    @validate(CellShareCreateForm, ('POST',))
    @watchdog_notfound
    def create(self, request, cell_id):
        """ If user not in shared_with add him. If user in shared_with update entry """
        user = request.form.cleaned_data['user']
        share = Share(user=user, mode=request.form.cleaned_data['mode'])

        # check that a root is not shared
        cell = Cell.objects.get(pk=cell_id)
        if Cell.objects.filter(pk__in = cell.roots,
                               shared_with__not__size = 0).count():
            return rc.BAD_REQUEST

        # remove previous entry, if any
        # (creating a Share object without mode results into all
        # shares of that user to be matched. mode is ignored)
        Cell.objects(pk=cell_id).update(pull__shared_with=Share(user=user))
        Cell.objects(pk=cell_id).update(push__shared_with=share)

        return rc.CREATED

    @add_server_timestamp
    @check_write_permission
    @watchdog_notfound
    def delete(self, request, cell_id, username=None):
        """ Currently only owner can change stuff
        """
        cell = Cell.objects.get(pk=cell_id)
        root = Cell.objects.get(pk__in = cell.roots + [cell],
                                shared_with__not__size = 0)

        if username:
            user = User.objects.get(username=username)
            if request.user.pk != root.owner.pk and request.user.pk != user.pk:
                # user is not owner and tries to delete another user
                # from share
                return rc.FORBIDDEN

            if Cell.objects(pk=root.pk).update(pull__shared_with = \
                                               Share(user=user)) != 1:
                return rc.NOT_FOUND

        else:
            # only owner can delete everything
            if request.user.pk == root.owner.pk:
                Cell.objects(pk=root.pk).update(set__shared_with=[])
            else:
                return rc.FORBIDDEN

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
    fields = ('pk','name', 'roots', 'owner', 'created', 'updated', 'deleted')
    depth = 2

    @add_server_timestamp
    @check_read_permission
    @watchdog_notfound
    def read(self, request, cell_id):
        cell = Cell.objects.get(pk=cell_id)

        return cell

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
        cell.name = request.form.cleaned_data.get('name') or cell.name
        cell.save()

        if len(request.form.cleaned_data.get('parent', '')):
            parent = Cell.objects.get(pk = request.form.cleaned_data['parent'])
            q = Cell.objects.filter(Q(roots__contains = cell) | Q(pk = cell.pk))
            q.update(pull_all__roots = cell.roots)
            q.update(push_all__roots = [parent] + parent.roots)

        cell.reload()
        return cell

    @add_server_timestamp
    @check_write_permission
    @watchdog_notfound
    def delete(self, request, cell_id):
        cell = Cell.objects.get(pk = cell_id)
        cell.set_deleted()

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

class StatusHandler(BaseHandler):
    allowed_methods = ('GET', )

    depth = 2

    @add_server_timestamp
    def read(self, request, timestamp=None):
        print timestamp
        # note that the default timestamp is 24 hours
        if not timestamp:
            timestamp = datetime.now() - timedelta(days=1)
        else:
            # parse timestamp
            try:
                timestamp = datetime.fromtimestamp(float(timestamp))
            except (ValueError, TypeError), error_message:
                return rc.BAD_REQUEST

        s = Share(user=request.user, mode='wara')
        s1 = Share(user=request.user, mode='wnra')
        cells = Cell.objects.filter( (Q(owner=request.user) |
                                      Q(shared_with__contains = s1) |
                                      Q(shared_with__contains = s)) & \
                                     Q(updated__gte = timestamp)
                                     )
        c = Cell.objects.filter( Q(pk__in = cells) | Q(roots__in = cells) )

        cells = []
        map(lambda x: cells.append(x), c)
        droplets = []
        map(lambda x: droplets.append(x), Droplet.objects.filter(cell__in = c,
                                                                 revisions__not__size = 0,
                                                                 updated__gte = timestamp))

        return {'cells': cells, 'droplets': droplets }

