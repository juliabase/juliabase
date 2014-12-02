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


substrate_data = {"sample IDs": [1, 2], "timestamp inaccuracy": 0, "timestamp": "2010-12-02T11:07:36",
                  "material": "corning", "external operator": None, "finished": True, "comments": "",
                  "operator": "testuser", "type": "substrate", "ID": 1}

class ExportTest(TestCase):
    fixtures = ["test_jb_institute"]
    urls = "jb_institute.tests.urls"

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="testuser", password="12345")

    def test_substrate_export(self):
        response = self.client.get("/processes/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["Content-Type"], "application/json; charset=ascii")
        self.assertEqual(json.loads(response.content.decode("ascii")), substrate_data)

    def test_pds_measurement_export(self):
        response = self.client.get("/pds_measurements/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["Content-Type"], "application/json; charset=ascii")
        self.assertEqual(
            json.loads(response.content.decode("ascii")),
            {"sample IDs": [2], "apparatus": "pds1", "timestamp inaccuracy": 0, "timestamp": "2010-12-02T12:07:36",
             "external operator": None,
             "operator": "testuser", "finished": True, "comments": "",
             "PDS number": 1, "type": "PDS measurement", "raw data file": "T:/Daten/pds/p4600-/pd4636.dat"})

    def test_sample_export(self):
        response = self.client.get("/samples/by_id/2", HTTP_ACCEPT="application/json")
        self.assertEqual(response["Content-Type"], "application/json; charset=ascii")
        self.assertEqual(
            json.loads(response.content.decode("ascii")),
            {"currently responsible person": "testuser", "name": "10-TB-second", "tags": "", "topic": None, "purpose": "",
             "current location": u"Torsten's office", "split origin": None, "ID": 2,
             "process #1": {"sample IDs": [1, 2], "type": "substrate", "timestamp inaccuracy": 0,
                            "timestamp": "2010-12-02T11:07:36", "external operator": None, "operator": "testuser", "finished": True,
                            "comments": "",
                            "material": "corning", "ID": 1},
             "process #2": {"sample IDs": [2], "type": "PDS measurement", "timestamp inaccuracy": 0,
                            "timestamp": "2010-12-02T12:07:36", "external operator": None, "operator": "testuser", "finished": True,
                            "comments": "",
                            "apparatus": "pds1", "PDS number": 1, "raw data file": "T:/Daten/pds/p4600-/pd4636.dat"}
            })


class SharedUtilsTest(TestCase):

    def test_capitalize_first_letter(self):
        self.assertEqual(samples.views.shared_utils.capitalize_first_letter("hello World"), "Hello World")
        self.assertEqual(samples.views.shared_utils.capitalize_first_letter("ärgerlich"), "Ärgerlich")


class AdminExportTest(TestCase):
    fixtures = ["test_jb_institute"]
    urls = "jb_institute.tests.urls"

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="juliabase", password="12345")

    def test_substrate_by_sample_export(self):
        response = self.client.get("/substrates_by_sample/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["Content-Type"], "application/json; charset=ascii")
        self.assertEqual(json.loads(response.content.decode("ascii")),
                         {"operator": "testuser", "timestamp": "2010-12-02T11:07:36", "material": "corning",
                          "timestamp inaccuracy": 0, "comments": "", "finished": True, "sample IDs": [1, 2],
                          "external operator": None, "type": "substrate", "ID": 1})
