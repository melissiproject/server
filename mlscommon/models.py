from django.db import models

# Create your models here.
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.core.validators import MinLengthValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from mptt.models import MPTTModel

def calculate_upload_path(instance, filename):
    return "%s-%s" % (instance.droplet.id, instance.content)

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
                               related_name='children')

    def __unicode__(self):
        return "[%s:%s]" % (self.id, self.name)

    @classmethod
    def _first_revision_creator(self, sender, instance, **kwargs):
        if instance.cellrevision_set.count() == 0:
            # create first revision
            revision = CellRevision(cell=instance,
                                    resource=instance.owner.userresource_set.all()[0],
                                    parent=instance.parent)
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

models.signals.post_save.connect(Cell._first_revision_creator, sender=Cell)


class CellRevision(models.Model):
    cell = models.ForeignKey(Cell)
    name = models.CharField(max_length=500, null=True, blank=True)
    parent = models.ForeignKey(Cell, null=True, blank=True,
                               related_name='revision_parent')
    resource = models.ForeignKey("UserResource")
    created = models.DateTimeField(auto_now_add=True)

    @classmethod
    def _update_cell(self, sender, instance, **kwargs):
        """ when a cellrevision is added, update cell with new values """
        if instance.name:
            instance.cell.name = instance.name

        if instance.parent:
            instance.cell.parent = instance.parent

        instance.cell.save()

models.signals.post_save.connect(CellRevision._update_cell, sender=CellRevision)

class Share(models.Model):
    cell = models.ForeignKey(Cell)
    user = models.ForeignKey(User)
    mode = models.SmallIntegerField(choices=((1, 'Read Write'),
                                             (2, 'Read Only')
                                             ),
                                    default=1)
    name = models.CharField(max_length=500, blank=True)
    parent = models.ForeignKey(Cell, related_name='share_parent')

    class Meta:
        unique_together = (('cell', 'user'),)

    def clean(self):
        if self.cell.owner == self.user:
            raise ValidationError("cell.owner is the same person as user")

        if Share.objects.filter(cell__in=self.cell.get_ancestors()).count():
            # oups there is another cell higher in the tree shared. abort
            raise ValidationError("Tree is already shared from another cell")

        if self.name == '':
            self.name = self.cell.name

        return super(Share, self).clean()

    def __unicode__(self):
        return "[%s:%s]" % (self.cell, self.user)

class Droplet(models.Model):
    name = models.CharField(max_length=500)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User)
    cell = models.ForeignKey(Cell)
    deleted = models.BooleanField(default=False)
    content = models.FileField(
        storage=FileSystemStorage(location='/tmp/melissi-sandbox'),
        upload_to=calculate_upload_path,
        blank=True,
        null=True)
    patch = models.FileField(
        storage=FileSystemStorage(location='/tmp/melisi-sandbox/patches/'),
        upload_to=calculate_upload_path,
        blank=True,
        null=True,
        validators=[PatchValidator()]
        )

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        # set owner always to cell.owner
        self.owner = self.cell.owner
        return super(Droplet, self).save(*args, **kwargs)

    @classmethod
    def _first_revision_creator(self, sender, instance, **kwargs):
        if instance.dropletrevision_set.count() == 0:
            # create first revision
            revision = DropletRevision(droplet=instance,
                                       resource=instance.owner.userresource_set.all()[0],
                                       cell=instance.cell)
            revision.save()

models.signals.post_save.connect(Droplet._first_revision_creator, sender=Droplet)

class DropletRevision(models.Model):
    droplet = models.ForeignKey(Droplet)
    created = models.DateTimeField(auto_now_add=True)
    resource = models.ForeignKey("UserResource")
    name = models.CharField(max_length=500, blank=True, null=True)
    cell = models.ForeignKey(Cell, blank=True, null=True)
    content = models.FileField(
        storage=FileSystemStorage(location='/tmp/melissi-sandbox'),
        upload_to=calculate_upload_path,
        blank=True,
        null=True)
    patch = models.FileField(
        storage=FileSystemStorage(location='/tmp/melisi-sandbox/patches/'),
        upload_to=calculate_upload_path,
        blank=True,
        null=True,
        validators=[PatchValidator()]
        )

    @classmethod
    def _update_droplet(self, sender, instance, **kwargs):
        """ when a dropletrevision is added, update droplet with new values """
        if instance.name:
            instance.droplet.name = instance.name

        if instance.cell:
            instance.droplet.cell = instance.cell

        if instance.content:
            instance.droplet.content = instance.content

        if instance.patch:
            instance.droplet.patch = instance.patch

        instance.droplet.save()

models.signals.post_save.connect(DropletRevision._update_droplet,
                                 sender=DropletRevision)


class UserResource(models.Model):
    name = models.CharField(max_length=500, default="melissi")
    user = models.ForeignKey(User)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('name', 'user'),)

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
