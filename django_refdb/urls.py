# -*- coding: utf-8 -*-
#
# Copyright © 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.
#
#     Django-RefDB is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public
#     License as published by the Free Software Foundation, either
#     version 3 of the License, or (at your option) any later
#     version.
#
#     Django-RefDB is distributed in the hope that it will be
#     useful, but WITHOUT ANY WARRANTY; without even the implied
#     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#     PURPOSE.  See the GNU Affero General Public License for more
#     details.
#
#     You should have received a copy of the GNU Affero General
#     Public License along with Django-RefDB.  If not, see
#     <http://www.gnu.org/licenses/>.


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

if settings.DEBUG:
    urlpatterns = patterns("",
                           (r"^media/(?P<path>.*)$", "django.views.static.serve",
                            {"document_root": settings.MEDIA_ROOT}),
                           ) + urlpatterns
