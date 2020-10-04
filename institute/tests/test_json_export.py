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


from django.test.client import Client
from django.test import override_settings
import jb_common.utils.base
from .tools import TestCase


@override_settings(ROOT_URLCONF="institute.tests.urls")
class ExportTest(TestCase):
    fixtures = ["test_main"]
    maxDiff = None

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="j.silverton", password="12345")

    def test_substrate_export(self):
        response = self.client.get("/processes/13", HTTP_ACCEPT="application/json")
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertJsonDictEqual(response,
            {"samples": [7], "timestamp_inaccuracy": 3, "timestamp": "2014-10-01T10:29:00Z", "material": "corning", "id": 13,
             "external_operator": None, "finished": True, "comments": "", "operator": "e.monroe",
             "content_type": "institute | substrate"})

    def test_pds_measurement_export(self):
        response = self.client.get("/pds_measurements/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["content-type"], "application/json")
        self.assertJsonDictEqual(response,
            {"samples": [7], "apparatus": "pds1", "timestamp_inaccuracy": 0, "timestamp": "2014-10-07T10:01:00Z",
             "external_operator": None, "id": 25,
             "operator": "n.burkhardt", "finished": True, "comments": "",
             "number": 1, "content_type": "institute | PDS measurement", "raw_datafile": "measurement-1.dat"})

    def test_sample_export(self):
        response = self.client.get("/samples/by_id/7", HTTP_ACCEPT="application/json")
        self.assertEqual(response["content-type"], "application/json")
        self.assertJsonDictEqual(response,
            {"split_origin": None, "name": "14-JS-1", "tags": "", "currently_responsible_person": "j.silverton",
             "topic": "Juliette's PhD thesis", "purpose": "",
             "current_location": "Juliette's office", "id": 7,
             "process #13": {"content_type": "institute | substrate", "timestamp": "2014-10-01T10:29:00Z",
                             "material": "corning", "timestamp_inaccuracy": 3, "comments": "", "finished": True,
                             "samples": [7], "external_operator": None,
                             "operator": "e.monroe", "id": 13},
             "process #14": {"external_operator": None, "content_type": "institute | cluster tool deposition",
                             "layer 1": {"base_pressure": 0.0, "h2": 1.0, "number": 1, "comments": "p-type layer",
                                         "content_type": "institute | cluster tool hot-wire layer", "time": "10:00",
                                         "sih4": 2.0, "wire_material": "rhenium", "id": 1},
                             "layer 2": {"plasma_start_with_shutter": False, "h2": 0.0, "number": 2, "comments":
                                         "i-type layer", "chamber": "#3", "deposition_power": None,
                                         "content_type": "institute | cluster tool PECVD layer", "time": "55:00",
                                         "sih4": 3.0, "id": 2},
                             "layer 3": {"base_pressure": 4.0, "h2": 4.0, "number": 3, "comments": "n-type layer",
                                         "content_type": "institute | cluster tool hot-wire layer", "time": "10:00",
                                         "sih4": 7.0, "wire_material": "rhenium", "id": 3},
                             "timestamp_inaccuracy": 0, "comments": "", "number": "14C-001", "finished": True, "carrier": "",
                             "samples": [7], "timestamp": "2014-10-01T10:30:00Z", "operator": "e.monroe", "split_done": False,
                             "id": 14},
             "process #25": {"external_operator": None, "content_type": "institute | PDS measurement", "apparatus": "pds1",
                             "timestamp": "2014-10-07T10:01:00Z", "timestamp_inaccuracy": 0, "comments": "", "number": 1,
                             "finished": True, "raw_datafile": "measurement-1.dat", "samples": [7],
                             "operator": "n.burkhardt", "id": 25}})


class SharedUtilsTest(TestCase):

    def test_capitalize_first_letter(self):
        self.assertEqual(jb_common.utils.base.capitalize_first_letter("hello World"), "Hello World")
        self.assertEqual(jb_common.utils.base.capitalize_first_letter("ärgerlich"), "Ärgerlich")


@override_settings(ROOT_URLCONF="institute.tests.urls")
class AdminExportTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="juliabase", password="12345")

    def test_substrate_by_sample_export(self):
        response = self.client.get("/substrates_by_sample/1", HTTP_ACCEPT="application/json")
        self.assertEqual(response["content-type"], "application/json")
        self.assertJsonDictEqual(response,
                         {"operator": "r.calvert", "timestamp": "2014-10-01T10:29:00Z", "material": "corning",
                          "timestamp_inaccuracy": 3, "comments": "", "finished": True, "samples": [1],
                          "external_operator": None, "content_type": "institute | substrate", "id": 1})
