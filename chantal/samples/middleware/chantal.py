#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import locale, re
from django.utils.cache import patch_vary_headers
from django.utils import translation
from django.template import loader, RequestContext
from django.contrib.auth.models import SiteProfileNotAvailable
from samples.models import UserDetails
from samples.views import utils
from samples.permissions import PermissionError
from django.conf import settings
from django.utils.translation import ugettext as _
import django.http
from django.shortcuts import render_to_response

u"""Middleware for handling samples-database-specific exceptions.
"""


# FixMe: Should be taken from ``chantal_common.utils``.  Watch out also for
# other occurences of this class.

class HttpResponseUnauthorized(django.http.HttpResponse):
    u"""The response sent back in case of a permission error.  This is another
    missing response class in Django.  I have no clue why they leave out such
    trivial code.
    """
    status_code = 401


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
            if utils.is_remote_client(request):
                return utils.respond_to_remote_client(False)
        elif isinstance(exception, PermissionError):
            return HttpResponseUnauthorized(
                loader.render_to_string("permission_error.html", {"title": _(u"Access denied"), "exception": exception},
                                        context_instance=RequestContext(request)))
        elif isinstance(exception, utils.AmbiguityException):
            render_to_response("disambiguation.html", {"alias": exception.sample_name, "samples": exception.samples,
                                                       "title": _("Ambiguous sample name")},
                               context_instance=RequestContext(request))
