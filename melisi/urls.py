from django.conf.urls.defaults import *
from django.views.generic.simple import redirect_to

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^melisi/', include('melisi.foo.urls')),

    url(r'^$', redirect_to, {'url': '/admin/'}),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),

    # almighty melisi API
    url(r'^api/v1/', include('melisi.mlscommon.api.v1.urls')),
)
