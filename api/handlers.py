from piston.handler import BaseHandler, AnonymousBaseHandler
from piston.utils import rc, FormValidationError
from django import forms
from mongoengine.queryset import DoesNotExist
from mongoengine.base import ValidationError as MongoValidationError
from django.db import IntegrityError, transaction
from mongoengine.django.auth import User, AnonymousUser
from mongoengine import Q
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.core.validators import MinValueValidator

import time
from datetime import datetime, timedelta
import re

from piston.decorator import decorator

from mlscommon.entrytypes import Droplet, Cell, DropletRevision,\
     Share, MelissiUser, UserResource, CellRevision
from mlscommon.common import calculate_md5, patch_file, sendfile, myFileField

from exceptions import APIBadRequest, APIForbidden, APINotFound

import settings

def validate(v_form, operations):
    # We don't use piston.utils.validate function
    # because it does not support request.FILES
    # and it's not according to documentation
    # i.e. when a form is valid it does not populate
    # request.form
    @decorator
    def wrap(function, self, request, *args, **kwargs):
        form = v_form(*tuple( getattr(request, operation) for operation in operations),
                      **{'request':request}
                      )

        if form.is_valid():
            request.form = form
            return function(self, request, *args, **kwargs)
        else:
            raise FormValidationError(form)

    return wrap

class MelissiResourceForm(forms.Form):
    resource = forms.CharField(max_length=500, min_length=1, required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('request')
        self.user = self.user.user

        super(MelissiResourceForm, self).__init__(*args, **kwargs)

    def clean(self):
        super(MelissiResourceForm, self).clean()
        if not isinstance(self.user, AnonymousUser):
            if self.cleaned_data['resource'] == '':
                self.cleaned_data['resource'] =\
                     UserResource.objects.filter(user=self.user)[0]
            else:
                self.cleaned_data['resource'], created =\
                     UserResource.objects.get_or_create(user=self.user,
                                                        name=self.cleaned_data['resource'])
        return self.cleaned_data

@decorator
def add_server_timestamp(function, self, request, *args, **kwargs):
    # we must log time before executing the function
    t = time.time()
    r = function(self, request, *args, **kwargs)
    return {'timestamp':t, 'reply': r}

@decorator
def watchdog_notfound(function, self, request, *args, **kwargs):
    try:
        return function(self, request, *args, **kwargs)

    # object does not exist
    except DoesNotExist, error:
        if getattr(settings, 'DEBUG', True):
            print error
        raise APINotFound({'error': "Object not found"})

    # object id not valid
    except MongoValidationError, error:
        if getattr(settings, 'DEBUG', True):
            print error
        raise APIBadRequest({'error': str(error)})


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
            raise APIForbidden({'cell': "You don't have permission to access cell %s" % args[0]})

    elif isinstance(self, CellShareHandler):
        cell = Cell.objects.get(pk=args[0])
        if not cell.owner.pk == request.user.pk:
            raise APIForbidden({'cell': "You don't have permission to read share list of cell %s" % args[0]})

    elif isinstance(self, DropletHandler) or \
             isinstance(self, RevisionHandler) or \
             isinstance(self, RevisionContentHandler) or \
             isinstance(self, RevisionPatchHandler):
        droplet = Droplet.objects.get(pk=args[0])
        if not _check_read_permission_obj(droplet.cell, request.user):
            raise APIForbidden({'droplet': "You don't have permission to access droplet %s" % args[0]})

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
                raise APIForbidden({'cell': "You don't have permission to write cell %s" % args[0]})

        # for create and update. in general when 'parent' is present
        # we must check that we can write to him
        if 'parent' in request.POST:
            # check parent
            parent = Cell.objects.get(pk = request.POST['parent'])
            if not _check_write_permission_obj(parent, request.user):
                raise APIForbidden({'cell': "You don't have permission to write cell %s" % parent.pk})

    elif isinstance(self, CellShareHandler):
        cell = Cell.objects.get(pk = args[0])
        try:
            root = Cell.objects.get(pk__in = cell.roots + [cell],
                                    shared_with__not__size = 0)
        except DoesNotExist, error:
            if cell.owner.pk != request.user.pk:
                raise APIForbidden({'cell': "You don't have permission to share cell %s" % args[0]})

        else:
            if root.owner.pk != request.user.pk and \
                   request.META['REQUEST_METHOD'] != 'DELETE':
                # DELETE is special case, because user can delete himself
                # from a share, without being owner of the root cell
                # Permission checks MUST be done at ShareHandler delete()
                raise APIForbidden({'cell': "You don't have permission to delete cell %s" % args[0]})

    elif isinstance(self, DropletHandler):
        if request.META['REQUEST_METHOD'] in ('DELETE', 'PUT') :
            droplet = Droplet.objects.get(pk = args[0])
            cell = droplet.cell
            if not _check_write_permission_obj(cell, request.user):
                raise APIForbidden({'droplet': "You don't have permission to write droplet %s" % args[0]})

        if 'cell' in request.POST:
            cell = Cell.objects.get(pk = request.POST['cell'])
            if not _check_write_permission_obj(cell, request.user):
                raise APIForbidden({'droplet': "You don't have permission to write cell %s" % cell.pk})

    elif isinstance(self, RevisionHandler):
        droplet = Droplet.objects.get(pk = args[0])
        if not _check_write_permission_obj(droplet.cell, request.user):
            raise APIForbidden({'droplet': "You don't have permission to write droplet %s" % args[0]})

    return function(self, request, *args, **kwargs)

def _recursive_update_shares(cell, request_user):
    """
    1. find all these users (variable sharing_users)
    2. for each shared cell of the tree just moved add a
       new share for each of the sharing_users with the
       same permissions as the owner of the tree

       Return the number of new shares created
    """
    number_of_shares_created = 0
    try:
        if request_user == cell.owner:
            parent=cell
        else:
            for share in cell.shared_with:
                if share.user.pk == request_user.pk:
                    parent = share.roots[0]
                    break
            else:
                raise IndexError

    except IndexError:
        # no parent, no need to do anything recursive
        return number_of_shares_created

    try:
        sharing_users = Cell.objects.get(pk__in=[parent.pk] + parent.roots,
                                         shared_with__not__size=0)

    except Cell.DoesNotExist:
        # the tree is not shared with anyone else. no worries
        pass

    else:
        # the tree is shared, locate all shared
        # cells of the tree just moved and create
        # new shares
        shared_cells = Cell.objects.filter((Q(roots=cell.pk) |\
                                            Q(pk=cell.pk) |\
                                            Q(shared_with__roots=cell.pk)
                                            ) &\
                                           Q(shared_with__not__size=0)
                                           )

        for shared_cell in shared_cells:
            # locate share of current user, so we
            # can copy name and mode
            current_user_share = None
            for share in shared_cell.shared_with:
                if share.user.pk == request_user.pk:
                    current_user_share = share
                    break
            else:
                continue

            # now add the shares
            for user in sharing_users.shared_with:
                s = Share(user = user.user,
                          mode = user.mode,
                          name = current_user_share.name,
                          roots = [parent.pk]
                          )
                shared_cell.shared_with.append(s)
                number_of_shares_created += 1

            shared_cell.save()

    return number_of_shares_created

class RevisionCreateForm(MelissiResourceForm):
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

class RevisionUpdateForm(MelissiResourceForm):
    number = forms.IntegerField(required=True, validators=[MinValueValidator(1)])
    md5 = forms.CharField(max_length=200, min_length=1, required=True)
    content = forms.FileField(required=True)
    patch = forms.ChoiceField(choices=((True, 'True'), (False, 'False')),
                              required=True,
                              )

class RevisionHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    fields = ('user', 'created', 'content_md5', 'patch_md5')
    model = DropletRevision

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
                raise APIBadRequest({'revision_id': 'Invalid revision number'})

            try:
                return droplet.revisions[revision_id]
            except IndexError:
                raise APINotFound({'revision': 'Revision with id %s not found'%\
                                   revision_id + 1}
                                  )

    @add_server_timestamp
    @check_write_permission
    @validate(RevisionCreateForm, ('POST', 'FILES'))
    @watchdog_notfound
    def create(self, request, droplet_id):
        """ TODO validate number """
        revision = DropletRevision()
        revision.resource = request.form.cleaned_data['resource']
        revision.content.put(request.form.cleaned_data['content'].file)
        revision.content.seek(0)

        # verify integrity
        if revision.content.md5 != request.form.cleaned_data['md5']:
            revision.content.delete()
            raise APIBadRequest({'md5': 'Content hashes do not match %s VS %s' %\
                                 (revision.content.md5, request.form.cleaned_data['md5'])
                                 }
                                )

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
            raise APINotFound({'revision': 'Request to updated non existing revision with id %s' %\
                               request.form.cleaned_data['number'] - 1
                               })

        revision = DropletRevision()
        revision.resource = request.form.cleaned_data['resource']

        if request.form.cleaned_data['patch'] == 'True':
            revision.content.put(patch_file(previous_revision.content,
                                            request.form.cleaned_data['content'])
                                )

            # rewinding the file
            request.form.cleaned_data['content'].file.seek(0)
            revision.patch.put(request.form.cleaned_data['content'])
        else:
            revision.content.put(request.form.cleaned_data['content'])

        # verify integrity
        if revision.content.md5 != request.form.cleaned_data['md5']:
            revision.content.delete()
            raise APIBadRequest({'md5': 'Content hashes do not match %s VS %s' %\
                                 (revision.content.md5, request.form.cleaned_data['md5'])
                                 }
                                )

        droplet.revisions.append(revision)
        droplet.save()

        return {'revision': revision, 'number': len(droplet.revisions)}

    @check_write_permission
    @watchdog_notfound
    def delete(self, request, droplet_id, revision_id):
        droplet = Droplet.objects.get(pk=droplet_id)
        revision_id = int(revision_id) - 1
        if revision_id < 0:
            raise APIBadRequest({'revision': 'Invalid revision number: %s' %\
                                 revision_id
                                 })

        try:
            droplet.revisions.pop(revision_id)
        except IndexError:
            raise APINotFound({'revision': 'Revision with id %s not found'%\
                               revision_id + 1}
                              )
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
            raise APIBadRequest({'revision': 'Invalid revision number: %s' %\
                                 revision_id
                                 })

        try:
            return sendfile(droplet.revisions[revision_id].content, droplet.name)
        except IndexError:
            raise APINotFound({'revision': 'Revision with id %s not found'%\
                               revision_id + 1}
                              )

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
            raise APIBadRequest({'revision': 'Invalid revision number: %s. Patching needs at least an existing revision' %\
                         revision_id
                         })


        try:
            return sendfile(droplet.revisions[revision_id].patch, "%s.patch" % droplet.name)
        except IndexError:
            raise APINotFound({'revision': 'Revision with id %s not found'%\
                               revision_id + 1}
                              )

class DropletCreateForm(MelissiResourceForm):
    name = forms.CharField(max_length=500, min_length=1, required=True)
    cell = forms.CharField(max_length=500, required=True)

class DropletUpdateForm(MelissiResourceForm):
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
    fields = ('pk', 'name', 'created', 'updated', 'revisions', 'deleted', 'owner',
              'cell')
    # fields = ('pk', ('cell', ('name', 'pk', ('owner', ('username', 'pk')))), 'revisions')
    # fields = ('revisions',)
    depth = 2

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

class CellShareForm(MelissiResourceForm):
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
    fields = ('user', 'mode', 'name', 'created')
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
        cell = Cell.objects.get(pk=cell_id)
        user = request.form.cleaned_data['user']

        # check that a root is not shared
        if Cell.objects.filter(pk__in = cell.roots,
                               shared_with__not__size = 0).count():
            raise APIBadRequest({'share': 'Another folder in the same tree is shared'})

        for share in cell.shared_with:
            if share.user == user:
                share.mode = request.form.cleaned_data['mode']
                break
        else:
            # we didn't find the user, create one share now
            cell.shared_with.append(Share(user=user,
                                          mode=request.form.cleaned_data['mode'],
                                          name=cell.name,
                                          roots=[Cell.objects.get(name='melissi',
                                                                  owner=user,
                                                                  roots__size = 0,
                                                                  )],
                                          )
                                    )

        cell.save()

        # create shares for all subshares of folder
        _recursive_update_shares(cell, request.user)

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
                raise APIForbidden({'share': "You don't have permission to delete user %s" % user.username})

            for share in cell.shared_with:
                if share.user == user:
                    cell.shared_with.remove(share)
                    cell.save()
                    break
            else:
                raise APINotFound({'share': 'User %s does not share cell'%\
                                   user.username}
                                  )

        else:
            # only owner can delete everything
            if request.user.pk == root.owner.pk:
                Cell.objects(pk=root.pk).update(set__shared_with=[])
            else:
                raise APIForbidden({'share': "You don't have permission to delete shares of cell %s" % root.pk})

        return rc.DELETED

class CellCreateForm(MelissiResourceForm):
    name = forms.CharField(max_length=500, min_length=1, required=True)
    parent = forms.CharField(max_length=500, required=False)

class CellUpdateForm(MelissiResourceForm):
    name = forms.CharField(max_length=500, min_length=1, required=False)
    parent = forms.CharField(max_length=500, required=False)

class CellHandler(BaseHandler):
    model = Cell
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    fields = ('pk','name', 'roots', 'owner',
              'created', 'updated', 'deleted')
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
                 roots = roots,
                 revisions = [CellRevision(resource=request.form.cleaned_data['resource'],
                                           name = request.form.cleaned_data['name']
                                           )]
                 )
        c.save()
        return c

    @add_server_timestamp
    @check_write_permission
    @validate(CellUpdateForm, ('POST',))
    @watchdog_notfound
    def update(self, request, cell_id):
        cell = Cell.objects.get(pk=cell_id)

        # if cell is root of shared and user is not owned then, change
        # values in shared_with
        if len(cell.shared_with) != 0 and cell.owner.pk != request.user.pk:
            for share in cell.shared_with:
                if share.user == request.user:
                    # update name
                    if request.form.cleaned_data.get('name'):
                        share.name = request.form.cleaned_data.get('name')

                    # update parents
                    if request.form.cleaned_data.get('parent'):
                        parent = Cell.objects.get(pk = request.form.cleaned_data['parent'])
                        share.roots = [parent] + parent.roots

                    break

            cell.save()

            # if the new parent tree is shared with other users then:
            _recursive_update_shares(cell, request.user)

            # return cell with modified name and roots to match user
            cell.name = share.name
            cell.roots = share.roots

            return cell

        else:
            # update name
            if request.form.cleaned_data.get('name'):
                cell.revisions.append(CellRevision(name=request.form.cleaned_data.get('name'),
                                                   resource=request.form.cleaned_data.get('resource')
                                                   )
                                      )
                cell.save()

            # update parents
            if len(request.form.cleaned_data.get('parent', '')):
                parent = Cell.objects.get(pk = request.form.cleaned_data['parent'])
                q = Cell.objects.filter(Q(roots__contains = cell) | Q(pk = cell.pk))
                q.update(pull_all__roots = cell.roots)
                q.update(push_all__roots = [parent] + parent.roots)
                q.update(set__updated = datetime.now())

                # update shared_with timestamps of shared root
                # find parents of parent
                try:
                    c = Cell.objects.get((Q(pk__in=parent.roots) | Q(pk=parent.pk)) &\
                                            Q(shared_with__not__size=0)
                                            )

                except:
                    # tree is not shared, do nothing
                    pass

                else:
                    timestamp = datetime.now()
                    for share in c.shared_with:
                        share.created = timestamp
                    c.save()

            cell.reload()
            return cell

    @add_server_timestamp
    @check_write_permission
    @watchdog_notfound
    def delete(self, request, cell_id):
        cell = Cell.objects.get(pk = cell_id)

        if cell.owner.pk != request.user.pk and len(cell.shared_with) > 0:
            # user want to delete share, not folder
            for share in cell.shared_with:
                if share.user == request.user:
                    cell.shared_with.remove(share)
                    cell.save()
                    break
        else:
            cell.set_deleted()

        return rc.DELETED

class UserCreateForm(MelissiResourceForm):
    username = forms.CharField(max_length=30, min_length=3)
    password = forms.CharField(max_length=30, min_length=3)
    password2 = forms.CharField(max_length=30, min_length=3)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(max_length=30)

    def clean(self):
        super(UserCreateForm, self).clean()

        # check hash
        if self.is_valid() and not re.match("\w+$", self.cleaned_data['username']):
            raise ValidationError("Not valid username")

        # check passwords
        if self.cleaned_data.get('password') != self.cleaned_data.get('password2'):
            raise ValidationError("Passwords to not match")

        return self.cleaned_data

class UserUpdateForm(MelissiResourceForm):
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
        if getattr(settings, 'MELISSI_REGISTRATIONS_OPEN', False):
            user = MelissiUser.create_user(request.form.cleaned_data['username'],
                                           request.form.cleaned_data['email'],
                                           request.form.cleaned_data['password']
                                           )
            user.first_name = request.form.cleaned_data['first_name']
            user.last_name = request.form.cleaned_data['last_name']
            user.save()
            return user
        else:
            raise APIForbidden({'register': 'Registrations are closed'})

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
            raise APIForbidden({'user': "You don't have permission to access user details"})

    @add_server_timestamp
    @validate(UserCreateForm, ('POST',))
    def create(self, request):
        if request.user.is_staff or request.user.is_superuser:
            user = MelissiUser.create_user(request.form.cleaned_data['username'],
                                           request.form.cleaned_data['email'],
                                           request.form.cleaned_data['password']
                                           )
            user.first_name = request.form.cleaned_data['first_name']
            user.last_name = request.form.cleaned_data['last_name']
            user.save()
            return user
        else:
            raise APIForbidden({'user': "You don't have permission to create new accounts"})

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
            raise APIForbidden({'user': "You don't have permission to update details for user %s" % user.username})

    def delete(self, request, username):
        user = User.objects.get(username=username)
        if request.user.is_staff or request.user.is_superuser or request.user == user:
            user.delete()
            return rc.DELETED
        else:
            raise APIForbidden({'user': "You don't have permission to delete user %s" % user.username})

class StatusHandler(BaseHandler):
    allowed_methods = ('GET', )
    depth = 2

    @add_server_timestamp
    def read(self, request, timestamp=None):
        # note that the default timestamp is 24 hours
        if timestamp == None:
            timestamp = datetime.now() - timedelta(days=1)
        else:
            # parse timestamp
            try:
                timestamp = datetime.fromtimestamp(float(timestamp))
            except (ValueError, TypeError), error_message:
                raise APIBadRequest({'timestamp': 'Bad timestamp format'})

        status_droplets = []
        status_cells = []

        owned_cells = Cell.objects.filter(owner=request.user)

        # add owned droplets after timestamp
        map(lambda x: status_droplets.append(x),
            Droplet.objects.filter(cell__in = owned_cells,
                                   revisions__not__size = 0,
                                   updated__gte = timestamp
                                   )
            )

        # add owned cells after timestamp
        map(lambda x: status_cells.append(x),
            Cell.objects.filter(pk__in = owned_cells,
                                updated__gte = timestamp
                                )
            )

        shared_cells_roots = Cell.objects.filter(shared_with__user = request.user)

        for cell in shared_cells_roots:
            shared = filter(lambda x: x.user == request.user,
                            cell.shared_with
                            )[0]
            cell.roots = shared.roots
            cell.name = shared.name

            if shared.created >= timestamp:
                # this is a new share, force add everything
                cells = Cell.objects.filter(roots__in = [cell])
                map(lambda x: status_cells.append(x), cells)
                map(lambda x: status_droplets.append(x),
                    Droplet.objects.filter((Q(cell__in = cells) | Q(cell=cell)) & \
                                           Q(revisions__not__size = 0)
                                           )
                )

                # add self
                status_cells.append(cell)

            else:
                # this is an old share, add only new stuff
                cells = Cell.objects.filter(Q(roots__in = [cell]) | Q(pk=cell))
                map(lambda x: status_droplets.append(x),
                    Droplet.objects.filter(cell__in = cells,
                                           revisions__not__size = 0,
                                           updated__gte = timestamp
                                           )
                    )
                map(lambda x: status_cells.append(x),
                    Cell.objects.filter(Q(roots__in = [cell]) | Q(pk=cell),
                                        updated__gte = timestamp
                                        )
                    )


        return {'cells':status_cells, 'droplets':status_droplets}
