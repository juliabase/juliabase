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
from .tools import TestCase


@override_settings(ROOT_URLCONF="institute.tests.urls")
class FiveChamberDepositionTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="r.calvert", password="12345")
        self.deposition_number = datetime.datetime.now().strftime("%yS-001")
        timestamp = django.utils.timezone.now()
        # See <https://code.djangoproject.com/ticket/11385>.
        self.timestamp = django.utils.timezone.localtime(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        self.timestamp_with_t = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_retrieve_add_view(self):
        response = self.client.get("/5-chamber_depositions/add/")
        self.assertEqual(response.status_code, 200)
        process_form = response.context["process"]
        self.assertEqual(process_form["operator"].value(), 7)
        self.assertEqual(process_form["combined_operator"].value(), 7)
        self.assertEqual(process_form["number"].value(), self.deposition_number)
        self.assertLess(abs((process_form["timestamp"].value() - datetime.datetime.now()).total_seconds()), 2)
        self.assertEqual(response.context["samples"]["sample_list"].value(), [])
        self.assertEqual(response.context["samples"].fields["sample_list"].choices,
                         [("Cooperation with Paris University",
                           [(1, "14S-001"), (2, "14S-002"), (3, "14S-003"), (4, "14S-004"), (5, "14S-005"), (6, "14S-006")])])

    def test_missing_fields_and_no_layers(self):
        response = self.client.post("/5-chamber_depositions/add/", {"number": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "process", "timestamp", "This field is required.")
        self.assertFormError(response, "process", "timestamp_inaccuracy", "This field is required.")
        self.assertFormError(response, "process", "combined_operator", "This field is required.")
        self.assertFormError(response, "process", "number", "This field is required.")
        self.assertFormError(response, "samples", "sample_list", "This field is required.")
        self.assertFormError(response, "process", None, "No layers given.")

    def test_correct_data(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"number": self.deposition_number, "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "combined_operator": "7", "sample_list": ["1", "3"],
             "0-number": "1", "1-chamber": "i2", "0-sih4": "3.000",
             "1-number": "2", "0-chamber": "i1", "1-sih4": "2.000"}, follow=True)
        self.assertRedirects(response, "/", 303)
        response = self.client.get("/5-chamber_depositions/" + self.deposition_number, HTTP_ACCEPT="application/json")
        self.assertEqual(response["content-type"], "application/json")
        self.assertEqual(response.status_code, 200)
        self.assertJsonDictEqual(response,
            {"id": 31, "number": self.deposition_number,
             "content_type": "institute | 5-chamber deposition",
             "timestamp": self.timestamp_with_t, "timestamp_inaccuracy": 0,
             "operator": "r.calvert",
             "external_operator": None, "finished": True, "comments": "", "split_done": False,
             "samples": [1, 3],
             "layer 1": {"chamber": "i1", "h2": None, "id": 19, "layer_type": "", "number": 1, "sih4": 3.0, "temperature_1": None,
                         "temperature_2": None},
             "layer 2": {"chamber": "i2", "h2": None, "id": 20, "layer_type": "", "number": 2, "sih4": 2.0, "temperature_1": None,
                         "temperature_2": None}})
        response = self.client.get("/my_samples/r.calvert", HTTP_ACCEPT="application/json")
        my_samples = response.json()
        self.assertIn(1, my_samples)
        self.assertIn(3, my_samples)

    def test_removal_from_my_samples(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"number": self.deposition_number, "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "combined_operator": "7", "sample_list": ["1", "3"],
             "1-number": "2", "0-chamber": "i1", "1-sih4": "2.000",
             "0-number": "1", "1-chamber": "i2", "0-sih4": "3.000",
             "remove_from_my_samples": "on"})
        response = self.client.get("/my_samples/r.calvert", HTTP_ACCEPT="application/json")
        my_samples = response.json()
        self.assertNotIn(1, my_samples)
        self.assertNotIn(3, my_samples)

    def test_samples_list(self):
        # Here, I check whether the selection of samples survive a failed POST.
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": self.deposition_number})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["samples"]["sample_list"].value(), ["1", "3"])

    def test_add_layer(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": self.deposition_number, "number_of_steps_to_add": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 1)
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["number"].value(), 1)

    def test_too_many_added_layers(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": self.deposition_number, "number_of_steps_to_add": "11"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "add_steps", "number_of_steps_to_add",
                             "Ensure this value is less than or equal to 10.")
        self.assertEqual(len(response.context["steps_and_change_steps"]), 0)

    def test_move_layer_up(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": self.deposition_number,
             "0-chamber": "i1", "0-number": "1", "0-sih4": "1",
             "1-chamber": "i2", "1-number": "2", "1-sih4": "2", "1-move_this_step": "up",
             "2-chamber": "i3", "2-number": "3", "2-sih4": "3"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 3)
        for i in range(3):
            self.assertEqual(response.context["steps_and_change_steps"][i][0]["number"].value(), i + 1)
            self.assertIsNone(response.context["steps_and_change_steps"][i][1]["move_this_step"].value())
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["sih4"].value(), "2")
        self.assertEqual(response.context["steps_and_change_steps"][1][0]["sih4"].value(), "1")
        self.assertEqual(response.context["steps_and_change_steps"][2][0]["sih4"].value(), "3")

        # Moving the first up must be a no-op
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": self.deposition_number,
             "0-chamber": "i1", "0-number": "1", "0-sih4": "1", "0-move_this_step": "up",
             "1-chamber": "i2", "1-number": "2", "1-sih4": "2",
             "2-chamber": "i3", "2-number": "3", "2-sih4": "3"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 3)
        for i in range(3):
            self.assertEqual(response.context["steps_and_change_steps"][i][0]["number"].value(), i + 1)
            self.assertIsNone(response.context["steps_and_change_steps"][i][1]["move_this_step"].value())
            self.assertEqual(response.context["steps_and_change_steps"][i][0]["sih4"].value(), str(i + 1))

    def test_move_layer_down(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": self.deposition_number,
             "0-chamber": "i1", "0-number": "1", "0-sih4": "1",
             "1-chamber": "i2", "1-number": "2", "1-sih4": "2", "1-move_this_step": "down",
             "2-chamber": "i3", "2-number": "3", "2-sih4": "3"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 3)
        for i in range(3):
            self.assertEqual(response.context["steps_and_change_steps"][i][0]["number"].value(), i + 1)
            self.assertIsNone(response.context["steps_and_change_steps"][i][1]["move_this_step"].value())
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["sih4"].value(), "1")
        self.assertEqual(response.context["steps_and_change_steps"][1][0]["sih4"].value(), "3")
        self.assertEqual(response.context["steps_and_change_steps"][2][0]["sih4"].value(), "2")

        # Moving the last down must be a no-op
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": self.deposition_number,
             "0-chamber": "i1", "0-number": "1", "0-sih4": "1",
             "1-chamber": "i2", "1-number": "2", "1-sih4": "2",
             "2-chamber": "i3", "2-number": "3", "2-sih4": "3", "2-move_this_step": "down"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 3)
        for i in range(3):
            self.assertEqual(response.context["steps_and_change_steps"][i][0]["number"].value(), i + 1)
            self.assertIsNone(response.context["steps_and_change_steps"][i][1]["move_this_step"].value())
            self.assertEqual(response.context["steps_and_change_steps"][i][0]["sih4"].value(), str(i + 1))

    def test_duplicate_layer(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": self.deposition_number,
             "0-chamber": "i1", "0-number": "1", "0-sih4": "1",
             "1-chamber": "i2", "1-number": "2", "1-sih4": "2", "1-duplicate_this_step": "on",
             "2-chamber": "i3", "2-number": "3", "2-sih4": "3"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 4)
        for i in range(4):
            self.assertEqual(response.context["steps_and_change_steps"][i][0]["number"].value(), i + 1)
            self.assertFalse(response.context["steps_and_change_steps"][i][1]["duplicate_this_step"].value())
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["sih4"].value(), "1")
        self.assertEqual(response.context["steps_and_change_steps"][1][0]["sih4"].value(), "2")
        self.assertEqual(response.context["steps_and_change_steps"][2][0]["sih4"].value(), "3")
        self.assertEqual(response.context["steps_and_change_steps"][3][0]["sih4"].value(), decimal.Decimal("2"))

    def test_remove_layer(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": self.deposition_number,
             "0-chamber": "i1", "0-number": "1", "0-sih4": "1",
             "1-chamber": "i2", "1-number": "2", "1-sih4": "2", "1-remove_this_step": "on",
             "2-chamber": "i3", "2-number": "3", "2-sih4": "3"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["steps_and_change_steps"]), 2)
        for i in range(2):
            self.assertEqual(response.context["steps_and_change_steps"][i][0]["number"].value(), i + 1)
            self.assertFalse(response.context["steps_and_change_steps"][i][1]["remove_this_step"].value())
        self.assertEqual(response.context["steps_and_change_steps"][0][0]["sih4"].value(), "1")
        self.assertEqual(response.context["steps_and_change_steps"][1][0]["sih4"].value(), "3")
