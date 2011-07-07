#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Create 3 users
# Create a cell and a droplet for melissi user

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files import File

from mlscommon.models import *
import tempfile


class Command(BaseCommand):
    help = "Populate database with test data"

    def handle(self, *args, **options):
        # clean database
        f = tempfile.NamedTemporaryFile()
        f.write('12345')
        f.seek(0)

        User.objects.filter(is_superuser=False).delete()

        u = User.objects.create_user("melisi", "seadog@sealabs.net", "123")
        u.first_name = u"Νίκος"
        u.last_name = u"Κούκος"
        u.save()

        u1 = User.objects.create_user("babis", "babis@example.com", "123")
        u1.first_name = u"Μπάμπης"
        u1.last_name = u"Σουγιάς"
        u1.save()

        u2 = User.objects.create_user("mitsos", "mitsos@example.com", "123")
        u2.first_name = u"Mitsos"
        u2.last_name = u"Mitsaras"
        u2.save()

        c = Cell(owner=u,
                 parent=Cell.objects.get(owner=u,
                                         name="melissi",
                                         parent=None),
                 name="0"
                 )
        c.save()

        d = Droplet(name="d0",
                    owner=u,
                    cell=c,
                    content_sha256='5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5',
                    )

        d.content.save('do', File(f))

        d.save()
