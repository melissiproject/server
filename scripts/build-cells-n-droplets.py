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

u = User.create_user("melisi", "123", "seadog@sealabs.net")
u.first_name = u"Νίκος"
u.last_name = u"Κούκος"
u.save()
C = Cell(name="melisi", owner=u)
C.save()
for i in range(1):
    c = Cell(name=str(i), owner=u, roots=[C])
    c.save()

    for k in range(2):
        c2 = Cell(name='-'.join(map(lambda x: str(x), [i,k])), owner=u, roots=[c,C])
        c2.save()
        for j in range(1):
            c3 = Cell(name='-'.join(map(lambda x: str(x), [i,k,j])), owner=u, roots=[c2, c, C])
            c3.save()

            # droplets
            d = Droplet(owner=u, cell=c3, name='d%s' % i)

            with open("/tmp/foobar") as f:
                r = Revision(user=u, content=f)
            d.revisions.append(r)
            d.save()


    # droplets
    d = Droplet(owner=u, cell=c, name='d%s' % i)

    with open("/tmp/foobar") as f:
        r = Revision(user=u, content=f)
    d.revisions.append(r)
    d.save()
