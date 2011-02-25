from django.conf.urls.defaults import *
from piston.resource import Resource
from piston.authentication import HttpBasicAuthentication
from django.views.generic.simple import redirect_to


from melisi.api.handlers import CellHandler, CellShareHandler, \
     DropletHandler, RevisionHandler, RevisionContentHandler, \
     RevisionPatchHandler, UserHandler

basic_auth = HttpBasicAuthentication(realm='melisi')
cell_handler = Resource(CellHandler, authentication=basic_auth)
cell_share_handler = Resource(CellShareHandler, authentication=basic_auth)
droplet_handler = Resource(DropletHandler, authentication=basic_auth)
# droplet_history_handler = Resource(DropletHistoryHandler, authentication=basic_auth)
revision_handler = Resource(RevisionHandler, authentication=basic_auth)
revision_content_handler = Resource(RevisionContentHandler, authentication=basic_auth)
revision_patch_handler = Resource(RevisionPatchHandler, authentication=basic_auth)
user_handler = Resource(UserHandler, authentication=basic_auth)

urlpatterns = patterns(
    '',
    (r'^cell/(?P<cell_id>\w+)/$', cell_handler),
    (r'^cell/(?P<cell_id>\w+)/share/$', cell_share_handler),
    (r'^cell/(?P<cell_id>\w+)/share/(?P<username>\w+)/$', cell_share_handler),
    (r'^cell/$', cell_handler),

    (r'^droplet/(?P<droplet_id>\w+)/$', droplet_handler),
    # (r'^droplet/(?P<droplet_id>\d+)/history/$', droplet_history_handler),
    (r'^droplet/(?P<droplet_id>\w+)/revision/$', revision_handler),
    (r'^droplet/(?P<droplet_id>\w+)/revision/latest/$', revision_handler),
    (r'^droplet/(?P<droplet_id>\w+)/revision/latest/content/$', revision_content_handler),
    (r'^droplet/(?P<droplet_id>\w+)/revision/latest/patch/$', revision_patch_handler),
    (r'^droplet/(?P<droplet_id>\w+)/revision/(?P<revision_id>\d+)/$', revision_handler),
    (r'^droplet/(?P<droplet_id>\w+)/revision/(?P<revision_id>\d+)/content/$', revision_content_handler),
    (r'^droplet/(?P<droplet_id>\w+)/revision/(?P<revision_id>\d+)/patch/$', revision_patch_handler),
    (r'^droplet/$', droplet_handler),

    (r'^user/(?P<username>\w+)/$', user_handler),
    # (r'^user/cells/$', user_cell_handler),
    (r'^user/$', user_handler),
    )
