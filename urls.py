#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Root URL dispach for the JuliaBase installation.  Mapping URL patterns to
function calls.  This is the local URL dispatch of the Django application
“jb_common”, which provides core functionality and core views for all JuliaBase
apps.

:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/
"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls import url, include
from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static


urlpatterns = [
    url(r"", include("inm.urls")),
    url(r"", include("jb_common.urls")),
    url(r"", include("samples.urls")),

    url(r"^admin/", include(admin.site.urls)),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
