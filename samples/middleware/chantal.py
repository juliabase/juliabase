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


from __future__ import absolute_import

import locale, re
from django.utils.cache import patch_vary_headers
from django.utils import translation
from django.template import loader, RequestContext
from django.contrib.auth.models import SiteProfileNotAvailable
from samples.models import UserDetails
from samples.views import utils
from samples.permissions import PermissionError
from chantal_common.utils import HttpResponseUnauthorized
from django.conf import settings
from django.utils.translation import ugettext as _
import django.http
from django.shortcuts import render_to_response

u"""Middleware for handling samples-database-specific exceptions.
"""

import json
from django.http import Http404


class ExceptionsMiddleware(object):
    u"""Middleware for catching all exceptions raised by views.  However, I
    handle only `PermissionError` and `AmbiguityException` here.  These
    exceptions mean a redirect in one way or another.  An HTTP 404 code is only
    handled here if the client was the Remote Client.

    It is important that this class is the last one in ``MIDDLEWARE_CLASSES``
    in the ``settings`` module, otherwise the above mentioned exceptions may
    propagate to other middleware which treats them as real errors.
    """

    def process_exception(self, request, exception):
        if isinstance(exception, django.http.Http404):
            if utils.is_json_requested(request):
                raise Http404(json.dumps(exception.args[0]))
        elif isinstance(exception, PermissionError):
            return HttpResponseUnauthorized(
                loader.render_to_string("samples/permission_error.html",
                                        {"title": _(u"Access denied"), "exception": exception},
                                        context_instance=RequestContext(request)))
        elif isinstance(exception, utils.AmbiguityException):
            return render_to_response("samples/disambiguation.html",
                                      {"alias": exception.sample_name, "samples": exception.samples,
                                       "title": _("Ambiguous sample name")},
                                      context_instance=RequestContext(request))
