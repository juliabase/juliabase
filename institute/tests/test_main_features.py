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

from django.test import TestCase
from django.test.client import Client


class MainFeaturesTest(TestCase):
    fixtures = ["test_main"]
    urls = "institute.tests.urls"

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="juliabase", password="12345")

    def test_main_menu(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_add_samples(self):
        response = self.client.get("/samples/add/")
        self.assertEqual(response.status_code, 200)

    def test_add_sample_series(self):
        response = self.client.get("/sample_series/add/")
        self.assertEqual(response.status_code, 200)

    def test_add_result(self):
        response = self.client.get("/results/add/")
        self.assertEqual(response.status_code, 200)

    def test_add_5_chamber_deposition(self):
        response = self.client.get("/5-chamber_depositions/add/")
        self.assertEqual(response.status_code, 200)

    def test_add_cluster_tool_deposition(self):
        response = self.client.get("/cluster_tool_depositions/add/")
        self.assertEqual(response.status_code, 200)

    def test_add_layer_thickness_measurement(self):
        response = self.client.get("/layer_thickness_measurements/add/")
        self.assertEqual(response.status_code, 200)

    def test_add_solarsimulator_measurement(self):
        response = self.client.get("/solarsimulator_measurements/add/")
        self.assertEqual(response.status_code, 200)

    def test_advanced_search(self):
        response = self.client.get("/advanced_search")
        self.assertEqual(response.status_code, 200)

    def test_search_by_sample_name(self):
        response = self.client.get("/samples/")
        self.assertEqual(response.status_code, 200)

    def test_search_by_deposition_number(self):
        response = self.client.get("/depositions/")
        self.assertEqual(response.status_code, 200)

    def test_5_chamber_lab_notebook(self):
        response = self.client.get("/5-chamber_depositions/lab_notebook/", follow=True)
        self.assertEqual(response.status_code, 200)

    def test_add_topic(self):
        response = self.client.get("/topics/add/")
        self.assertEqual(response.status_code, 303)

    def test_change_topic_members(self):
        response = self.client.get("/topics/")
        self.assertEqual(response.status_code, 200)

    def test_admin(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_rename_sample(self):
        response = self.client.get("/samples/rename/")
        self.assertEqual(response.status_code, 200)

    def test_change_preferences(self):
        response = self.client.get("/preferences/juliabase")
        self.assertEqual(response.status_code, 200)

    def test_topics_and_permissions(self):
        response = self.client.get("/topics_and_permissions/juliabase")
        self.assertEqual(response.status_code, 200)

    def test_permissions(self):
        response = self.client.get("/permissions/")
        self.assertEqual(response.status_code, 200)

    def test_tasks(self):
        response = self.client.get("/tasks/")
        self.assertEqual(response.status_code, 200)

    def test_change_password(self):
        response = self.client.get("/change_password")
        self.assertEqual(response.status_code, 200)

    def test_newsfeed(self):
        response = self.client.get("/feeds/juliabase+b45a8775d0")
        self.assertEqual(response.status_code, 200)

    def test_my_layers(self):
        response = self.client.get("/my_layers/juliabase")
        self.assertEqual(response.status_code, 200)

    def test_status(self):
        response = self.client.get("/status/")
        self.assertEqual(response.status_code, 200)

    def test_merge_samples(self):
        response = self.client.get("/merge_samples")
        self.assertEqual(response.status_code, 200)

    def test_sample_claims(self):
        response = self.client.get("/claims/juliabase/")
        self.assertEqual(response.status_code, 200)

    def test_crawler_logs(self):
        response = self.client.get("/crawler_logs/")
        self.assertEqual(response.status_code, 200)

    def test_about_page(self):
        response = self.client.get("/about")
        self.assertEqual(response.status_code, 200)

    def test_statistics(self):
        response = self.client.get("/statistics")
        self.assertEqual(response.status_code, 200)
