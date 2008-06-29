from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # Example:
    # (r'^chantal/', include('chantal.foo.urls')),

    # Uncomment this for admin:
     (r'^admin/', include('django.contrib.admin.urls')),
)
