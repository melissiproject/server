from django.conf.urls.defaults import *
from piston.authentication import HttpBasicAuthentication

from utils import api_url, Resource
from handlers import CellHandler, CellShareHandler, DropletHandler,\
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
    api_url(r'^cell/(?P<cell_id>\d+)/$', cell_handler),
    api_url(r'^cell/(?P<cell_id>\d+)/share/$', cell_share_handler),
    api_url(r'^cell/(?P<cell_id>\d+)/share/(?P<username>[\w.@+-]+)/$', cell_share_handler),
    api_url(r'^cell/$', cell_handler),

    api_url(r'^droplet/$', droplet_handler),
    api_url(r'^droplet/(?P<droplet_id>\d+)/$', droplet_handler),

    api_url(r'^droplet/(?P<droplet_id>\d+)/revision/$',
     droplet_revision_handler),
    api_url(r'^droplet/(?P<droplet_id>\d+)/revision/(?P<revision_number>\d+)/$',
     droplet_revision_handler),
    api_url(r'^droplet/(?P<droplet_id>\d+)/revision/(?P<revision_number>\d+)/content/$',
     droplet_revision_data_handler,  {'type':'content'}),
    api_url(r'^droplet/(?P<droplet_id>\d+)/revision/(?P<revision_number>\d+)/patch/$',
     droplet_revision_data_handler,  {'type':'patch'}),
    api_url(r'^droplet/(?P<droplet_id>\d+)/revision/latest/content/$',
     droplet_revision_data_handler, {'type':'content'}),
    api_url(r'^droplet/(?P<droplet_id>\d+)/revision/latest/patch/$',
     droplet_revision_data_handler, {'type':'patch'}),

    api_url(r'^status/all/$', status_handler, {'timestamp': 0}),
    api_url(r'^status/after/(?P<timestamp>\d+\.?\d*)/$', status_handler),
    api_url(r'^status/$', status_handler),

    api_url(r'^user/(?P<user_id>\d+)/$', user_handler),
    api_url(r'^user/$', user_handler),


    )
