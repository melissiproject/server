from django.db import models

# Create your models here.
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.core.validators import MinLengthValidator
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.conf import settings
from mptt.models import MPTTModel

import hashlib
from datetime import datetime
from common import calculate_sha256

def calculate_upload_path(instance, filename):
    if isinstance(instance, Droplet):
        return "%s" % (instance.name)
    elif isinstance(instance, DropletRevision):
        return "%s" % (instance.droplet.id)
    else:
        raise Exception("Cannot calculate upload path")

class PatchValidator(object):
    def __call__(self, value):
        if not value.read(4).encode('HEX') == '72730236':
            raise ValidationError("Not a librsync delta")
        value.seek(0)

        return value

class Cell(MPTTModel):
    owner = models.ForeignKey(User)
    deleted = models.BooleanField(default=False)
    name = models.CharField(max_length=500)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    parent = models.ForeignKey('self',
                               null=True, blank=True,
                               default=None,
                               related_name='children')
    revisions = models.PositiveIntegerField(default=0)

    def __unicode__(self):
        return "[%s:%s]" % (self.id, self.name)

    @property
    def pid(self):
        """ return parent_id """
        if self.parent:
            return self.parent.id
        else:
            return None

    @classmethod
    def _first_revision_creator(self, sender, instance, **kwargs):
        if instance.cellrevision_set.count() == 0:
            # create first revision
            revision = CellRevision(cell=instance,
                                    name = instance.name,
                                    resource=instance.owner.userresource_set.all()[0],
                                    parent=instance.parent,
                                    number=1)
            revision.save()

    def clean(self):
        # root cells cannot have the same name, it's the only
        # restriction
        if not self.parent and \
               Cell.objects.filter(owner=self.owner,
                                   name=self.name,
                                   parent=None).exclude(pk=self.id).count():
            raise ValidationError("There is already a cell with name '%s' and "
                                  "no parent for user '%s'" % (self.name, self.owner))

        return super(Cell, self).clean()

    def save(self, *args, **kwargs):
        # if parent set owner to parent.owner
        if self.parent:
            self.owner = self.parent.owner
        return super(Cell, self).save(*args, **kwargs)

    def set_deleted(self):
        # set children cells and droplets to deleted
        self.get_descendants().update(deleted=True, updated=datetime.now())
        Droplet.objects.filter(cell__in=self.get_descendants()).update(deleted=True,
                                                                       updated=datetime.now())

        # set self and own droplets to deleted
        Droplet.objects.filter(cell=self).update(deleted=True,
                                                 updated=datetime.now())

        self.deleted=True
        self.save()

    @classmethod
    def _revision_count(self, sender, instance, **kwargs):
        instance.revisions = instance.cellrevision_set.count()

models.signals.post_save.connect(Cell._first_revision_creator, sender=Cell)
models.signals.pre_save.connect(Cell._revision_count, sender=Cell)

class CellRevision(models.Model):
    cell = models.ForeignKey(Cell)
    name = models.CharField(max_length=500, default=None, null=True, blank=True)
    parent = models.ForeignKey(Cell, null=True, blank=True,
                               default=None,
                               related_name='revision_parent')
    number = models.PositiveIntegerField()
    resource = models.ForeignKey("UserResource")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('cell', 'number'),)
        get_latest_by = "number"
        ordering = ("-number",)

    def clean(self):
        if self.name == '':
            self.name = None

    @classmethod
    def _update_cell(self, sender, instance, **kwargs):
        """
        Always get latest revision and set values. Used when adding
        new or when deleting the latest

        """
        try:
            rev = instance.cell.cellrevision_set.latest()
        except Cell.DoesNotExist:
            # when delering the cell, safe to return
            return

        if rev.name:
            instance.cell.name = rev.name

        if rev.parent:
            instance.cell.parent = rev.parent

        instance.cell.save()

models.signals.post_save.connect(CellRevision._update_cell, sender=CellRevision)
models.signals.post_delete.connect(CellRevision._update_cell,
                                   sender=CellRevision)

class Share(models.Model):
    cell = models.ForeignKey(Cell)
    user = models.ForeignKey(User)
    mode = models.SmallIntegerField(choices=((1, 'Read Write'),
                                             (2, 'Read Only')
                                             ),
                                    default=1)
    name = models.CharField(max_length=500, blank=True)
    parent = models.ForeignKey(Cell, related_name='share_parent',
                               blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('cell', 'user'),)
        get_latest_by = "number"

    @classmethod
    def _clean_share(self, sender, instance, **kwargs):
        instance.clean()

    def clean(self):
        if self.cell.owner == self.user:
            raise ValidationError("cell.owner is the same person as user")

        if Share.objects.filter(cell__in=self.cell.get_ancestors()).count():
            # oups there is another cell higher in the tree shared. abort
            raise ValidationError("Tree is already shared from another cell")

        if self.name == '':
            self.name = self.cell.name

        if not self.parent:
            self.parent = Cell.objects.get(owner=self.user,
                                           name='melissi',
                                           parent=None)

        return super(Share, self).clean()

    def __unicode__(self):
        return "[%s:%s]" % (self.cell, self.user)

models.signals.pre_save.connect(Share._clean_share, sender=Share)

class Droplet(models.Model):
    name = models.CharField(max_length=500)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User)
    cell = models.ForeignKey(Cell)
    deleted = models.BooleanField(default=False)
    content = models.FileField(
        storage=FileSystemStorage(location=settings.MELISSI_STORE_LOCATION),
        upload_to=calculate_upload_path,
        blank=False,
        null=False)
    patch = models.FileField(
        storage=FileSystemStorage(location=settings.MELISSI_STORE_LOCATION),
        upload_to=calculate_upload_path,
        blank=True,
        null=True,
        validators=[PatchValidator()]
        )
    content_sha256 = models.CharField(max_length=64, null=False, blank=False)
    patch_sha256 = models.CharField(max_length=64, null=True, blank=True)
    revisions = models.PositiveIntegerField(default=0)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        # set owner always to cell.owner
        self.owner = self.cell.owner
        return super(Droplet, self).save(*args, **kwargs)

    def set_deleted(self):
        # set deleted
        self.deleted = True
        self.save()

    @classmethod
    def _first_revision_creator(self, sender, instance, **kwargs):
        if instance.dropletrevision_set.count() == 0:
            # create first revision
            revision = DropletRevision(droplet=instance,
                                       name = instance.name,
                                       content = instance.content,
                                       patch = instance.patch,
                                       content_sha256 = instance.content_sha256,
                                       patch_sha256 = instance.patch_sha256,
                                       resource=instance.owner.userresource_set.all()[0],
                                       cell=instance.cell,
                                       number=1)
            revision.save()

    @classmethod
    def _revision_count(self, sender, instance, **kwargs):
        if isinstance(instance, Droplet):
            instance.revisions = instance.dropletrevision_set.count()

        elif isinstance(instance, DropletRevision):
            try:
                instance.droplet.revisions = instance.droplet.dropletrevision_set.count()
                instance.droplet.save()
            except Droplet.DoesNotExist:
                # we are deleting the droplet, ignore
                return

models.signals.post_save.connect(Droplet._first_revision_creator, sender=Droplet)
models.signals.pre_save.connect(Droplet._revision_count, sender=Droplet)


class DropletRevision(models.Model):
    droplet = models.ForeignKey(Droplet)
    created = models.DateTimeField(auto_now_add=True)
    resource = models.ForeignKey("UserResource")
    name = models.CharField(max_length=500, blank=True, null=True)
    number = models.PositiveIntegerField()
    cell = models.ForeignKey(Cell, blank=True, null=True)
    content = models.FileField(
        storage=FileSystemStorage(location=settings.MELISSI_STORE_LOCATION),
        upload_to=calculate_upload_path,
        blank=True,
        default=None,
        null=True)
    patch = models.FileField(
        storage=FileSystemStorage(location=settings.MELISSI_STORE_LOCATION),
        upload_to=calculate_upload_path,
        blank=True,
        null=True,
        default=None,
        validators=[PatchValidator()]
        )
    content_sha256 = models.CharField(max_length=64, default=None,
                                      null=True, blank=True)
    patch_sha256 = models.CharField(max_length=64, default=None,
                                    null=True, blank=True)

    class Meta:
        unique_together = (('droplet', 'number'),)
        get_latest_by = "number"
        ordering = ("number",)

    @classmethod
    def _clean_dropletrevision(self, sender, instance, **kwargs):
        instance.clean()

    def clean(self):
        if self.content_sha256 == '':
            self.content_sha256 = None

        if self.patch_sha256 == '':
            self.patch_sha256 = None

        if self.content and not self.content_sha256:
            raise ValidationError("Cannot have content without content sha256")

        elif self.content and self.content_sha256:
            # verify hash
            if str(self.content_sha256) != calculate_sha256(self.content):
                raise ValidationError("Hashes do not match")


        # TODO patch match by applied before hash checking
        # if self.patch and not self.patch_sha256:
        #     raise ValidationError("Cannot have patch without patch sha256")

        # elif self.patch and self.patch_sha256:
        #     # verify hash
        #     if self.patch_sha256 != calculate_hash(self.patch):
        #         raise ValidationError("Hashes do not match")

        return super(DropletRevision, self).clean()

    @classmethod
    def _update_droplet(self, sender, instance, **kwargs):
        """
        Always get latest revision and set values. Used when adding
        new or when deleting the latest

        """
        try:
            rev = instance.droplet.dropletrevision_set.latest()
        except Droplet.DoesNotExist:
            # when deleting the droplet, safe to return
            return

        if rev.name:
            instance.droplet.name = rev.name

        if rev.cell:
            instance.droplet.cell = rev.cell

        if rev.content:
            instance.droplet.content = rev.content
            instance.droplet.content_sha256 = rev.content_sha256

        if rev.patch:
            instance.droplet.patch = rev.patch
            instance.droplet.patch_sha256 = rev.patch_sha256

        instance.droplet.save()

models.signals.post_save.connect(DropletRevision._update_droplet,
                                 sender=DropletRevision)
models.signals.post_delete.connect(DropletRevision._update_droplet,
                                   sender=DropletRevision)
models.signals.pre_save.connect(DropletRevision._clean_dropletrevision,
                                sender=DropletRevision)
models.signals.post_delete.connect(Droplet._revision_count, sender=DropletRevision)


class UserResource(models.Model):
    name = models.CharField(max_length=500, default="melissi")
    user = models.ForeignKey(User)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    # TODO with mysql innodb and utf8 :(
    # class Meta:
    #     unique_together = (('name', 'user'),)

    def __unicode__(self):
        return "[%s:%s]" % (self.user, self.name)

class UserProfile(models.Model):
    user = models.ForeignKey(User, unique=True)
    quota = models.PositiveIntegerField(default=settings.MELISSI_QUOTA)

    def __unicode__(self):
        return unicode(self.user)

def user_post_save(sender, instance, **kwargs):
    """
    Create
     - user profile,
     - default userresource and
     - root cell
    when the a user is created
    """
    profile, created = UserProfile.objects.get_or_create(user=instance)
    if created:
        profile.save()

    resource, created = UserResource.objects.get_or_create(user=instance)
    if created:
        resource.save()

    cell, created = Cell.objects.get_or_create(owner=instance,
                                               name='melissi',
                                               parent=None)
    if created:
        cell.save()

models.signals.post_save.connect(user_post_save, sender=User)
