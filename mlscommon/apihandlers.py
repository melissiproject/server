import time
from datetime import datetime, timedelta
import re

from django import forms
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import MinValueValidator
from django.contrib.auth.models import AnonymousUser, User
from django.shortcuts import get_object_or_404

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
    model = Cell
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    fields = ('pk','name', 'owner',
              'created', 'updated', 'deleted',
              )

    @check_read_permission
    @watchdog_notfound
    def read(self, request, cell_id):
        cell = get_object_or_404(Cell, pk=cell_id)
        return cell

    @check_write_permission
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
            share = cell.share_set.get(user=request.user)
            share.name = form.instance.name or share.name
            share.parent = form.instance.parent or share.parent
            share.save()

            # TODO
            # if the new parent tree is shared with others then:
            # recurseive_update_shares

            # TODO
            # return cell with modified name and parent
            return cell

        else:
            form.save()

            if form.instance.parent:
                # set all parents updated
                cell.get_ancestors.update(updated=datetime.now())

                # find if any parent is shared, and if yes set all shares
                # updated time
                Share.objects.filter(
                    cell__in=cell.get_ancestors).update(updated=datetime.now())

        return cell

    @check_write_permission
    @watchdog_notfound
    @transaction.commit_on_success()
    def delete(self, request, cell_id):
        cell = get_object_or_404(Cell, pk=cell_id)
        cell.set_deleted()
        return rc.DELETED

class CellShareHandler(BaseHandler):
    model = Share
    fields = ('user', 'mode', 'name', 'created', 'updated')
    allowed_methods = ('GET', 'POST', 'DELETE')

    def read(self, request, cell_id):
        pass

    def create(self, request, cell_id):
        pass

    def delete(self, request, cell_id, username=None):
        pass

class StatusHandler(BaseHandler):
    pass

class ResourceHandler(BaseHandler):
    pass

class AnonymousUserHandler(AnonymousBaseHandler):
    pass

class UserHandler(BaseHandler):
    model = User
    fields = ('id', 'username', 'email', 'first_name', 'last_name', 'last_login')

