# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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


import re, json, hashlib, random, time, logging
from django.contrib.messages.storage import default_storage
from django.utils.cache import patch_vary_headers, add_never_cache_headers
from django.utils import translation
from django.template import loader, RequestContext
from django.contrib.auth import logout
import django.urls
from jb_common.models import UserDetails, ErrorPage
from jb_common.utils.base import is_json_requested, JSONRequestException
from django.conf import settings
from django.utils.translation import ugettext as _
import django.http


"""Middleware classes for various totally unrelated things.
"""


class LocaleMiddleware:
    """This is a simple middleware that parses a request and decides what
    translation object to install in the current thread context depending on
    what's found in `models.UserDetails`. This allows pages to be dynamically
    translated to the language the user desires (if the language is available,
    of course).

    It must be after ``django.middleware.locale.LocaleMiddleware`` and
    ``AuthenticationMiddleware`` in the list.
    """
    language_pattern = re.compile("[a-zA-Z0-9]+")

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def get_language_for_user(request):
        if request.user.is_authenticated:
            try:
                language = request.user.jb_user_details.language
                return language
            except UserDetails.DoesNotExist:
                pass
        return translation.get_language_from_request(request)

    def __call__(self, request):
        if is_json_requested(request):
            # JSON responses are made for programs, so strings must be stable
            language = "en"
        else:
            language = self.get_language_for_user(request)
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

        response = self.get_response(request)

        patch_vary_headers(response, ("Accept-Language",))
        response["Content-Language"] = translation.get_language()
        translation.deactivate()
        return response


class MessageMiddleware:
    """Middleware that handles temporary messages.  It is a copy of Django's
    original ``MessageMiddleware`` but it adds cache disabling.  This way,
    pages with messages are never cached by the browser, so that the messages
    don't get persistent.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """Updates the storage backend (i.e., saves the messages).

        If not all messages could not be stored and ``DEBUG`` is ``True``, a
        ``ValueError`` is raised.
        """
        request._messages = default_storage(request)

        response = self.get_response(request)

        # A higher middleware layer may return a request which does not contain
        # messages storage, so make no assumption that it will be there.
        if hasattr(request, '_messages'):
            unstored_messages = request._messages.update(response)
            if unstored_messages and settings.DEBUG:
                raise ValueError('Not all temporary messages could be stored.')
            if request._messages.used:
                del response["ETag"]
                del response["Last-Modified"]
                response["Expires"] = "Fri, 01 Jan 1990 00:00:00 GMT"
                # FixMe: One should check whether the following settings are
                # sensible.
                response["Pragma"] = "no-cache"
                response["Cache-Control"] = "no-cache, no-store, max-age=0, must-revalidate, private"
        return response


class ActiveUserMiddleware:
    """Middleware to prevent a non-active user from using the site.  Unfortunately,
    ``is_active=False`` only prevents a user from logging in.  If he was
    already logged in before ``is_active`` was set to ``False`` and doesn't log
    out, he can use the site until the session is purged.  This middleware
    prevents this.

    Alternatively to this middleware, you can make sure that all the user's
    sessions are purged when he or she is set to inactive.

    This middleware must be after AuthenticationMiddleware in the list of
    installed middleware classes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_active:
            logout(request)
        return self.get_response(request)


class HttpResponseUnauthorised(django.http.HttpResponse):
    status_code = 401


class HttpResponseUnprocessableEntity(django.http.HttpResponse):
    status_code = 422


class JSONClientMiddleware:
    """Middleware to convert responses to JSON if this was requested by the client.

    It is important that this class comes after all non-JuliaBase middleware in
    ``MIDDLEWARE`` in the ``settings`` module, otherwise the ``Http404``
    exception may be already caught.  FixMe: Is this really the case?
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """Return a HTTP 422 response if a JSON response was requested and an HTML page
        with form errors is returned.
        """
        response = self.get_response(request)
        if is_json_requested(request) and response._headers["content-type"][1].startswith("text/html") and \
                response.status_code == 200:
            user = request.user
            if not user.is_authenticated:
                # Login view was returned
                return HttpResponseUnauthorised()
            hash_ = hashlib.sha1()
            hash_.update(str(random.random()).encode())
            # For some very obscure reason, a random number was not enough --
            # it led to collisions time after time.
            hash_.update(str(time.time()).encode())
            hash_value = hash_.hexdigest()
            ErrorPage.objects.create(hash_value=hash_value, user=user, requested_url=request.get_full_path(),
                                     html=response.content.decode())
            return HttpResponseUnprocessableEntity(
                json.dumps((1, request.build_absolute_uri(
                    django.urls.reverse("jb_common:show_error_page", kwargs={"hash_value": hash_value})))),
                content_type="application/json")
        return response

    def process_exception(self, request, exception):
        """Convert response to exceptions to JSONised version if the response
        is requested to be JSON.
        """
        if isinstance(exception, django.http.Http404):
            if is_json_requested(request):
                return django.http.HttpResponseNotFound(json.dumps((2, exception.args[0])), content_type="application/json")
        elif isinstance(exception, JSONRequestException):
            return HttpResponseUnprocessableEntity(json.dumps((exception.error_number, exception.error_message)),
                                                   content_type="application/json")


class UserTracebackMiddleware:
    """Adds user to request context during request processing, so that they show up
    in the error emails.  Taken from <http://stackoverflow.com/a/21158544>.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Convert response to exceptions to JSONised version if the response
        is requested to be JSON.
        """
        if request.user.is_authenticated:
            request.META["AUTH_USER"] = request.user.username
        else:
            request.META["AUTH_USER"] = "Anonymous User"


class LoggingMiddleware:
    """Keeps a request log at `settings.JB_LOGGING_PATH`.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("jb_common")
        self.logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(settings.JB_LOGGING_PATH)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(handler)

    def __call__(self, request):
        self.logger.info(f"{request.user} {request.method} {request.path}")
        return self.get_response(request)
