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


"""Views with statistical data visualisation, and the “about” view.  So far, I
have only one comprehensive statistics page.  However, I need many helper
functions for it.
"""

from __future__ import absolute_import, division, unicode_literals

import sys
try:
    import memcache
except ImportError:
    memcache = None
import matplotlib
from django.utils.translation import ugettext as _
from django.shortcuts import render
from django.conf import settings
import django
from jb_common import utils, __version__


def get_cache_connections():
    """Returns the connections statistics of the memcached servers in the
    cluster.

    :Return:
      the total number of current memcached connections, the maximal number of
      current memcached connections, or ``(0, 0)`` if memcached is not used

    :rtype: int, int
    """
    if memcache and settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.memcached.MemcachedCache":
        memcached_client = memcache.Client(settings.CACHES["default"]["LOCATION"])
        servers = memcached_client.get_stats()
        number_of_servers = len(servers)
        connections = sum(int(server[1]["curr_connections"]) for server in servers)
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

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return render(request, "samples/statistics.html",
                  {"title": _("JuliaBase server statistics"),
                   "cache_hit_rate": int(round((utils.cache_hit_rate() or 0) * 100)),
                   "cache_connections": get_cache_connections()})


def about(request):
    """The “about” view.  It displays general superficial information about
    JuliaBase.  This view is more or less static – it shows only the components
    of JuliaBase and versioning information.

    Note that you needn't be logged in for accessing this.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return render(request, "samples/about.html", {"title": _("With kind support of …"),
                                                  "language_version": sys.version.split()[0],
                                                  "matplotlib_version": matplotlib.__version__,
                                                  "framework_version": django.get_version(),
                                                  "juliabase_version": __version__
                                              })
