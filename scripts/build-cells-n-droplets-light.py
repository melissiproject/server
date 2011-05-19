#!/usr/bin/env python
# -*- coding: utf-8 -*-

# setup enviroment
import settings
from django.core.management import setup_environ
setup_environ(settings)

from mlscommon.entrytypes import *

# create 5 cells with 2 child cells with 1 child cell
# the first level has one droplet per cell
# the last level has two droplets per cell

# clear db
map(lambda x: x.delete(), Droplet.objects.all())
map(lambda x: x.delete(), User.objects.all())
map(lambda x: x.delete(), Cell.objects.all())
map(lambda x: x.delete(), UserResource.objects.all())

u = MelissiUser.create_user("melisi", "seadog@sealabs.net", "123")
u.first_name = u"Νίκος"
u.last_name = "Koykos"
u.save()

ur = UserResource.objects.all()[0]

u1 = MelissiUser.create_user("babis", "babis@example.com", "123")
u1.first_name = u"Μπάμπης"
u1.last_name = u"Σουγιάς"
u1.save()

u2 = MelissiUser.create_user("mitsos", "mitsos@example.com", "123")
u2.first_name = u"Mitsos"
u2.last_name = u"Mitsaras"
u2.save()

C = Cell.objects.get(owner=u)
for i in range(1):
    c = Cell(revisions=[CellRevision(name=str(i), resource=ur)], owner=u, roots=[C])
    c.save()

    # droplets
    d = Droplet(owner=u, cell=c, name='d%s' % i)
    with open("/tmp/foobar") as f:
        r = DropletRevision(resource=ur, content=f, name='d%s' % i )
    d.revisions.append(r)
    d.save()
