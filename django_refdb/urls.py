from django.conf.urls.defaults import *
import django.contrib.auth.views
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
                       (r'^accounts/login/$', 'django.contrib.auth.views.login'),
                       (r"", include("refdb.urls")),
                       (r'^admin/', include(admin.site.urls)),
                       )
