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

urlpatterns = patterns("django.contrib.auth.views",
                       (r"^change_password$", "password_change", {"template_name": "chantal_common/change_password.html"}),
                       (r"^change_password/done/$", "password_change_done",
                        {"template_name": "chantal_common/password_changed.html"}),
                       (r"^login$", "login", {"template_name": "chantal_common/login.html"}),
                       (r"^logout$", "logout", {"template_name": "chantal_common/logout.html"}),
                       )
urlpatterns += patterns('',
                        (r'^admin/', include(admin.site.urls)),
                        (r"", include("chantal_common.urls")),
                        (r"", include("refdb.urls")),
                        )

if settings.IS_TESTSERVER:
    urlpatterns = patterns("",
                           (r"^media/(?P<path>.*)$", "django.views.static.serve",
                            {"document_root": settings.MEDIA_ROOT}),
                           ) + urlpatterns
