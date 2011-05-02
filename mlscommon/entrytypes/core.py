from django import forms
from django.conf import settings

from datetime import datetime, date

from mongoengine import *
from mongoengine.django.auth import User
from mongoengine.queryset import QuerySet
from mongoengine.base import ValidationError as MongoValidationError

class MelissiUser(User):
    @classmethod
    def create_user(cls, username, email, password, resource=None):
        user = super(MelissiUser, cls).create_user(username, email, password)
        # create (default) user resource
        if not resource:
            resource = 'default'
        user_resource = UserResource(name=resource, user=user)
        user_resource.save()

        # create melissi cell
        cell = Cell(owner=user,
                    roots=[],
                    revisions=[CellRevision(name='melissi', resource=user_resource)]
                    )

        cell.save()

        return user

class UserResource(Document):
    name = StringField(required=True)
    user = ReferenceField(User, required=True)
    created = DateTimeField(required=True, default=datetime.now)
    updated = DateTimeField(required=True)

    def save(self):
        self.updated = datetime.now()
        super(UserResource, self).save()

    def __unicode__(self):
        return "User: %s Resource: %s" % (self.user, self.name)

    def __repr__(self):
        # I don't want to prepend the model type before __unicode__
        # e.g. I just want __unicode__() value and not <Cell - __unicode__()>
        #
        return self.__unicode__()


class Share(EmbeddedDocument):
    user = ReferenceField(User)
    mode = StringField(required=True)
    name = StringField(required=True)
    roots = ListField(ReferenceField("Cell"))
    created = DateTimeField(required=True, default=datetime.now)

    def __unicode__(self):
        return "%s - %s" % (self.user, self.mode)

class CellRevision(EmbeddedDocument):
    resource = ReferenceField(UserResource, required=True)
    created = DateTimeField(required=True, default=datetime.now)
    name = StringField(required=True)

class Cell(Document):
    owner = ReferenceField(User, required=True)
    shared_with = ListField(EmbeddedDocumentField(Share))
    roots = ListField(ReferenceField("Cell"))
    deleted = BooleanField(default=False, required=True)
    revisions = ListField(EmbeddedDocumentField(CellRevision))
    name = StringField(required=True)
    created = DateTimeField(required=True, default=datetime.now)
    updated = DateTimeField(required=True)

    # nah not pythonic
    meta = {
        'indexes': ('shared_with', 'roots'),
        }

    def __unicode__(self):
        return str(self.id)

    def __repr__(self):
        # I don't want to prepend the model type before __unicode__
        # e.g. I just want __unicode__() value and not <Cell - __unicode__()>
        #
        return self.__unicode__()

    def validate(self):
        # ensure that cell has at least one revisions
        if len(self.revisions) == 0:
            raise MongoValidationError("Cell must have at least one revision")

        # ensure that shared_with does not contain the same user twice

        # ensure that shared_with has values only for one cell in a tree
        if len(self.shared_with) and Cell.objects.filter(pk__in = self.roots,
                                                         shared_with__not__size = 0).count():
            raise MongoValidationError("Multiple shares in the same tree")

        # if roots = [] ensure that name and owner are unique
        # TODO optimize query
        q = Cell.objects.filter(owner = self.owner,
                                roots__size = 0,
                                deleted = False,
                                )
        for c in q:
            if c and c.name == self.name and ( self.pk and self.pk != c.pk ):
                raise MongoValidationError("Name not unique %s, cell: %s" %\
                                           (self.name, self.roots[0] if len(self.roots) else 'root'))

    def save(self):
        # TODO until we fix mongoengine to support auto_now_add and auto_now

        self.updated = self.revisions[-1].created
        self.name = self.revisions[-1].name
        super(Cell, self).save()

    def set_deleted(self):
        # set deleted all related droplets
        cells = Cell.objects.filter(Q(roots__contains = self.pk) |\
                                Q(pk=self.pk))
        Droplet.objects(cell__in=cells).update(set__deleted=True)
        cells.update(set__deleted=True)

        # reload cell to update values
        self.reload()

        # save self to update updated timestamp
        self.save()

    def delete(self):
        # delete all related droplets
        map(lambda x: x.delete(), Droplet.objects.filter(cell=self))
        map(lambda x: x.delete(), Cell.objects(roots__contains = self.pk))

        super(Cell, self).delete()

class DropletRevision(EmbeddedDocument):
    name = StringField(required=False)
    resource = ReferenceField(UserResource, required=True)
    created = DateTimeField(required=True, default=datetime.now)
    content = FileField(required=True)
    patch = FileField(required=False)

    @property
    def content_md5(self):
        try:
            return self.content.md5
        except AttributeError:
            return None

    @property
    def patch_md5(self):
        try:
            return self.patch.md5
        except AttributeError:
            return None

class Droplet(Document):
    name = StringField(required=True)
    owner = ReferenceField(User, required=True)
    created = DateTimeField(required=True, default=datetime.now)
    updated = DateTimeField(required=True, default=datetime.now)
    cell = ReferenceField(Cell, required=True)
    revisions = ListField(EmbeddedDocumentField(DropletRevision))
    deleted = BooleanField(default=False, required=True)

    meta = {
        'indexes': ['revisions', 'cell']
        }

    # def validate(self):
    #     """ Droplet can have zero revisions """
    #     q = Droplet.objects.get(name = self.name,
    #                             cell = self.cell,
    #                             deleted = False,
    #                             )
    #     if q.count() and (self.pk and
    #     if self.pk and Droplet.objects.filter(name = self.name,
    #                                           cell = self.cell,
    #                                           deleted = False,
    #                                           pk__ne = self.pk
    #                                           ).count():
    #         raise MongoValidationError("Name not unique %s, cell: %s" %\
    #                                    (self.name, self.cell))
    #     elif not self.pk and Droplet.objects.filter(name = self.name,
    #                                                 cell = self.cell,
    #                                                 deleted = False,
    #                                                 ).count():
    #         raise MongoValidationError("Name not unique %s, cell: %s" %\
    #                                    (self.name, self.cell))

    def set_deleted(self):
        # set deleted all related droplets
        self.deleted = True

        # save self to update updated timestamp
        self.save()

    def save(self):
        # TODO until we fix mongoengine to support auto_now_add and auto_now
        self.updated = datetime.now()
        super(Droplet, self).save()

    def delete(self):
        """
        Delete all content before deleting the droplet itself. Note
        though that since we are going to use the content to multiple
        revisions we must first check that the content is not used
        anywhere else.
        """
        map(lambda x: x.content.delete(), self.revisions)

        super(Droplet, self).delete()
