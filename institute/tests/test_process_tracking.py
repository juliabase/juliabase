# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2026 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""Tests for the automatically maintained fields of processes which record who
created and who last modified a process, and when.
"""

import datetime
import django.utils.timezone
from django.contrib.auth.models import User
from django.test import override_settings
from django.test.client import Client
from samples import models
import institute.models as institute_models
from .tools import TestCase


@override_settings(ROOT_URLCONF="institute.tests.urls")
class ProcessTrackingTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.operator = User.objects.get(username="r.calvert")
        self.client = Client()
        assert self.client.login(username="r.calvert", password="12345")
        self.number = datetime.datetime.now().strftime("%yS-001")
        self.timestamp = django.utils.timezone.localtime(django.utils.timezone.now()).strftime("%Y-%m-%d %H:%M:%S")

    # last_modified_by_person: on_delete=SET_NULL

    def test_deleting_last_modifier_keeps_process(self):
        process = models.Process.objects.first()
        modifier = User.objects.create_user("modifier", password="12345")
        process.last_modified_by_person = modifier
        process.save()
        modifier.delete()
        process.refresh_from_db()
        self.assertIsNone(process.last_modified_by_person)

    # created and created_by_person

    def test_created_is_set_automatically(self):
        before = django.utils.timezone.now()
        deposition = institute_models.FiveChamberDeposition.objects.create(
            number=self.number, timestamp=before - datetime.timedelta(days=100), operator=self.operator)
        self.assertGreaterEqual(deposition.created, before)
        self.assertIsNone(deposition.created_by_person)

    def test_deleting_creator_keeps_process(self):
        creator = User.objects.create_user("creator", password="12345")
        deposition = institute_models.FiveChamberDeposition.objects.create(
            number=self.number, timestamp=django.utils.timezone.now(), operator=self.operator,
            created_by_person=creator)
        creator.delete()
        deposition.refresh_from_db()
        self.assertIsNone(deposition.created_by_person)

    # Tracking fields are not part of process forms

    def test_tracking_fields_are_not_in_process_form(self):
        response = self.client.get("/5-chamber_depositions/add/")
        self.assertEqual(response.status_code, 200)
        fields = response.context["process"].fields
        self.assertNotIn("created_by_person", fields)
        self.assertNotIn("last_modified_by_person", fields)
