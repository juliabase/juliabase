#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
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

from __future__ import absolute_import, division, unicode_literals

import sys
try:
    import memcache
except ImportError:
    memcache = None
import matplotlib
from django.views.decorators.cache import cache_page, cache_control
from django.utils.translation import ugettext as _
from django.shortcuts import render
from django.db import connection
from django.conf import settings
import django
from jb_common import __version__
import jb_common.utils.base as utils


def get_cache_connections():
    """Returns the connections statistics of the memcached servers in the
    cluster.

    :return:
      the total number of current memcached connections, the maximal number of
      current memcached connections, or ``(0, 0)`` if memcached is not used

    :rtype: int, int
    """
    if memcache and settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.memcached.MemcachedCache":
        memcached_client = memcache.Client(settings.CACHES["default"]["LOCATION"])
        servers = memcached_client.get_stats()
        number_of_servers = len(servers)
        connections = sum(int(server[1][b"curr_connections"]) for server in servers)
    else:
        number_of_servers = 0
        connections = 0
    max_connections = 0
    try:
        for line in open("/etc/memcached.conf"):
            if line.startswith("-c"):
                max_connections = int(line.split()[1])
                break
        else:
            max_connections = 1024
    except:
        pass
    max_connections *= number_of_servers
    return connections, max_connections


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
                   "cache_hit_rate": int(round((utils.cache_hit_rate() or 0) * 100)),
                   "cache_connections": get_cache_connections()})


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
    if db_backend == "django.db.backends.postgresql_psycopg2":
        cursor = connection.cursor()
        cursor.execute("SELECT version()")
        context["postgresql_version"] = cursor.fetchone()[0].split()[1]
    return render(request, "samples/about.html", context)
