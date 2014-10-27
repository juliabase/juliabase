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


substrate_data = {"sample IDs": [1, 2], "timestamp inaccuracy": 0, "timestamp": "2010-12-02 11:07:36",
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
        self.assertEqual(json.loads(response.content), substrate_data)

    def test_pds_measurement_export(self):
        response = self.client.get("/pds_measurements/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["Content-Type"], "application/json; charset=ascii")
        self.assertEqual(
            json.loads(response.content),
            {"sample IDs": [2], "apparatus": "pds1", "timestamp inaccuracy": 0, "timestamp": "2010-12-02 12:07:36",
             "external operator": None,
             "operator": "testuser", "finished": True, "comments": "",
             "PDS number": 1, "type": "PDS measurement", "raw data file": "T:/Daten/pds/p4600-/pd4636.dat"})


class AdminExportTest(TestCase):
    fixtures = ["test_jb_institute"]
    urls = "jb_institute.tests.urls"

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="juliabase", password="12345")

    def test_substrate_by_sample_export(self):
        response = self.client.get("/substrates_by_sample/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["Content-Type"], "application/json; charset=ascii")
        self.assertEqual(json.loads(response.content),
                         {"operator": "testuser", "timestamp": "2010-12-02 11:07:36", "material": "corning",
                          "timestamp inaccuracy": 0, "comments": "", "finished": True, "sample IDs": [1, 2],
                          "external operator": None, "type": "substrate", "ID": 1})
