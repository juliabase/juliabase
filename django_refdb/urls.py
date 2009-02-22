from django.conf.urls.defaults import *
import django.contrib.auth.views

urlpatterns = patterns('',
                       (r'^accounts/login/$', 'django.contrib.auth.views.login'),
                       (r"", include("refdb.urls")),
                       )
