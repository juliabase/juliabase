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


u"""Additional context processors for Chantal.  There functions must be added
to `settings.TEMPLATE_CONTEXT_PROCESSORS`.  They add further data to the
dictionary passed to the templates.
"""

from __future__ import absolute_import

from django.utils.http import urlquote, urlquote_plus
import django.core.urlresolvers
from django.utils.translation import ugettext as _


def default(request):
    u"""Injects some session data into the template context.  At the same time,
    it removes them from the session data so that the next view has to re-set
    them.  Obviously, this is meant to things that are displyed only once: the
    last DB access time, a possible success report in green colour à la “sample
    x was added sucessfully”.

    Additionally, the help link on the top (see the
    `samples.views.utils.help_link` decorator) is added to the context by
    extracting it (and removing it from) the request object.  It cannot be in
    the session because this would reset the cache every time it is used.
    FixMe: What is the previous sentence supposed to mean?

    And finally, it adds tuples with information needed to realise the neat
    little flags on the top left for language switching.  These flags don't
    occur if it was a POST request, or if the user isn't logged-in.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the (additional) context dictionary

    :rtype: dict mapping str to session data
    """
    result = {}
    for key in ["db_access_time_in_ms", "success_report"]:
        if key in request.session:
            result[key] = request.session[key]
            del request.session[key]
    if hasattr(request, "chantal_help_link"):
        result["help_link"] = request.chantal_help_link
        del request.chantal_help_link
    # Now for the flags for the language switching
    if request.method == "GET" and request.user.is_authenticated():
        old_query_string = request.META["QUERY_STRING"] or u""
        if old_query_string:
            old_query_string = "?" + old_query_string
        switch_language_url = django.core.urlresolvers.reverse("chantal_common.views.switch_language").replace("%", "%%") + \
            "?lang=%s&next=" + urlquote_plus(request.path+old_query_string).replace("%", "%%")
        pootle_string = "/trac/chantal/wiki/HumanLanguages"
        result["translation_flags"] = (("de", _(u"German"), switch_language_url % "de"),
                                       ("en", _(u"English"), switch_language_url % "en"),
                                       ("zh_CN", _(u"Chinese"), pootle_string),
                                       ("uk", _(u"Ukrainian"), pootle_string),
                                       ("ru", _(u"Russian"), pootle_string),
                                       ("fr", _(u"French"), pootle_string),
                                       ("nl", _(u"Dutch"), pootle_string),
                                       )
    else:
        result["translation_flags"] = ()
    return result
