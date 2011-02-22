from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^melisi/', include('melisi.foo.urls')),

    # almighty melisi API
    (r'^api/', include('melisi.api.urls')),
)
