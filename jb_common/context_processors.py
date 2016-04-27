#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""Additional context processors for JuliaBase.  These functions must be added
to ``settings.TEMPLATES[…]["OPTIONS"]["context_processors"]``.  They add
further data to the dictionary passed to the templates.
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
        result["help_link"] = settings.HELP_LINK_PREFIX + request.juliabase_help_link
    except AttributeError:
        pass
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
