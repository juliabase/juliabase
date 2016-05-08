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

from django.test import TestCase, override_settings
from django.test.client import Client


@override_settings(ROOT_URLCONF="institute.tests.urls")
class DeletionTest(TestCase):
    fixtures = ["test_main"]#, "test_delete"]

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="r.calvert", password="12345")

    def test_delete_sample_too_old(self):
        response = self.client.post("/samples/14S-001/delete/")
        self.assertContains(response, "You are not allowed to delete the process “Corning glass substrate #1” "
                            "because it is older than one hour.", status_code=401)

    def test_delete_process_too_old(self):
        response = self.client.post("/processes/1/delete/")
        self.assertContains(response, "You are not allowed to delete the process “Corning glass substrate #1” "
                            "because it is older than one hour.", status_code=401)

    def test_delete_sample_not_viewable(self):
        response = self.client.post("/samples/14-JS-1/delete/")
        self.assertContains(response, "You are not allowed to view the sample since you are not in the sample&#39;s topic, "
                            "nor are you its currently responsible person (Juliette Silverton), nor can you view all "
                            "samples.", status_code=401)


@override_settings(ROOT_URLCONF="institute.tests.urls")
class DeletionFailureTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="s.renard", password="12345")

    def test_delete_sample_not_editable(self):
        response = self.client.post("/samples/14-JS-1/delete/")
        self.assertContains(response, "You are not allowed to edit the sample “14-JS-1” (including splitting, declaring "
                            "dead, and deleting) because you are not the currently responsible person for this sample.",
                            status_code=401)
