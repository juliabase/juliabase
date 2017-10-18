#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Views with statistical data visualisation, and the “about” view.  So far, I
have only one statistics page with cache status data.  However, one can extend
this in the institution's app.
"""

import sys
import matplotlib
from django.views.decorators.cache import cache_page, cache_control
from django.utils.translation import ugettext as _
from django.shortcuts import render
from django.db import connection
from django.conf import settings
import django
from jb_common import __version__
import jb_common.utils.base as utils


def statistics(request):
    """View for various internal server statistics and plots.  Note that you
    needn't be logged in for accessing this.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    return render(request, "samples/statistics.html",
                  {"title": _("JuliaBase server statistics"),
                   "cache_hit_rate": int(round((utils.cache_hit_rate() or 0) * 100))})


@cache_control(max_age=0)  # This is for language switching
@cache_page(3600)
def about(request):
    """The “about” view.  It displays general superficial information about
    JuliaBase.  This view is more or less static – it shows only the components
    of JuliaBase and versioning information.

    Note that you needn't be logged in for accessing this.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    context = {"title": _("With kind support of …"),
               "language_version": sys.version.split()[0],
               "matplotlib_version": matplotlib.__version__,
               "framework_version": django.get_version(),
               "juliabase_version": __version__
    }
    db_configuration = settings.DATABASES.get("default", {})
    db_backend = db_configuration.get("ENGINE")
    if db_backend == "django.db.backends.postgresql":
        cursor = connection.cursor()
        cursor.execute("SELECT version()")
        context["postgresql_version"] = cursor.fetchone()[0].split()[1]
    return render(request, "samples/about.html", context)
