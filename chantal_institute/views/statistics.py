#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
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

import memcache
from django.utils.translation import ugettext as _
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings
import django


def about(request):
    """The “about” view.  It displays general superficial information about
    Chantal.  This view is more or less static – it shows only the components
    of Chantal and versioning information.

    Note that you needn't be logged in for accessing this.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    django_version = django.get_version()
    return render_to_response("chantal_institute/about.html",
                              {"title": _("Chantal is presented to you by …"),
                               "language_version": settings.PYTHON_VERSION,
                               "matplotlib_version": settings.MATPLOTLIB_VERSION,
                               "framework_version": django_version,
                               },
                              context_instance=RequestContext(request))
