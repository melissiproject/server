from django.conf.urls.defaults import *
from piston.authentication import HttpBasicAuthentication
from resource import Resource

from apihandlers import CellHandler

basic_auth = HttpBasicAuthentication(realm='melissi')
cell_handler = Resource(CellHandler, authentication=basic_auth)

urlpatterns = patterns(
    '',
    (r'^cell/(?P<cell_id>\d+)/$', cell_handler),
    (r'^cell/$', cell_handler)
    )
