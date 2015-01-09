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


"""Additional context processors for JuliaBase.  These functions must be added
to ``settings.TEMPLATE_CONTEXT_PROCESSORS``.  They add further data to the
dictionary passed to the templates.
"""

from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.utils.translation import ugettext


def default(request):
    """Injects some session data into the template context.

    The help link on the top (see the `samples.utils.views.help_link`
    decorator) is added to the context by extracting it (and removing it from)
    the request object.

    Moreover, it adds tuples with information needed to realise the neat little
    flags on the top left for language switching.  These flags don't occur if
    it was a POST request, or if the user isn't logged-in.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the (additional) context dictionary

    :rtype: dict mapping str to session data
    """
    user = request.user
    result = {}
    try:
        result["help_link"] = request.juliabase_help_link
    except AttributeError:
        pass
    else:
        del request.juliabase_help_link
    result["url"] = request.path
    if request.GET:
        result["url"] += "?" + request.GET.urlencode()
    if user.is_authenticated():
        result["salutation"] = user.first_name or user.username
    if request.method == "GET":
        result["translation_flags"] = tuple((code, ugettext(language)) for code, language in settings.LANGUAGES)
    else:
        result["translation_flags"] = ()
    result["default_home_url"] = settings.LOGIN_REDIRECT_URL
    result["add_samples_view"] = settings.ADD_SAMPLES_VIEW
    return result
