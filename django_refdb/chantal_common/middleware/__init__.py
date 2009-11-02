#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.  Django-RefDB is published under the MIT
# license.  A copy of this licence is shipped with Django-RefDB in the file
# LICENSE.


from __future__ import absolute_import

import locale, re
from django.utils.cache import patch_vary_headers
from django.utils import translation
from django.template import loader, RequestContext
from django.contrib.auth.models import SiteProfileNotAvailable
from refdb.models import UserDetails
from django.conf import settings
from django.utils.translation import ugettext as _
import django.http
from django.shortcuts import render_to_response
from ..views import utils

u"""Middleware for setting the current language to what can be found in
`models.UserDetails`.
"""


class LocaleMiddleware(object):
    u"""This is a very simple middleware that parses a request and decides what
    translation object to install in the current thread context depending on
    what's found in `models.UserDetails`. This allows pages to be dynamically
    translated to the language the user desires (if the language is available,
    of course).
    """
    language_pattern = re.compile("[a-zA-Z0-9]+")

    @staticmethod
    def get_language_for_user(request):
        if request.user.is_authenticated():
            try:
                language = request.user.get_profile().language
                return language
            except (SiteProfileNotAvailable, UserDetails.DoesNotExist):
                pass
        return translation.get_language_from_request(request)

    def get_language_code_only(self, language):
        match = self.language_pattern.match(language)
        return match.group(0) if match else "en"

    def process_request(self, request):
        language = self.get_language_for_user(request)
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()
        # Now for the locale, but only if necessary because it seems to be a
        # costly operation.
        new_locale = settings.LOCALES_DICT.get(self.get_language_code_only(language))
        old_locale = locale.getlocale()[0]
        if not old_locale or not new_locale.startswith(old_locale):
            locale.setlocale(locale.LC_ALL, new_locale or "C")

    def process_response(self, request, response):
        patch_vary_headers(response, ("Accept-Language",))
        response["Content-Language"] = translation.get_language()
        translation.deactivate()
        return response
