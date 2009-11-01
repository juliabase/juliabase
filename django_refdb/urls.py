# Copyright (c) 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.  Django-RefDB is published under the MIT
# license.  A copy of this licence is shipped with Django-RefDB in the file
# LICENSE.


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
    urlpatterns = patterns("",
                           (r"^media/(?P<path>.*)$", "django.views.static.serve",
                            {"document_root": os.path.join(settings.ROOTDIR, "media/")}),
                           ) + urlpatterns
