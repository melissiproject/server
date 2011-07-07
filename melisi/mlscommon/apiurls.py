from django.conf.urls.defaults import *
from piston.authentication import HttpBasicAuthentication
from resource import Resource

from apihandlers import CellHandler, CellShareHandler, DropletHandler,\
     DropletRevisionDataHandler, DropletRevisionHandler, UserHandler,\
     StatusHandler

basic_auth = HttpBasicAuthentication(realm='melissi')
cell_handler = Resource(CellHandler, authentication=basic_auth)
cell_share_handler = Resource(CellShareHandler, authentication=basic_auth)
droplet_handler = Resource(DropletHandler, authentication=basic_auth)
droplet_revision_data_handler = Resource(DropletRevisionDataHandler, authentication=basic_auth)
droplet_revision_handler = Resource(DropletRevisionHandler, authentication=basic_auth)
user_handler = Resource(UserHandler, authentication=basic_auth)
status_handler = Resource(StatusHandler, authentication=basic_auth)

urlpatterns = patterns(
    '',
    (r'^cell/(?P<cell_id>\d+)/$', cell_handler),
    (r'^cell/(?P<cell_id>\d+)/share/$', cell_share_handler),
    (r'^cell/(?P<cell_id>\d+)/share/(?P<username>[\w.@+-]+)/$', cell_share_handler),
    (r'^cell/$', cell_handler),

    (r'^droplet/$', droplet_handler),
    (r'^droplet/(?P<droplet_id>\d+)/$', droplet_handler),

    (r'^droplet/(?P<droplet_id>\d+)/revision/$',
     droplet_revision_handler),
    (r'^droplet/(?P<droplet_id>\d+)/revision/(?P<revision_number>\d+)/$',
     droplet_revision_handler),
    (r'^droplet/(?P<droplet_id>\d+)/revision/(?P<revision_number>\d+)/content/$',
     droplet_revision_data_handler,  {'type':'content'}),
    (r'^droplet/(?P<droplet_id>\d+)/revision/(?P<revision_number>\d+)/patch/$',
     droplet_revision_data_handler,  {'type':'patch'}),
    (r'^droplet/(?P<droplet_id>\d+)/revision/latest/content/$',
     droplet_revision_data_handler, {'type':'content'}),
    (r'^droplet/(?P<droplet_id>\d+)/revision/latest/patch/$',
     droplet_revision_data_handler, {'type':'patch'}),

    (r'^status/all/$', status_handler, {'timestamp': 0}),
    (r'^status/after/(?P<timestamp>\d+\.?\d*)/$', status_handler),
    (r'^status/$', status_handler),

    (r'^user/(?P<user_id>\d+)/$', user_handler),
    (r'^user/$', user_handler),


    )
