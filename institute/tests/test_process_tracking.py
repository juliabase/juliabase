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

    # The views set the tracking fields

    def post_deposition(self, client, url, **extra_data):
        data = {"number": self.number, "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
                "operator": str(self.operator.pk), "combined_operator": str(self.operator.pk),
                "sample_list": ["1", "3"],
                "0-number": "1", "0-chamber": "i1", "0-sih4": "2.000"}
        data.update(extra_data)
        response = client.post(url, data)
        self.assertEqual(response.status_code, 303, response.content.decode()[:3000])
        return institute_models.FiveChamberDeposition.objects.get(number=self.number)

    def test_add_sets_creator(self):
        deposition = self.post_deposition(self.client, "/5-chamber_depositions/add/")
        self.assertEqual(deposition.created_by_person, self.operator)
        self.assertIsNone(deposition.last_modified_by_person)
        self.assertIsNotNone(deposition.created)

    def test_forged_tracking_fields_are_ignored(self):
        other_user = User.objects.exclude(pk=self.operator.pk).first()
        deposition = self.post_deposition(self.client, "/5-chamber_depositions/add/",
                                          created_by_person=str(other_user.pk),
                                          last_modified_by_person=str(other_user.pk))
        self.assertEqual(deposition.created_by_person, self.operator)
        self.assertIsNone(deposition.last_modified_by_person)

    def test_edit_by_other_user_keeps_creator(self):
        deposition = self.post_deposition(self.client, "/5-chamber_depositions/add/")
        created = deposition.created
        editor = User.objects.create_superuser("editor", "editor@example.com", "12345")
        editor_client = Client()
        assert editor_client.login(username="editor", password="12345")
        deposition = self.post_deposition(editor_client, "/5-chamber_depositions/{}/edit/".format(self.number),
                                          created_by_person=str(editor.pk), description="tracking test")
        self.assertEqual(deposition.created_by_person, self.operator)
        self.assertEqual(deposition.created, created)
        self.assertEqual(deposition.last_modified_by_person, editor)
        self.assertGreaterEqual(deposition.last_modified, created)
