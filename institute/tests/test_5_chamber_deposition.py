#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
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


from __future__ import absolute_import, unicode_literals

import datetime
from django.test import TestCase
from django.test.client import Client
from .tools import TestCase


class FiveChamberDepositionTest(TestCase):
    fixtures = ["test_main"]
    urls = "institute.tests.urls"

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="r.calvert", password="12345")
        self.deposition_number = datetime.datetime.now().strftime("%yS-001")
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def test_retrieve_add_view(self):
        response = self.client.get("/5-chamber_depositions/add/")
        self.assertEqual(response.status_code, 200)
        process_form = response.context["process"]
        self.assertEqual(process_form["operator"].value(), 7)
        self.assertEqual(process_form["combined_operator"].value(), 7)
        self.assertEqual(process_form["number"].value(), self.deposition_number)
        self.assertLess(abs((process_form["timestamp"].value() - datetime.datetime.now()).total_seconds()), 1)
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
             "1-number": "2", "0-chamber": "i1", "1-sih4": "2.000",
             "0-number": "1", "1-chamber": "i2", "0-sih4": "3.000"}, follow=True)
        self.assertRedirects(response, "http://testserver/", 303)
        response = self.client.get("/5-chamber_depositions/" + self.deposition_number)
        self.assertEqual(response.status_code, 200)

    def test_samples_list(self):
        # Here, I check whether the selection of samples survive a failed POST.
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": "2015-06-18 13:53:38", "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": "15S-001"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["samples"]["sample_list"].value(), ["1", "3"])

    def test_add_layer(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": "15S-001", "number_of_layers_to_add": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["layers_and_change_layers"]), 1)
        self.assertEqual(response.context["layers_and_change_layers"][0][0]["number"].value(), 1)

    def test_too_many_added_layers(self):
        response = self.client.post("/5-chamber_depositions/add/",
            {"combined_operator": "7", "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
             "sample_list": ["1", "3"], "number": "15S-001", "number_of_layers_to_add": "11"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "add_layers", "number_of_layers_to_add",
                             "Ensure this value is less than or equal to 10.")
        self.assertEqual(len(response.context["layers_and_change_layers"]), 0)
