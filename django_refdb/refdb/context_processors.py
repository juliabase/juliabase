#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.  Django-RefDB is published under the MIT
# license.  A copy of this licence is shipped with Django-RefDB in the file
# LICENSE.


u"""Additional context processors for Django-RefDB.  There functions must be
added to `settings.TEMPLATE_CONTEXT_PROCESSORS`.  They add further data to the
dictionary passed to the templates.
"""

from __future__ import absolute_import


def default(request):
    u"""Injects some data into the template context.  The only addition is the
    injection of the current URL into the context in the variable
    "http_query_string" and "current_url".

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the (additional) context dictionary

    :rtype: dict mapping str to session data
    """
    return {"http_query_string": request.META.get("QUERY_STRING", ""), "current_url": request.get_full_path()}
