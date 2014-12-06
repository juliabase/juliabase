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
# Copyright © 2010 Torsten Bronger <bronger@physik.rwth-aachen.de>


"""Root URL dispach for testing the “inm” app.
"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static


urlpatterns = patterns("",
                       (r"", include("jb_common.urls")),
                       (r"", include("samples.urls")),
                       (r"", include("inm.urls")),
                       )

urlpatterns += patterns("",
    (r"^admin/", include(admin.site.urls)),
)

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
