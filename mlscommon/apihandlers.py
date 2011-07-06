"""

The order of the decorators should be as follows:
 - add_server_timestamp
 - watchdog_notfound
 - check_read_permission OR check_write_permission
 - transaction.commit_on_success()

TODO
 recursive update

"""
import time
from datetime import datetime, timedelta
import re

from django import forms
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import MinValueValidator
from django.contrib.auth.models import AnonymousUser, User
from django.conf import settings
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _

from piston.handler import BaseHandler, AnonymousBaseHandler
from piston.utils import rc, FormValidationError
from piston.decorator import decorator

from models import Droplet, DropletRevision, Cell, CellRevision,\
     Share, UserResource, UserProfile

from exceptions import APIBadRequest, APIForbidden, APINotFound
import common

@decorator
def check_read_permission(function, self, request, *args, **kwargs):
    cell = None
    if isinstance(self, DropletHandler) or \
       isinstance(self, DropletRevisionHandler) or \
       isinstance(self, DropletRevisionDataHandler):
        obj = Droplet.objects.get(pk=args[0])
        cell = obj.cell

    elif isinstance(self, CellHandler) or isinstance(self, CellShareHandler):
        obj = Cell.objects.get(pk=args[0])
        cell = obj

    if cell:
        # now do the check
        if cell.owner == request.user:
            return function(self, request, *args, **kwargs)

        else:
            shares = Share.objects.filter(Q(cell__in=cell.get_ancestors()) |\
                                          Q(cell=cell)).filter(user=request.user)
            if shares:
                return function(self, request, *args, **kwargs)
            else:
                raise APIForbidden("Permission denied")
    else:
        raise APIForbidden("Permission denied")


def _check_write_permission(user, cell):
    if cell.owner == user:
        return True

    else:
        shares = Share.objects.filter(Q(cell__in=cell.get_ancestors()) |\
                                      Q(cell=cell)).filter(user=user, mode=1)

        if shares:
            return True

        else:
            return False

@decorator
def check_write_permission(function, self, request, *args, **kwargs):
    cells = []
    new_root_cell = False

    if isinstance(self, DropletHandler):
        if request.META['REQUEST_METHOD'] == 'POST':
            # this is a CREATE command, the cell to put the droplet into
            # is in the POSTED parameters
            cells.append(Cell.objects.get(pk=request.POST.get('cell', None)))

        else:
            obj = Droplet.objects.get(pk=kwargs.get('droplet_id', None))
            cells.append(obj.cell)

    elif isinstance(self, DropletRevisionHandler):
        obj = Droplet.objects.get(pk=kwargs.get('droplet_id', None))
        cells.append(obj.cell)

        # if this is a "move" then also fetch the cell to move into
        if 'cell' in request.POST:
            cells.append(Cell.objects.get(pk=request.POST.get('cell', None)))

    elif isinstance(self, CellHandler):
        if request.META['REQUEST_METHOD'] == 'POST':
            # this is a CREATE command, the cell to put the cell into
            # is in the POSTED parameters
            if not request.POST.get('parent', None):
                new_root_cell = True
            else:
                cells.append(Cell.objects.get(pk=request.POST.get('parent')))
        else:
            cells.append(Cell.objects.get(pk=kwargs.get('cell_id', None)))

            # if this is a "move" then also fetch the cell to move into
            if 'parent' in request.POST:
                cells.append(Cell.objects.get(pk=request.POST.get('parent', None)))

    elif isinstance(self, CellShareHandler):
        cell = Cell.objects.get(pk=kwargs.get('cell_id', None))
        cells.append(cell)
        if kwargs.get('user_id', None):
            # this a refering to a specific user. Only user and owner
            # can view / edit
            user_id = int(kwargs.get('user_id'))
            if not (user_id == request.user.id or request.user.id == cell.owner.id):
                # empty cells so check fails
                cells = []

    if new_root_cell:
        return function(self, request, *args, **kwargs)

    elif cells:
        for cell in cells:
            if not _check_write_permission(request.user, cell):
                raise APIForbidden("Permission denied")

        else:
            return function(self, request, *args, **kwargs)

    raise APIForbidden("Permission denied")

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
    except ObjectDoesNotExist, error:
        if getattr(settings, 'DEBUG', True):
            print error
        raise APINotFound({'error': "Object not found"})

class ResourceForm(forms.ModelForm):
    resource = forms.CharField(max_length=500, required=False)

    def __init__(self, user, *args, **kwargs):
        self._user = user
        super(ResourceForm, self).__init__(*args, **kwargs)

    def clean_resource(self):
        resource, created =  UserResource.objects.get_or_create(
            name = self.cleaned_data.get('resource', 'melissi'),
            user = self._user
            )
        if created:
            resource.save()

        self.instance.resource = resource

        return resource

def _recursive_update_shares(cell, user):
    """
    """
    # find cell parent
    # find if parent tree is shared
    # move cells shared to parent tree shares

    number_of_shares_created = 0

    if user == cell.owner:
        parent = cell.parent

    else:
        parent = cell.share_set.get(user=user).parent

    shares = Share.objects.filter(Q(cell__in=parent.get_ancestors()) |\
                                  Q(cell=parent))

    if shares.count():
        share_root = shares[0].cell
        # locate share of current user to we can copy name and mode
        try:
            share = shares.get(user=user)
        except Share.DoesNotExist:
            # user was not in share, he's owner
            share = None

        for s in Share.objects.filter(Q(cell__in=cell.get_descendants()) |\
                                      Q(cell=cell)):
            s.cell = share_root
            if share:
                s.mode = share.mode
                s.name = share.name
            s.save()

            number_of_shares_created +=1

    return number_of_shares_created

class DropletRevisionCreateForm(ResourceForm):
    class Meta:
        model = DropletRevision
        fields = ('name', 'cell', 'content', 'content_sha256', 'number')

class DropletRevisionHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'DELETE')
    fields = (('resource', ('name', 'user')), 'created', 'name',
              'content_sha256', 'patch_sha256'
              )
    models = DropletRevision

    @check_write_permission
    @watchdog_notfound
    @add_server_timestamp
    def read(self, request, droplet_id, revision_number=None):
        droplet = Droplet.objects.get(pk=droplet_id)
        if revision_number:
            rev = droplet.dropletrevision_set.get(number=revision_number)
        else:
            rev = droplet.dropletrevision_set.latest()
        return rev

    @check_write_permission
    @add_server_timestamp
    @transaction.commit_on_success()
    def create(self, request, droplet_id):
        droplet = Droplet.objects.get(pk=droplet_id)
        resource, created = UserResource.objects.get_or_create(user=request.user,
                                                               name=request.POST.get('resource', 'melissi')
                                                               )
        if created:
            resource.save()

        revision = DropletRevision(resource=resource,
                                   droplet=droplet,
                                   )
        form = DropletRevisionCreateForm(request.user,
                                         request.POST,
                                         request.FILES,
                                         instance=revision)

        if not form.is_valid():
            raise APIBadRequest(form.errors)

        # check for conflicts
        if form.instance.number > droplet.revisions + 1:
            raise APIBadRequest({'error':'Wrong revision number'})

        elif form.instance.number < droplet.revisions + 1:
            # houston we have a conflict
            # create a new droplet
            new_droplet = Droplet(name=droplet.name,
                                  owner=droplet.owner,
                                  created=droplet.created,
                                  cell=droplet.cell,
                                  content=droplet.content,
                                  patch=droplet.patch,
                                  content_sha256=droplet.content_sha256,
                                  patch_sha256=droplet.patch_sha256,
                                  deleted=droplet.deleted)

            new_droplet.save()

            # delete autogenerated revisions
            try:
                new_droplet.dropletrevision_set.all().delete()
            except ObjectDoesNotExist:
                # _update_droplet will raise DoesNotExist that we
                # can safetly ignore, since we will create manually
                # the revisions
                pass

            # copy revisions
            for rev in droplet.dropletrevision_set.all().order_by("number"):
                if rev.number == form.instance.number:
                    # don't copy conflicting revision
                    # break since its the last to copy
                    break

                new_rev = DropletRevision(droplet=new_droplet,
                                          resource=rev.resource,
                                          name=rev.name,
                                          number=rev.number,
                                          cell=rev.cell,
                                          content=rev.content,
                                          patch=rev.patch,
                                          content_sha256=rev.content_sha256,
                                          patch_sha256=rev.patch_sha256
                                          )

                new_rev.save()

            # set new_droplet
            droplet = new_droplet
            form.instance.droplet = new_droplet

        form.save()

        return droplet

    @check_write_permission
    @watchdog_notfound
    @transaction.commit_on_success()
    def delete(self, request, droplet_id, revision_number):
        droplet = Droplet.objects.get(pk=droplet_id)
        revision = droplet.dropletrevision_set.filter(number=revision_number)

        if droplet.dropletrevision_set.count() == 1:
            # cannot delete the last revision
            raise APIBadRequest("Cannot delete the last revision "
                                "of droplet %s" % droplet.id)

        revision.delete()

        return rc.DELETED

class DropletRevisionDataHandler(BaseHandler):
    allowed_methods = ('GET', )

    @check_read_permission
    @watchdog_notfound
    def read(self, request, type, droplet_id, revision_number=None):
        droplet = Droplet.objects.get(pk=droplet_id)
        if revision_number:
            # find the revision with the latest name entry with
            # revision_number less than or equal to revision_number
            name = droplet.dropletrevision_set.filter(name__isnull=False,
                                                      number__lte=revision_number)[0].name

            # find the revision with the latest content entry with
            # revision_number less than or equal to revision_number
            data = getattr(droplet.dropletrevision_set.filter(content_sha256__isnull=False,
                                                              number__lte=revision_number)[0],
                           type)

        else:
            revision = droplet.dropletrevision_set.latest()
            name = droplet.name
            data = getattr(droplet, type)

        try:
            path = data.path

        except ValueError:
            raise APINotFound("Droplet '%s' has no '%s'" % (droplet_id, type))

        return common.sendfile(path, name)

class DropletCreateForm(ResourceForm):
    class Meta:
        model = Droplet
        fields = ('name', 'cell', 'content', 'content_sha256')

class DropletHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'DELETE')
    model = Droplet
    fields = ('id', ('cell', ('name', 'id', ('owner', ('username', 'id', 'email')))),
              'name', ('owner', ('username', 'id', 'email')), 'created', 'updated',
              'deleted', 'content_sha256', 'patch_sha256', 'revisions')

    @add_server_timestamp
    @watchdog_notfound
    @check_read_permission
    def read(self, request, droplet_id):
        droplet = Droplet.objects.get(pk=droplet_id)
        return droplet

    @add_server_timestamp
    @watchdog_notfound
    @check_write_permission
    @transaction.commit_on_success()
    def create(self, request):
        droplet = Droplet(owner=request.user)
        form = DropletCreateForm(request.user,
                                 request.POST,
                                 request.FILES,
                                 instance=droplet
                                 )
        if not form.is_valid():
            raise APIBadRequest(form.errors)

        form.save()

        rev = form.instance.dropletrevision_set.all()[0]
        rev.resource = form.cleaned_data['resource']
        rev.save()

        return form.instance

    @add_server_timestamp
    @watchdog_notfound
    @check_write_permission
    @transaction.commit_on_success()
    def delete(self, request, droplet_id):
        droplet = Droplet.objects.get(pk=droplet_id)
        droplet.set_deleted()

        return rc.DELETED

class CellCreateForm(ResourceForm):
    class Meta:
        model = Cell
        fields = ('name', 'parent')

class CellUpdateForm(ResourceForm):
    class Meta:
        model = CellRevision
        fields = ('name', 'parent', 'resource', 'number')

class CellHandler(BaseHandler):
    """

    """
    model = Cell
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    fields = ('pk','name', 'owner', 'pid',
              'created', 'updated', 'deleted', 'revisions',
              )

    @add_server_timestamp
    @watchdog_notfound
    @check_read_permission
    def read(self, request, cell_id):
        cell = Cell.objects.get(pk=cell_id)
        try:
            share = cell.share_set.get(user=request.user)
            # change cell.name and cell.parent according to share
            # used only to return values, do NOT save
            cell.name = share.name
            cell.parent = share.parent
        except ObjectDoesNotExist:
            # cell is not shared, no worries
            pass

        return cell

    @add_server_timestamp
    @watchdog_notfound
    @check_write_permission
    @transaction.commit_on_success()
    def create(self, request):
        cell = Cell(owner=request.user)
        form = CellCreateForm(request.user, request.POST, instance=cell)
        if not form.is_valid():
            raise APIBadRequest(form.errors)

        form.save()

        rev = form.instance.cellrevision_set.all()[0]
        rev.resource = form.cleaned_data['resource']
        rev.save()

        return form.instance

    @add_server_timestamp
    @watchdog_notfound
    @check_write_permission
    @transaction.commit_on_success()
    def update(self, request, cell_id):
        cell = Cell.objects.get(pk=cell_id)
        cell_revision = CellRevision(cell=cell)

        form = CellUpdateForm(request.user, request.POST, instance=cell_revision)
        if not form.is_valid():
            raise APIBadRequest(form.errors)

        # check for conflicts
        if form.instance.number > cell.revisions + 1:
            raise APIBadRequest({'error': 'Wrong revision number'})

        elif form.instance.number < cell.revisions + 1:
            # lower revision number, just ignore
            pass

        else:
            # cell is root of shared and user is not owner then, change
            # values in share
            if cell.owner != request.user and cell.share_set.count():
                # TODO
                # maybe we can do that with a form, instead of using
                # CellUpdateForm. Just to be clean and safe
                share = cell.share_set.get(user=request.user)
                share.name = form.instance.name or share.name
                share.parent = form.instance.parent or share.parent
                share.save()

                # change cell.name and cell.parent according to share
                # used only to return values, do NOT save
                cell.name = share.name
                cell.parent = share.parent

                return cell

            else:
                form.save()

                if form.instance.parent:
                    # set all parents updated
                    cell.get_ancestors().update(updated=datetime.now())

                    # find if any parent is shared, and if yes set all shares
                    # updated time
                    Share.objects.filter(
                        cell__in=cell.get_ancestors()
                        ).update(updated=datetime.now())

            # # if the new parent tree is shared with others then:
            # _recursive_update_shares(cell, request.user)

        return cell

    @add_server_timestamp
    @watchdog_notfound
    @check_write_permission
    @transaction.commit_on_success()
    def delete(self, request, cell_id):
        cell = Cell.objects.get(pk=cell_id)
        cell.set_deleted()
        return rc.DELETED

class CellShareCreateForm(forms.ModelForm):
    class Meta:
        model = Share
        fields = ('mode',)

class CellShareHandler(BaseHandler):
    """
    """

    model = Share
    fields = ('user', 'mode', 'name', 'created', 'updated')
    allowed_methods = ('GET', 'POST', 'DELETE')

    @add_server_timestamp
    @watchdog_notfound
    @check_read_permission
    def read(self, request, cell_id):
        cell = Cell.objects.get(pk=cell_id)
        shares = Share.objects.filter(Q(cell__in=cell.get_ancestors()) |\
                                      Q(cell = cell))
        return shares

    @add_server_timestamp
    @watchdog_notfound
    @check_write_permission
    @transaction.commit_on_success()
    def create(self, request, cell_id, user_id):
        """
        If user not in shared_with add him. If user in shared_with
        update entry
        """
        cell = Cell.objects.get(pk=cell_id)
        user = User.objects.get(pk=user_id)
        cell_share, created = Share.objects.get_or_create(cell=cell, user=user)
        form = CellShareCreateForm(request.POST, instance=cell_share)

        if not form.is_valid():
            raise APIBadRequest(form.errors)

        form.save()

        # _recursive_update_shares(cell, request.user)

        return rc.CREATED

    @add_server_timestamp
    @watchdog_notfound
    @check_write_permission
    @transaction.commit_on_success()
    def delete(self, request, cell_id, user_id=None):
        cell = Cell.objects.get(pk=cell_id)
        try:
            share_root = Share.objects.filter(
                Q(cell__in = cell.get_ancestors()) |\
                Q(cell = cell)
                )[0].cell
        except IndexError:
            # cell is not shared, nothing to delete
            raise APIBadRequest("Cell or Tree not shared")

        if user_id:
            user = User.objects.get(pk=user_id)

            # user if not owner and tries to delete another user from
            # share
            if request.user != share_root.owner and user != request.user:
                raise APIForbidden("You don't have permission to delete "
                                   "user '%s'" % user)

            else:
                # delete own share
                share_root.share_set.filter(user=user).delete()

        else:
            # only owner can delete everything
            if request.user == share_root.owner:
                share_root.share_set.all().delete()

            else:
                raise APIForbidden("You don't have permission to delete "
                                   "shares of cell %s" % share_root)

        return rc.DELETED


class StatusHandler(BaseHandler):
    allowed_methods = ('GET', )

    @add_server_timestamp
    def read(self, request, timestamp=None):
        # note that the default timestamp is 24hours
        if not timestamp:
            timestamp = datetime.now() - timedelta(days=1)
        else:
            # parse timestamp
            try:
                timestamp = datetime.fromtimestamp(float(timestamp))
            except (ValueError, TypeError), error_message:
                raise APIBadRequest({'timestamp': 'Bad timestamp format'})


        status_droplets = []
        status_cells = []

        shares = Share.objects.filter(user=request.user)
        owned_cells = Cell.objects.filter(owner=request.user)


        # add owned droplets after timestamp
        map(lambda x: status_droplets.append(x),
            Droplet.objects.filter(cell__in = owned_cells,
                                   updated__gte = timestamp)
            )

        # add owned cells after timestamp
        map(lambda x: status_cells.append(x),
            owned_cells.filter(updated__gte=timestamp)
            )

        # now add shares
        for share in shares:
            cell = share.cell
            cell.name = share.name
            cell.panret = share.parent

            if share.created >= timestamp:
                # this is a new share, force add everything
                map(lambda x: status_cells.append(x),
                    share.cell.get_descendants())
                status_cells.append(cell)

                map(lambda x: status_droplets.append(x),
                    Droplet.objects.filter(
                        Q(cell__in = share.cell.get_descendants()) |\
                        Q(cell = cell)
                        )
                    )

            else:
                # this is an old share, add only new stuff
                map(lambda x: status_cells.append(x),
                    share.cell.get_descendants().filter(updated_gte=timestamp)
                    )
                if share.cell.updated >= timestamp:
                    status_cells.append(cell)

                map(lambda x: status_droplets.append(x),
                    Droplet.objects.filter(
                        Q(cell__in = share.cell.get_descendants()) |\
                        Q(cell = cell)
                        ).filter(updated__gte=timestamp)
                    )

        return {'cells': status_cells, 'droplets': status_droplets }

class ResourceHandler(BaseHandler):
    model = UserResource
    fields = ('name', 'user', 'created', 'updated')
    allowed_methods = tuple()

class UserCreateForm(forms.Form):
    username = forms.CharField(_('username'), required=True)
    first_name = forms.CharField(_('first name'), required=True)
    last_name = forms.CharField(_('last name'), required=True)
    email = forms.EmailField(_('e-mail address'), required=True)
    password = forms.CharField(_('password'), required=True)

class UserUpdateForm(forms.Form):
    password = forms.CharField(_('password'), required=True)

class AnonymousUserHandler(AnonymousBaseHandler):
    model = User
    allowed_methods = ('POST', )
    fields = ('id', 'username', 'email', 'first_name', 'last_name', 'last_login')

    @add_server_timestamp
    @transaction.commit_on_success()
    def create(self, request):
        if not getattr(settings, 'MELISSI_REGISTRATIONS_OPEN', False):
            raise APIForbidden({'register': 'Registrations are closed'})

        form = UserCreateForm(request.POST)

        if not form.is_valid():
            raise APIBadRequest(form.errors)

        if User.objects.filter(Q(username=form.cleaned_data['username']) |\
                               Q(email=form.cleaned_data['email'])).count():
            raise APIBadRequest({'error': 'email and / or username already exists'})

        user = User.objects.create_user(form.cleaned_data['username'],
                                        form.cleaned_data['email'],
                                        form.cleaned_data['password'])
        user.first_name = form.cleaned_data['first_name']
        user.last_name = form.cleaned_data['last_name']
        user.save()

        return user

class UserHandler(BaseHandler):
    model = User
    anonymous = AnonymousUserHandler
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    fields = ('id', 'username', 'email', 'first_name', 'last_name', 'last_login')

    @add_server_timestamp
    @watchdog_notfound
    def read(self, request, user_id):
        if not user_id:
            user = request.user

        else:
            user = User.objects.get(pk=user_id)

        if request.user.is_staff or request.user.is_superuser or request.user == user:
            return user

        else:
            raise APIForbidden({'user': "You don't have permission to access user details"})

    @add_server_timestamp
    @watchdog_notfound
    @transaction.commit_on_success()
    def create(self, request):
        if request.user.is_staff or request.user.is_superuser:
            form = UserCreateForm(request.POST)
            if not form.is_valid():
                raise APIBadRequest(form.errors)

            if User.objects.filter(Q(username=form.cleaned_data['username']) |\
                                   Q(email=form.cleaned_data['email'])).count():
                raise APIBadRequest({'error': 'email and / or username already exists'})

            user = User.objects.create_user(form.cleaned_data['username'],
                                            form.cleaned_data['email'],
                                            form.cleaned_data['password'])
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.save()

            return user

        else:
            raise APIForbidden({'user': "You don't have permission to create new accounts"})

    @add_server_timestamp
    @watchdog_notfound
    @transaction.commit_on_success()
    def update(self, request, user_id):
        """
        User update call. Currently used only for password changing
        """

        user = User.objects.get(pk=user_id)
        if request.user.is_staff or request.user.is_superuser or user == request.user:
            form = UserUpdateForm(request.POST)
            if not form.is_valid():
                raise APIBadRequest(form.errors)

            user.set_password(form.cleaned_data['password'])
            user.save()
            return user

        else:
            raise APIForbidden({'user': "You don't have permission to edit user"})

    @add_server_timestamp
    @watchdog_notfound
    @transaction.commit_on_success()
    def delete(self, request, user_id):
        user = User.objects.get(pk=user_id)
        if request.user.is_staff or request.user.is_superuser or request.user == user:
            user.delete()
            return rc.DELETED

        else:
            raise APIForbidden({'user': "You don't have permission to delete "
                                "user %s" % user.username})
