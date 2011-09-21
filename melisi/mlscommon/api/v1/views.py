import hashlib
from datetime import datetime

from piston.handler import PistonView, Field


class UserView(PistonView):
    fields = [
        'id',
        'username',
        'email',
        'first_name',
        'last_name',
        Field('',
              lambda x: ' '.join((x.first_name, x.last_name)),
              destination='full_name'),
        Field('last_login', lambda x: x.isoformat()),
        Field('email',
              lambda x: hashlib.md5(x).hexdigest(),
              destination='email_md5'),
        ]

class CellView(PistonView):
    fields = [
        'id',
        'name',
        Field('owner', lambda x: UserView(x)),
        'pid',
        Field('created', lambda x: x.isoformat()),
        Field('updated', lambda x: x.isoformat()),
        'deleted',
        'revisions',
        ]

class CellListView(PistonView):
    fields = [
        Field('',
              lambda x: CellView(x),
              destination='cells')
        ]

class DropletView(PistonView):
    fields = [
        'id',
        'name',
        Field('cell', lambda x: CellView(x)),
        Field('owner', lambda x: UserView(x)),
        Field('created', lambda x: x.isoformat()),
        Field('updated', lambda x: x.isoformat()),
        'deleted',
        'content_sha256',
        'patch_sha256',
        'revisions',
        ]

class DropletListView(PistonView):
    fields = [
        Field('',
              lambda x: DropletView(x),
              destination='droplets')
        ]

class ResourceView(PistonView):
    fields = [
        'name',
        Field('user', lambda x: UserView(x)),
        ]

class DropletRevisionView(PistonView):
    fields = [
        Field('resource', lambda x: ResourceView(x)),
        Field('created', lambda x: x.isoformat()),
        'content_sha256',
        'patch_sha256',
        ]

class CellShareView(PistonView):
    fields = [
        Field('user', lambda x: UserView(x)),
        'mode',
        Field('', lambda x: x.get_mode_display(), destination="mode_repr"),
        'name',
        Field('created', lambda x: x.isoformat()),
        Field('updated', lambda x: x.isoformat()),
        ]

class CellShareListView(PistonView):
    fields = [
        Field('',
              lambda x: [CellShareView(y) for y in x],
              destination="shares"),
        ]

