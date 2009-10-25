import os.path
from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
                       (r'^accounts/login/$', 'django.contrib.auth.views.login'),
                       (r'^accounts/logout/$', 'django.contrib.auth.views.logout'),
                       (r'^admin/', include(admin.site.urls)),
                       (r"", include("refdb.urls")),
                       )

if settings.IS_TESTSERVER:
    urlpatterns += patterns("",
                            (r"^media/(?P<path>.*)$", "django.views.static.serve",
                             {"document_root": os.path.join(settings.ROOTDIR, "media/")}),
                            )
