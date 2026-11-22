# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2026 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


"""Every view requires a login (`jb_common.middleware.LoginRequiredMiddleware`)
unless it is explicitly public.  These tests prevent new views from being
public by accident.
"""

import re
from urllib.parse import quote
from django.conf import settings
from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.contrib.auth.models import AnonymousUser, User
from django.test import override_settings
from django.test.client import Client, RequestFactory
from django.urls import URLResolver, get_resolver, reverse
from django.views.static import serve
from samples import permissions
from samples.models import Sample
from .tools import TestCase


PUBLIC_URL_NAMES = {
    "login",
    "admin:login",
    "jb_common:jsi18n",
    # The remote client URLs have no names.
    "^login_remote_client$",
    "^logout_remote_client$",
    "samples:show_feed",
}
"""URL names of the intentionally public views.  Add a view here only together
with `django.contrib.auth.decorators.login_not_required` and a reason in its
code.
"""

REGEX_METACHARACTERS = re.compile(r"[()\[\]?*+\\{}|<]")


def walk_url_patterns(resolver, route_prefix="", namespace=""):
    """Yields the full route, the namespaced name (or the route if unnamed),
    and the pattern of every URL pattern.
    """
    for pattern in resolver.url_patterns:
        route = route_prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            sub_namespace = f"{namespace}{pattern.namespace}:" if pattern.namespace else namespace
            yield from walk_url_patterns(pattern, route, sub_namespace)
        else:
            name = f"{namespace}{pattern.name}" if pattern.name else route
            yield route, name, pattern


def path_without_parameters(route):
    """Returns the URL path of a route without parameters, or ``None``."""
    path = route.replace("^", "").replace("$", "")
    if REGEX_METACHARACTERS.search(path):
        return None
    return "/" + path


@override_settings(ROOT_URLCONF="urls")
class LoginRequiredTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.client = Client()

    def is_login_redirect(self, response, name):
        """Whether the response redirects to the login page; the admin has its
        own.
        """
        login_urls = (settings.LOGIN_URL, reverse("admin:login")) if name.startswith("admin:") else (settings.LOGIN_URL,)
        return response.status_code == 302 and response["Location"].startswith(login_urls)

    def test_middleware_follows_authentication_middleware(self):
        authentication_index = settings.MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
        self.assertEqual(settings.MIDDLEWARE[authentication_index + 1], "jb_common.middleware.LoginRequiredMiddleware")

    def test_only_allowlisted_views_are_public(self):
        public_names = {name for _route, name, pattern in walk_url_patterns(get_resolver())
                        if not getattr(pattern.callback, "login_required", True)}
        self.assertEqual(public_names, PUBLIC_URL_NAMES)

    def test_anonymous_get_is_redirected_to_login(self):
        """An anonymous GET of every URL without parameters ends at the login
        page.
        """
        checked_paths = []
        for route, name, _pattern in walk_url_patterns(get_resolver()):
            path = path_without_parameters(route)
            if path is None or name in PUBLIC_URL_NAMES:
                continue
            response = self.client.get(path)
            self.assertTrue(self.is_login_redirect(response, name), f"{path} ({name}) → {response.status_code}")
            checked_paths.append(path)
        self.assertIn(reverse("samples:main_menu"), checked_paths)
        self.assertGreater(len(checked_paths), 50)

    def test_static_files_are_public_but_serve_is_not(self):
        """With ``DEBUG``, the static files are served by Django (`urls.py`);
        the tests run without ``DEBUG``, so the views are checked directly.
        ``login_not_required`` flags the function it gets, so it must not flag
        ``serve``, which may serve non-public files elsewhere.
        """
        import urls
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        middleware = LoginRequiredMiddleware(lambda request: None)
        self.assertIs(getattr(serve, "login_required", True), True)
        self.assertIsNone(middleware.process_view(request, urls.serve_static_file, (), {}))
        self.assertEqual(middleware.process_view(request, serve, (), {}).status_code, 302)

    def test_anonymous_htmx_request_redirects_browser_to_login(self):
        """htmx must not put the login page into a page fragment."""
        sample = Sample.objects.get(name="14-JS-1")
        sample_url = sample.get_absolute_url()
        url = reverse("samples:process_details", kwargs={"process_id": 1, "sample_id": sample.pk})
        response = self.client.get(url, HTTP_HX_REQUEST="true", HTTP_HX_CURRENT_URL=f"http://testserver{sample_url}?a=1")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response["HX-Redirect"].startswith(settings.LOGIN_URL))
        self.assertTrue(response["HX-Redirect"].endswith("next=" + quote(f"{sample_url}?a=1", safe="/")))
        self.assertNotIn(b"<form", response.content)

    def test_anonymous_json_request_gets_401(self):
        """JSON clients log in via ``login_remote_client`` and cannot follow the
        redirect.
        """
        response = self.client.get(reverse("samples:main_menu"), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 401)

    def test_login_page_and_javascript_catalog_are_public(self):
        login_response = self.client.get(reverse("login"))
        self.assertEqual(login_response.status_code, 200)
        self.assertIn(b'name="password"', login_response.content)
        catalog_response = self.client.get(reverse("jb_common:jsi18n"))
        self.assertEqual(catalog_response.status_code, 200)
        self.assertIn(b"django.catalog", catalog_response.content)

    def test_remote_client_can_log_in_and_out(self):
        login_url = "/login_remote_client"
        self.assertEqual(self.client.get(login_url, HTTP_ACCEPT="application/json").status_code, 200)
        login_response = self.client.post(login_url, {"username": "r.calvert", "password": "12345"},
                                          HTTP_ACCEPT="application/json")
        self.assertEqual(login_response.status_code, 200)
        self.assertIs(login_response.json(), True)
        self.assertEqual(self.client.get(reverse("samples:main_menu")).status_code, 200)
        logout_response = self.client.get("/logout_remote_client", HTTP_ACCEPT="application/json")
        self.assertEqual(logout_response.status_code, 200)
        self.assertIs(logout_response.json(), True)
        self.assertEqual(self.client.get("/logout_remote_client", HTTP_ACCEPT="application/json").status_code, 200)

    def test_feed_is_public_with_user_hash(self):
        """Feed readers cannot log in; the secret hash in the URL authenticates
        them.
        """
        user = User.objects.get(username="r.calvert")
        response = self.client.get(reverse("samples:show_feed", kwargs={"username": user.username,
                                                                         "user_hash": permissions.get_user_hash(user)}))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<feed", response.content)
        wrong_hash_response = self.client.get(reverse("samples:show_feed", kwargs={"username": user.username,
                                                                                    "user_hash": "0" * 10}))
        self.assertNotEqual(wrong_hash_response.status_code, 200)
