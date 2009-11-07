#!/usr/bin/env python
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
