#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


from __future__ import absolute_import, unicode_literals

import json
from django.test import TestCase
from django.test.client import Client
import samples.views.shared_utils


class JsonTestCase(TestCase):

    def remove_dynamic_fields(self, dictionary):
        for key, value in list(dictionary.items()):
            if key == "last_modified":
                del dictionary[key]
            elif isinstance(value, dict):
                self.remove_dynamic_fields(value)

    def assertJsonDictEqual(self, response, dictionary):
        data = json.loads(response.content.decode("ascii"))
        self.remove_dynamic_fields(data)
        self.assertEqual(data, dictionary)
        

substrate_data = {"samples": [1, 2], "timestamp_inaccuracy": 0, "timestamp": "2010-12-02T11:07:36",
                  "material": "corning", "external_operator": None, "finished": True, "comments": "",
                  "operator": "testuser", "content_type": "substrate", "id": 1}

class ExportTest(JsonTestCase):
    fixtures = ["test_inm"]
    urls = "inm.tests.urls"
    maxDiff = None

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="testuser", password="12345")

    def test_substrate_export(self):
        response = self.client.get("/processes/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertJsonDictEqual(response, substrate_data)

    def test_pds_measurement_export(self):
        response = self.client.get("/pds_measurements/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["content-type"], "application/json")
        self.assertJsonDictEqual(response,
            {"samples": [2], "apparatus": "pds1", "timestamp_inaccuracy": 0, "timestamp": "2010-12-02T12:07:36",
             "external_operator": None,
             "operator": "testuser", "finished": True, "comments": "", "id": 2,
             "number": 1, "content_type": "PDS measurement", "raw_datafile": "T:/Daten/pds/p4600-/pd4636.dat"})

    def test_sample_export(self):
        response = self.client.get("/samples/by_id/2", HTTP_ACCEPT="application/json")
        self.assertEqual(response["content-type"], "application/json")
        self.assertJsonDictEqual(response,
            {"currently_responsible_person": "testuser", "name": "10-TB-second", "tags": "", "topic": None, "purpose": "",
             "current_location": u"Torsten's office", "split_origin": None, "id": 2,
             "process #1": {"samples": [1, 2], "content_type": "substrate", "timestamp_inaccuracy": 0,
                            "timestamp": "2010-12-02T11:07:36", "external_operator": None, "operator": "testuser",
                            "finished": True, "comments": "", "material": "corning", "id": 1},
             "process #2": {"samples": [2], "content_type": "PDS measurement", "timestamp_inaccuracy": 0,
                            "timestamp": "2010-12-02T12:07:36", "external_operator": None, "operator": "testuser",
                            "finished": True, "comments": "", "apparatus": "pds1", "number": 1, "id": 2,
                            "raw_datafile": "T:/Daten/pds/p4600-/pd4636.dat"}
            })


class SharedUtilsTest(TestCase):

    def test_capitalize_first_letter(self):
        self.assertEqual(samples.views.shared_utils.capitalize_first_letter("hello World"), "Hello World")
        self.assertEqual(samples.views.shared_utils.capitalize_first_letter("ärgerlich"), "Ärgerlich")


class AdminExportTest(JsonTestCase):
    fixtures = ["test_inm"]
    urls = "inm.tests.urls"

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="juliabase", password="12345")

    def test_substrate_by_sample_export(self):
        response = self.client.get("/substrates_by_sample/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["content-type"], "application/json")
        self.assertJsonDictEqual(response,
                         {"operator": "testuser", "timestamp": "2010-12-02T11:07:36", "material": "corning",
                          "timestamp_inaccuracy": 0, "comments": "", "finished": True, "samples": [1, 2],
                          "external_operator": None, "content_type": "substrate", "id": 1})
