#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
# Copyright © 2010 Torsten Bronger <bronger@physik.rwth-aachen.de>


"""Root URL dispach for testing the “institute” app.
"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static


urlpatterns = patterns("",
                       (r"", include("jb_common.urls")),
                       (r"", include("samples.urls")),
                       (r"", include("institute.urls")),
                       )

urlpatterns += patterns("",
    (r"^admin/", include(admin.site.urls)),
)

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
