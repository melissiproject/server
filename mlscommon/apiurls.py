from django.conf.urls.defaults import *
from piston.authentication import HttpBasicAuthentication
from resource import Resource

from apihandlers import CellHandler, CellShareHandler

basic_auth = HttpBasicAuthentication(realm='melissi')
cell_handler = Resource(CellHandler, authentication=basic_auth)
cell_share_handler = Resource(CellShareHandler, authentication=basic_auth)

urlpatterns = patterns(
    '',
    (r'^cell/(?P<cell_id>\d+)/$', cell_handler),
    (r'^cell/(?P<cell_id>\d+)/share/$', cell_share_handler),
    (r'^cell/(?P<cell_id>\d+)/share/(?P<user_id>\d+)/$', cell_share_handler),
    (r'^cell/$', cell_handler)
    )
