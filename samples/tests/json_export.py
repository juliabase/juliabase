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


class SampleExportTest(TestCase):
    fixtures = ["test_samples"]
    urls = "samples.tests.urls"

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="testuser", password="12345")

    def test_sample_export(self):
        response = self.client.get("/samples/by_id/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["Content-Type"], "application/json; charset=ascii")
        self.assertEqual(
            json.loads(response.content),
            {"currently responsible person": "testuser", "name": "10-TB-first", "tags": "", "topic": None, "purpose": "",
             "current location": "Torsten's office", "split origin": None, "ID": 1,
             "process #1": {"sample IDs": [1, 3], "apparatus": "setup1", "timestamp inaccuracy": 0,
                            "timestamp": "2010-12-02 11:07:36", "number": 1, "external operator": None, "finished": True,
                            "comments": "", "evaluated data file": "", "operator": "testuser",
                            "type": "test physical process", "raw data file": "test.dat"},
             "process #2": {"sample IDs": [1], "timestamp inaccuracy": 0, "timestamp": "2010-12-03 11:07:36",
                            "number": 1, "external operator": None, "finished": True, "comments": "", "operator": "testuser",
                            "type": "abstract measurement one"}
             })
