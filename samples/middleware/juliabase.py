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


from __future__ import absolute_import, unicode_literals

import locale, re
from django.utils.cache import patch_vary_headers
from django.utils import translation
from django.template import loader, RequestContext
from django.contrib.auth.models import SiteProfileNotAvailable
from samples.models import UserDetails
from samples.views import utils
from samples.permissions import PermissionError
from jb_common.utils import HttpResponseUnauthorized
from django.conf import settings
from django.utils.translation import ugettext as _
import django.http
from django.shortcuts import render_to_response

"""Middleware for handling samples-database-specific exceptions.
"""


# FixMe: A JSON client should see JSON responses.

class ExceptionsMiddleware(object):
    """Middleware for catching JuliaBase-samples-specific exceptions raised by
    views.  I handle only `PermissionError` and `AmbiguityException` here.
    These exceptions mean a redirect in one way or another.

    It is important that this class comes after non-JuliaBase middleware in
    ``MIDDLEWARE_CLASSES`` in the ``settings`` module, otherwise the above
    mentioned exceptions may propagate to other middleware which treats them as
    real errors.
    """

    def process_exception(self, request, exception):
        if isinstance(exception, PermissionError):
            return HttpResponseUnauthorized(
                loader.render_to_string("samples/permission_error.html",
                                        {"title": _("Access denied"), "exception": exception},
                                        context_instance=RequestContext(request)))
        elif isinstance(exception, utils.AmbiguityException):
            return render_to_response("samples/disambiguation.html",
                                      {"alias": exception.sample_name, "samples": exception.samples,
                                       "title": _("Ambiguous sample name")},
                                      context_instance=RequestContext(request))
