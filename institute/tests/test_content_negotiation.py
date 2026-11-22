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


"""Tests for the formats of the sample data sheet that the client can request
with the HTTP Accept header: HTML, JSON, RDF, and RO-Crate.
"""

import shutil
from unittest import skipUnless
from django.contrib.auth.models import User
from django.test import override_settings
from django.test.client import Client
from .tools import TestCase


SAMPLE_URL = "/samples/14-JS-1"
BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


@override_settings(ROOT_URLCONF="institute.tests.urls")
class ContentNegotiationTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.client = Client()
        self.client.force_login(User.objects.get(username="juliabase"))

    def assert_content_type(self, accept, content_type):
        response = self.client.get(SAMPLE_URL, HTTP_ACCEPT=accept)
        self.assertEqual(response.status_code, 200, accept)
        self.assertTrue(response["Content-Type"].startswith(content_type), (accept, response["Content-Type"]))
        return response

    def test_html_wins_if_everything_is_acceptable(self):
        """Clients like curl or Python's “requests” send “*/*”."""
        self.assert_content_type("*/*", "text/html")
        self.assert_content_type(BROWSER_ACCEPT, "text/html")

    def test_json(self):
        self.assert_content_type("application/json", "application/json")

    @override_settings(GRAPH_NAMESPACE_PREFIX=None)
    def test_no_rdf_without_graph_namespace(self):
        self.assert_content_type("text/turtle", "text/html")
        self.assert_content_type("application/vnd.eln+zip", "text/html")

    def test_rdf_with_graph_namespace(self):
        """settings_test sets GRAPH_NAMESPACE_PREFIX."""
        self.assert_content_type("*/*", "text/html")
        self.assert_content_type(BROWSER_ACCEPT, "text/html")
        self.assert_content_type("text/turtle", "text/turtle")

    @skipUnless(shutil.which("zip"), "The RO-Crate export needs the program “zip”.")
    def test_ro_crate_with_graph_namespace(self):
        self.assert_content_type("application/vnd.eln+zip", "application/vnd.eln+zip")
