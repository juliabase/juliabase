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


u"""Additional context processors for Chantal.  There functions must be added
to `settings.TEMPLATE_CONTEXT_PROCESSORS`.  They add further data to the
dictionary passed to the templates.
"""

from __future__ import absolute_import

from django.utils.http import urlquote, urlquote_plus
import django.core.urlresolvers
from django.conf import settings
from django.utils.translation import ugettext as _


def default(request):
    u"""Injects some session data into the template context.

    The help link on the top (see the `samples.views.utils.help_link`
    decorator) is added to the context by extracting it (and removing it from)
    the request object.

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
    if hasattr(request, "chantal_help_link"):
        result["help_link"] = request.chantal_help_link
        del request.chantal_help_link
    # Now for the flags for the language switching
    if request.method == "GET" and request.user.is_authenticated():
        old_query_string = request.META["QUERY_STRING"] or u""
        if old_query_string:
            old_query_string = "?" + old_query_string
        def get_language_url(language_code):
            url = django.core.urlresolvers.reverse("chantal_common.views.switch_language")
            url += "?lang={0}&next=".format(language_code)
            url += urlquote_plus(request.path + old_query_string)
            return url
        rosetta_url = "https://translations.launchpad.net/chantal/trunk/+lang/{0}"
        result["translation_flags"] = (("de", _(u"German"), get_language_url("de")),
                                       ("en", _(u"English"), get_language_url("en")),
                                       ("zh_CN", _(u"Chinese"), rosetta_url.format("zh_CN")),
                                       ("uk", _(u"Ukrainian"), rosetta_url.format("uk")),
                                       ("ru", _(u"Russian"), rosetta_url.format("ru")),
                                       ("fr", _(u"French"), rosetta_url.format("fr")),
                                       ("nl", _(u"Dutch"), rosetta_url.format("nl")),
                                       )
    else:
        result["translation_flags"] = ()
    result["default_home_url"] = settings.LOGIN_REDIRECT_URL
    return result
