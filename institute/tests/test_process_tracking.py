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

import datetime, re
import django.forms
import django.utils.timezone
from django.contrib.auth.models import User, Permission
from django.template.loader import render_to_string
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

    # The process form records the tracking fields, also for views that are not
    # class-based

    def substrate_form(self, user, instance=None):
        from institute.views.samples.substrate import SubstrateForm
        form = SubstrateForm(user, {"timestamp": self.timestamp, "timestamp_inaccuracy": "0",
                                    "combined_operator": str(self.operator.pk), "material": "custom",
                                    "comments": "form test"}, instance=instance)
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def test_process_form_records_creator_and_last_modifier(self):
        substrate = self.substrate_form(self.operator).save()
        substrate.refresh_from_db()
        self.assertEqual(substrate.created_by_person, self.operator)
        self.assertIsNone(substrate.last_modified_by_person)
        editor = User.objects.create_user("form-editor", password="12345")
        self.substrate_form(editor, substrate).save()
        substrate.refresh_from_db()
        self.assertEqual(substrate.created_by_person, self.operator)
        self.assertEqual(substrate.last_modified_by_person, editor)

    def test_process_form_records_creator_without_commit(self):
        substrate = self.substrate_form(self.operator).save(commit=False)
        self.assertEqual(substrate.created_by_person, self.operator)
        substrate.save()
        substrate.refresh_from_db()
        self.assertEqual(substrate.created_by_person, self.operator)

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

    # Processes created outside of the generic process views

    def assert_successful(self, response):
        """Asserts that a POST request was successful, i.e. redirected.  Otherwise,
        the errors of all forms in the response are shown.
        """
        if response.status_code != 303:
            def form_errors(value):
                if isinstance(value, django.forms.BaseForm):
                    return [value.errors.as_data()] if value.errors else []
                if isinstance(value, (list, tuple)):
                    return [error for item in value for error in form_errors(item)]
                return []
            errors = {key: form_errors(response.context[key]) for key in response.context.keys()} \
                if response.context else {}
            self.fail("{}: {}".format(response.status_code, {key: value for key, value in errors.items() if value}))

    def create_editor_client(self):
        editor = User.objects.create_superuser("editor", "editor@example.com", "12345")
        editor_client = Client()
        assert editor_client.login(username="editor", password="12345")
        return editor, editor_client

    def test_sample_death_sets_creator(self):
        sample = models.Sample.objects.get(pk=2)
        self.assert_successful(self.client.post("/samples/{}/kill/".format(sample.name), {"reason": "lost"}))
        self.assertEqual(models.SampleDeath.objects.get(samples=sample).created_by_person, self.operator)

    def test_split_and_resplit_set_creator_and_last_modifier(self):
        sample = models.Sample.objects.get(pk=2)
        self.assert_successful(self.client.post("/samples/{}/split/".format(sample.name),
                                                {"0-new_name": sample.name + "a", "1-new_name": sample.name,
                                                 "finished": "on"}))
        split = models.SampleSplit.objects.get(parent=sample)
        self.assertEqual(split.created_by_person, self.operator)
        self.assertIsNone(split.last_modified_by_person)
        editor, editor_client = self.create_editor_client()
        self.assert_successful(editor_client.post("/resplit/{}".format(split.pk),
                                                  {"0-new_name": sample.name + "b", "1-new_name": sample.name,
                                                   "sample_completely_split": "on", "finished": "on"}))
        split.refresh_from_db()
        self.assertEqual(split.created_by_person, self.operator)
        self.assertEqual(split.last_modified_by_person, editor)
        self.assertEqual(models.SampleDeath.objects.get(samples=sample).created_by_person, editor)

    def test_split_after_deposition_sets_creator(self):
        self.post_deposition(self.client, "/5-chamber_depositions/add/")
        sample = models.Sample.objects.get(pk=1)
        self.assert_successful(self.client.post(
            "/depositions/split_and_rename_samples/" + self.number,
            {"0-sample": sample.name, "0-new_name": self.number + "-1", "0-number_of_pieces": "2",
             "0_0-new_name": self.number + "-1a", "0_1-new_name": self.number + "-1b",
             "1-sample": models.Sample.objects.get(pk=3).name, "1-new_name": self.number + "-2", "1-number_of_pieces": "1",
             "1_0-new_name": self.number + "-2"}))
        self.assertEqual(models.SampleSplit.objects.get(parent=sample).created_by_person, self.operator)
        self.assertEqual(models.SampleDeath.objects.get(samples=sample).created_by_person, self.operator)

    def post_result(self, client, url):
        self.assert_successful(client.post(url, {"title": "Tracking test", "comments": "tracking test",
                                                 "timestamp": self.timestamp, "timestamp_inaccuracy": "0",
                                                 "operator": str(self.operator.pk),
                                                 "combined_operator": str(self.operator.pk), "samples": ["1"],
                                                 "number_of_quantities": "0", "number_of_values": "0",
                                                 "previous-number_of_quantities": "0",
                                                 "previous-number_of_values": "0"}))

    def test_result_sets_creator_and_last_modifier(self):
        self.post_result(self.client, "/results/add/")
        result = models.Result.objects.get(title="Tracking test")
        self.assertEqual(result.created_by_person, self.operator)
        self.assertIsNone(result.last_modified_by_person)
        editor, editor_client = self.create_editor_client()
        self.post_result(editor_client, "/results/{}/edit/".format(result.pk))
        result.refresh_from_db()
        self.assertEqual(result.created_by_person, self.operator)
        self.assertEqual(result.last_modified_by_person, editor)

    def test_add_samples_sets_creator_of_substrate(self):
        self.assert_successful(self.client.post("/samples/add/", {"number_of_samples": "1", "substrate": "asahi-u",
                                                                  "timestamp": self.timestamp, "current_location": "lab",
                                                                  "rename": ""}))
        substrate = institute_models.Substrate.objects.latest("pk")
        self.assertEqual(substrate.created_by_person, self.operator)

    def test_claim_sets_creator_of_substrates(self):
        reviewer = User.objects.create_user("reviewer", password="12345")
        reviewer.user_permissions.add(Permission.objects.get(codename="adopt_samples"))
        self.assert_successful(self.client.post("/claims/r.calvert/add_oldstyle/",
                                                {"samples": "10Z-001", "material": "asahi-u",
                                                 "reviewer": str(reviewer.pk)}))
        claim = models.SampleClaim.objects.latest("pk")
        self.assertEqual([sample.name for sample in claim.samples.all()], ["10Z-001"])
        substrate = institute_models.Substrate.objects.get(samples__name="10Z-001")
        self.assertEqual(substrate.created_by_person, self.operator)


def plain_text(html):
    """Returns the text of an HTML snippet with normalised whitespace."""
    return " ".join(re.sub(r"<[^>]+>", " ", html).split()).replace(" ,", ",")


@override_settings(ROOT_URLCONF="institute.tests.urls")
class ProcessTrackingDisplayTest(TestCase):
    """The operator and timestamp of a process, and below, if known, who
    entered it into the database and who edited it last.
    """
    fixtures = ["test_main"]
    timestamp_pattern = r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d"

    def setUp(self):
        self.operator = User.objects.get(username="e.monroe")
        self.creator = User.objects.get(username="r.calvert")
        self.editor = User.objects.get(username="n.burkhardt")
        self.sample = models.Sample.objects.get(name="14-JS-1")
        self.substrate = institute_models.Substrate.objects.create(
            operator=self.operator, timestamp=django.utils.timezone.make_aware(datetime.datetime(2024, 5, 2, 10, 0)),
            material="custom", created_by_person=self.creator)
        self.substrate.samples.add(self.sample)

    def render(self, process, clearance=None):
        return plain_text(render_to_string("samples/operator_and_timestamp.html",
                                           {"process": process, "clearance": clearance}))

    def test_legacy_process_shows_only_operator(self):
        process = models.Process.objects.filter(created_by_person__isnull=True, last_modified_by_person__isnull=True,
                                                external_operator__isnull=True).first()
        text = self.render(process)
        self.assertTrue(text.startswith("Operator: "), text)
        self.assertNotIn("Created by:", text)
        self.assertNotIn("Edited by:", text)

    def test_creator_and_editor_are_shown_below_operator(self):
        self.assertRegex(self.render(self.substrate),
                         r"^Operator: Eddie Monroe, 2024-05-02 10:00:00 Created by: Rosalee Calvert, " +
                         self.timestamp_pattern + "$")
        self.substrate.last_modified_by_person = self.editor
        self.substrate.save()
        self.assertRegex(self.render(self.substrate),
                         r"^Operator: Eddie Monroe, 2024-05-02 10:00:00 Created by: Rosalee Calvert, " +
                         self.timestamp_pattern + " Edited by: Nick Burkhardt, " + self.timestamp_pattern + "$")

    def test_external_operator_is_shown_instead_of_operator(self):
        external_operator = models.ExternalOperator.objects.create(
            name="Ext Operator", institution="Elsewhere", email="ext@example.com", confidential=True)
        self.substrate.external_operator = external_operator
        self.substrate.save()
        self.assertIn("Operator: Ext Operator,", self.render(self.substrate))
        self.assertIn(f"Operator: Confidential operator #{external_operator.pk},",
                      self.render(self.substrate, clearance=True))

    def test_pages_show_creator(self):
        client = Client()
        client.force_login(User.objects.get(username="juliabase"))
        sample_page = plain_text(client.get(self.sample.get_absolute_url()).content.decode())
        self.assertIn("Operator: Eddie Monroe, 2024-05-02 10:00:00 Created by: Rosalee Calvert,", sample_page)
        process_page = plain_text(client.get(self.substrate.get_absolute_url()).content.decode())
        self.assertIn("Operator: Eddie Monroe, 2024-05-02 10:00:00 Created by: Rosalee Calvert,", process_page)
        result = models.Result.objects.create(operator=self.operator, title="Display test", created_by_person=self.creator,
                                              timestamp=django.utils.timezone.make_aware(datetime.datetime(2024, 5, 3, 9, 0)))
        result.samples.add(self.sample)
        result_page = plain_text(client.get(result.get_absolute_url()).content.decode())
        self.assertIn("Operator: Eddie Monroe, 2024-05-03 09:00:00 Created by: Rosalee Calvert,", result_page)
