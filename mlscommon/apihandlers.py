import time
from datetime import datetime, timedelta
import re

from django import forms
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import MinValueValidator
from django.contrib.auth.models import AnonymousUser, User
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Q

from piston.handler import BaseHandler, AnonymousBaseHandler
from piston.utils import rc, FormValidationError
from piston.decorator import decorator

from models import Droplet, DropletRevision, Cell, CellRevision,\
     Share, UserResource, UserProfile

from exceptions import APIBadRequest, APIForbidden, APINotFound

@decorator
def check_read_permission(function, self, request, *args, **kwargs):
    return function(self, request, *args, **kwargs)

@decorator
def check_write_permission(function, self, request, *args, **kwargs):
    return function(self, request, *args, **kwargs)

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
                                  Q(cell=c))
    if shares.count():
        share_root = shares[0].cell

        # locate share of current user to we can copy name and mode
        share = shares.get(user=user)

        for s in cell.share_set.all():
            s.cell = share_root
            s.mode = share.mode
            s.name = share.name
            s.save()
            number_of_shares_created +=1

    return number_of_shares_created

class DropletRevisionHandler(BaseHandler):
    pass

class DropletRevisionContentHandler(BaseHandler):
    pass

class DropletRevisionPatchHandler(BaseHandler):
    pass

class DropletHandler(BaseHandler):
    pass

class CellCreateForm(forms.ModelForm):
    class Meta:
        model = Cell
        fields = ('name', 'parent')

class CellUpdateForm(forms.ModelForm):
    class Meta:
        model = CellRevision
        fields = ('name', 'parent', 'resource', 'number')

class CellHandler(BaseHandler):
    """
    TODO
    _recursive_update_shares
    conflict resolving
    permission control
    """
    model = Cell
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    fields = ('pk','name', 'owner',
              'created', 'updated', 'deleted',
              )

    @check_read_permission
    @watchdog_notfound
    @add_server_timestamp
    def read(self, request, cell_id):
        cell = get_object_or_404(Cell, pk=cell_id)
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

    @check_write_permission
    @watchdog_notfound
    @add_server_timestamp
    @transaction.commit_on_success()
    def create(self, request):
        cell = Cell(owner=request.user)
        form = CellCreateForm(request.POST, instance=cell)
        if not form.is_valid():
            raise APIBadRequest(form.errors)

        form.save()

        return form.instance

    @check_write_permission
    @watchdog_notfound
    @add_server_timestamp
    @transaction.commit_on_success()
    def update(self, request, cell_id):
        cell = get_object_or_404(Cell, pk=cell_id)
        cell_revision = CellRevision(cell=cell)

        form = CellUpdateForm(request.POST, instance=cell_revision)
        if not form.is_valid():
            raise APIBadRequest(form.errors)

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

            # TODO
            # if the new parent tree is shared with others then:
            # _recursive_update_shares(cell, request.user)

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
                    cell__in=cell.get_ancestors).update(updated=datetime.now())

        return cell

    @check_write_permission
    @watchdog_notfound
    @add_server_timestamp
    @transaction.commit_on_success()
    def delete(self, request, cell_id):
        cell = get_object_or_404(Cell, pk=cell_id)
        cell.set_deleted()
        return rc.DELETED

class CellShareCreateForm(forms.ModelForm):
    class Meta:
        model = Share
        fields = ('mode',)

class CellShareHandler(BaseHandler):
    """
    TODO
    permission control
    """

    model = Share
    fields = ('user', 'mode', 'name', 'created', 'updated')
    allowed_methods = ('GET', 'POST', 'DELETE')

    @check_read_permission
    @watchdog_notfound
    @add_server_timestamp
    def read(self, request, cell_id):
        cell = get_object_or_404(Cell, pk=cell_id)
        shares = Share.objects.filter(Q(cell__in=cell.get_ancestors()) |\
                                      Q(cell = cell))
        return shares

    @check_write_permission
    @watchdog_notfound
    @add_server_timestamp
    @transaction.commit_on_success()
    def create(self, request, cell_id, user_id):
        """
        If user not in shared_with add him. If user in shared_with
        update entry
        """
        cell = get_object_or_404(Cell, pk=cell_id)
        user = get_object_or_404(User, pk=user_id)
        cell_share, created = Share.objects.get_or_create(cell=cell, user=user)
        form = CellShareCreateForm(request.POST, instance=cell_share)

        if not form.is_valid():
            raise APIBadRequest(form.errors)

        form.save()

        return form.instance


    @check_write_permission
    @watchdog_notfound
    @add_server_timestamp
    @transaction.commit_on_success()
    def delete(self, request, cell_id, user_id=None):
        cell = get_object_or_404(Cell, pk=cell_id)
        try:
            share_root = Share.objects.filter(
                Q(cell__in = cell.get_ancestors()) |\
                Q(cell = cell)
                )[0].cell
        except IndexError:
            # cell is not shared, nothing to delete
            raise APIBadRequest("Cell or Tree not shared")

        if user_id:
            user = get_object_or_404(User, pk=user_id)

            # user if not owner and tries to delete another user from
            # share
            if user != share_root.owner and user != request.user:
                raise APIForbidden("You don't have permission to delete "
                                   "user '%s'" % user)

            else:
                # delete own share
                share_root.share_set.filter(user=request.user).delete()

        else:
            # only owner can delete everything
            if request.user == share_root.owner:
                share_root.share_set.all().delete()

            else:
                raise APIForbidden("You don't have permission to delete "
                                   "shares of cell %s" % share_root)

        return rc.DELETED


class StatusHandler(BaseHandler):
    pass

class ResourceHandler(BaseHandler):
    pass

class AnonymousUserHandler(AnonymousBaseHandler):
    pass

class UserHandler(BaseHandler):
    model = User
    fields = ('id', 'username', 'email', 'first_name', 'last_name', 'last_login')

