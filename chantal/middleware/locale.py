from __future__ import absolute_import

import locale
from django.utils.cache import patch_vary_headers
from django.utils import translation
from django.contrib.auth.models import SiteProfileNotAvailable
from chantal.samples.models import UserDetails
from django.conf import settings

class LocaleMiddleware(object):
    """This is a very simple middleware that parses a request and decides what
    translation object to install in the current thread context depending on the
    user's profile. This allows pages to be dynamically translated to the
    language the user desires (if the language is available, of course).
    """
    def get_language_for_user(self, request):
        if request.user.is_authenticated():
            try:
                language = request.user.get_profile().language
                return language
            except (SiteProfileNotAvailable, UserDetails.DoesNotExist):
                pass
        return translation.get_language_from_request(request)
    def process_request(self, request):
        language = self.get_language_for_user(request)
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()
        # Now for the locale, but only if necessary because it seems to be a
        # costly operation.
        new_locale = settings.LOCALES_DICT.get(language)
        old_locale = locale.getlocale()[0]
        if not old_locale or not new_locale.startswith(old_locale):
            locale.setlocale(locale.LC_ALL, new_locale or "C")
    def process_response(self, request, response):
        patch_vary_headers(response, ("Accept-Language",))
        response["Content-Language"] = translation.get_language()
        translation.deactivate()
        return response
