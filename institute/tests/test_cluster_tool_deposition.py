# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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


import datetime, decimal
import django.utils.timezone
from django.test.client import Client
from django.test import override_settings
import jb_remote_inm
from .tools import TestCase, JuliaBaseConnection


@override_settings(ROOT_URLCONF="institute.tests.urls")
class ClusterToolDepositionTest(TestCase):
    fixtures = ["test_main", "monroe_samples"]

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="e.monroe", password="12345")
        self.deposition_number = django.utils.timezone.now().strftime("%yC-001")
        timestamp = django.utils.timezone.now()
        # See <https://code.djangoproject.com/ticket/11385>.
        self.timestamp = django.utils.timezone.localtime(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        self.timestamp_with_t = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_correct_data(self):
        response = self.client.post("/cluster_tool_depositions/add/",
            {"number": self.deposition_number, "combined_operator": "6",
             "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["13", "14"],
             "0-step_type": "clustertoolhotwirelayer", "0-number": "1", "0-wire_material": "rhenium",
             "1-step_type": "clustertoolpecvdlayer", "1-number": "2", "1-chamber": "#1"}, follow=True)
        self.assertRedirects(response, "/", 303)
        response = self.client.get("/cluster_tool_depositions/" + self.deposition_number, HTTP_ACCEPT="application/json")
        self.assertEqual(response["content-type"], "application/json")
        self.assertEqual(response.status_code, 200)
        self.maxDiff = None
        self.assertJsonDictEqual(response,
            {"id": 31, "number": self.deposition_number,
             "content_type": "institute | cluster tool deposition",
             "timestamp": self.timestamp_with_t, "timestamp_inaccuracy": 0,
             "operator": "e.monroe",
             "external_operator": None, "finished": True, "comments": "", "split_done": False, "carrier": "",
             "samples": [13, 14],
             "layer 1": {"h2": None, "id": 19, "number": 1, "sih4": None, "base_pressure": None,
                         "wire_material": "rhenium", "time": "", "comments": "",
                         "content_type": "institute | cluster tool hot-wire layer"},
             "layer 2": {"chamber": "#1", "h2": None, "id": 20, "number": 2, "sih4": None, "comments": "",
                         "content_type": "institute | cluster tool PECVD layer", "plasma_start_with_shutter": False,
                         "time": "", "deposition_power": None}})
        response = self.client.get("/my_samples/e.monroe", HTTP_ACCEPT="application/json")
        my_samples = response.json()
        self.assertIn(13, my_samples)
        self.assertIn(14, my_samples)

    def test_add_layer(self):
        response = self.client.post("/cluster_tool_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["13", "14"], "number": self.deposition_number, "step_to_be_added": "clustertoolhotwirelayer"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 1)
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["number"].value(), "1")
        # This checks whether the new step really is a hot-wire layer.
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["wire_material"].value(), None)

    def test_add_my_layer(self):
        response = self.client.post("/cluster_tool_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["13", "14"], "number": self.deposition_number, "my_step_to_be_added": "14-1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 1)
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["number"].value(), 1)
        # This checks whether the new layer really is the hot-wire layer.
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["wire_material"].value(), "rhenium")
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["h2"].value(), decimal.Decimal("1"))
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["sih4"].value(), decimal.Decimal("2"))
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["base_pressure"].value(), decimal.Decimal("0"))
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["time"].value(), "10:00")
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["comments"].value(), "p-type layer")

    def test_duplicate_layer(self):
        response = self.client.post("/cluster_tool_depositions/add/",
            {"combined_operator": "6", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["13", "14"], "number": self.deposition_number,
             "0-step_type": "clustertoolhotwirelayer", "0-number": "1", "0-sih4": "1", "0-wire_material": "rhenium",
             "1-chamber": "#1", "1-step_type": "clustertoolpecvdlayer", "1-number": "2", "1-sih4": "2",
             "1-duplicate_this_step": "on",
             "2-step_type": "clustertoolhotwirelayer", "2-number": "3", "2-sih4": "3", "2-wire_material": "rhenium",
             "step_to_be_added": "clustertoolpecvdlayer"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 5)
        for i in range(5):
            self.assertEqual(int(response.context["steps_and_change_steps"][i][0]["number"].value()), i + 1)
            self.assertFalse(response.context["steps_and_change_steps"][i][1]["duplicate_this_step"].value())
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["sih4"].value(), "1")
        self.assertEqual(response.context["steps_and_change_steps"][1][0]["sih4"].value(), "2")
        self.assertEqual(response.context["steps_and_change_steps"][2][0]["sih4"].value(), "3")
        self.assertEqual(response.context["steps_and_change_steps"][3][0]["sih4"].value(), decimal.Decimal("2"))
        self.assertEqual(response.context["steps_and_change_steps"][4][0]["sih4"].value(), None)

    def test_duplicate_deposition(self):
        response = self.client.get("/cluster_tool_depositions/add/?copy_from=14C-001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["samples"]["sample_list"].value(), [])
        self.assertEqual(len(response.context["steps_and_change_steps"]), 3)
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["sih4"].value(), decimal.Decimal("2"))
        self.assertEqual(response.context["steps_and_change_steps"][1][0]["sih4"].value(), decimal.Decimal("3"))
        self.assertEqual(response.context["steps_and_change_steps"][2][0]["sih4"].value(), decimal.Decimal("7"))
        self.assertLess(abs((response.context["process"]["timestamp"].value() - datetime.datetime.now()).total_seconds()), 2)
        self.assertEqual(response.context["process"]["operator"].value(), 6)
        self.assertEqual(response.context["process"]["combined_operator"].value(), 6)

    def test_remote_client(self):
        jb_remote_inm.connection = JuliaBaseConnection(self.client)
        jb_remote_inm.ClusterToolDeposition("14C-001")
