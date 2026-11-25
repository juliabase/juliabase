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


"""Tests for the sample data sheet and its separately loaded process bodies
(``samples:process_details``).

The rule under test: a user may load a process body exactly if this process is
shown to them on the data sheet of the given sample.
"""

import datetime, re
import django.utils.timezone
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.test.client import Client
from django.urls import reverse
from jb_common.models import Department, Topic
from samples.models import Clearance, Sample, SampleSplit
from institute.models import Substrate
from .tools import TestCase


START = django.utils.timezone.make_aware(datetime.datetime(2024, 1, 1, 12, 0))


def details_url(process, sample):
    return reverse("samples:process_details", kwargs={"process_id": process.pk, "sample_id": sample.pk})


def sample_url(sample):
    return reverse("samples:show_sample_by_name", kwargs={"sample_name": sample.name})


def create_user(username):
    user = User.objects.create_user(username, password="12345")
    user.jb_user_details.department = Department.objects.get(pk=1)
    user.jb_user_details.save()
    return user


def create_substrate(sample, operator, hours, comments=""):
    substrate = Substrate.objects.create(operator=operator, timestamp=START + datetime.timedelta(hours=hours),
                                         material="custom", comments=comments)
    substrate.samples.add(sample)
    return substrate


def split(parent, operator, hours, piece_names):
    sample_split = SampleSplit.objects.create(operator=operator, timestamp=START + datetime.timedelta(hours=hours),
                                              parent=parent)
    sample_split.samples.add(parent)
    pieces = [Sample.objects.create(name=name, current_location=parent.current_location,
                                    currently_responsible_person=parent.currently_responsible_person,
                                    topic=parent.topic, split_origin=sample_split)
              for name in piece_names]
    return sample_split, pieces


def visible_process_ids(response):
    return [entry.process.id for entry in response.context["samples_and_processes"].processes]


def process_element(content, process, sample):
    """Returns the opening tag of the ``<details>`` element of a process on a
    sample data sheet.
    """
    match = re.search(r'<details class="process"[^>]*' + re.escape(details_url(process, sample)) + r'[^>]*>', content)
    assert match, "process not found on the data sheet"
    return match.group(0)


@override_settings(ROOT_URLCONF="institute.tests.urls")
class ProcessDetailsTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.owner = create_user("sample-page-owner")
        self.outsider = create_user("sample-page-outsider")
        topic = Topic(name="Confidential sample-page topic", department=Department.objects.get(pk=1),
                      manager=self.owner, confidential=True)
        topic.save()
        topic.members.add(self.owner)
        self.sample = Sample.objects.create(name="sample-page-sample", current_location="lab",
                                            currently_responsible_person=self.owner, topic=topic)
        self.substrate = create_substrate(self.sample, self.owner, 0, comments="secret substrate comment")
        self.other_sample = Sample.objects.create(name="sample-page-other-sample", current_location="lab",
                                                  currently_responsible_person=self.owner, topic=topic)
        self.other_substrate = create_substrate(self.other_sample, self.owner, 1, comments="other substrate comment")
        self.client = Client()

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(details_url(self.substrate, self.sample))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])
        self.assertNotIn(b"secret substrate comment", response.content)

    def test_user_without_sample_permission_is_denied(self):
        self.client.force_login(self.outsider)
        response = self.client.get(details_url(self.substrate, self.sample))
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(b"secret substrate comment", response.content)

    def test_process_of_another_sample_is_not_found(self):
        """A visible sample does not unlock processes that are not shown on its
        data sheet.
        """
        self.client.force_login(self.owner)
        response = self.client.get(details_url(self.other_substrate, self.sample))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"other substrate comment", response.content)

    def test_process_body_is_returned(self):
        self.client.force_login(self.owner)
        response = self.client.get(details_url(self.substrate, self.sample))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-cache", response["Cache-Control"])
        content = response.content.decode()
        self.assertIn("secret substrate comment", content)
        self.assertNotIn("<html", content)
        # The edit icons replace the placeholder icons in the process heading.
        self.assertIn(f'id="process-icons-{self.substrate.pk}" hx-swap-oob="true"', content)

    def test_sample_page_lists_process_headings(self):
        """The data sheet lists the process headings, but not the separately
        loaded bodies.
        """
        self.client.force_login(self.owner)
        response = self.client.get(sample_url(self.sample))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('<span class="process-name">Substrate</span>', content)
        self.assertNotIn("(not finished)", content)
        self.assertNotIn("secret substrate comment", content)
        self.assertNotIn(details_url(self.other_substrate, self.sample), content)
        element = process_element(content, self.substrate, self.sample)
        self.assertIn(" open", element)
        self.assertIn('hx-trigger="load"', element)

    def test_folded_process_is_loaded_on_first_expansion(self):
        self.owner.samples_user_details.default_folded_process_classes.add(ContentType.objects.get_for_model(Substrate))
        self.client.force_login(self.owner)
        content = self.client.get(sample_url(self.sample)).content.decode()
        element = process_element(content, self.substrate, self.sample)
        self.assertNotIn(" open", element)
        self.assertIn('hx-trigger="toggle once"', element)

    def test_clearance_user_sees_only_cleared_processes(self):
        cleared_substrate = create_substrate(self.sample, self.owner, 2, comments="cleared")
        clearance = Clearance.objects.create(user=self.outsider, sample=self.sample)
        clearance.processes.add(cleared_substrate)
        self.client.force_login(self.outsider)

        page_response = self.client.get(sample_url(self.sample))
        self.assertEqual(page_response.status_code, 200)
        self.assertEqual(visible_process_ids(page_response), [cleared_substrate.id])
        page_content = page_response.content.decode()
        self.assertIn(details_url(cleared_substrate, self.sample), page_content)
        self.assertNotIn(details_url(self.substrate, self.sample), page_content)

        cleared_response = self.client.get(details_url(cleared_substrate, self.sample))
        self.assertEqual(cleared_response.status_code, 200)
        self.assertIn(b"cleared", cleared_response.content)

        hidden_response = self.client.get(details_url(self.substrate, self.sample))
        self.assertEqual(hidden_response.status_code, 404)
        self.assertNotIn(b"secret substrate comment", hidden_response.content)


@override_settings(ROOT_URLCONF="institute.tests.urls")
class SampleSplitContextTest(TestCase):
    """A grandparent is split into a parent and its sibling, the parent is split
    into a child.  A split is worded differently depending on the data sheet it
    is shown on.
    """
    fixtures = ["test_main"]

    def setUp(self):
        owner = create_user("split-owner")
        self.grandparent = Sample.objects.create(name="split-grandparent", current_location="lab",
                                                 currently_responsible_person=owner)
        create_substrate(self.grandparent, owner, 0)
        self.grandparent_split, (self.parent, self.sibling) = split(self.grandparent, owner, 1,
                                                                    ["split-parent", "split-sibling"])
        self.late_grandparent_substrate = create_substrate(self.grandparent, owner, 2, comments="after the split")
        self.parent_split, (self.child,) = split(self.parent, owner, 3, ["split-child"])
        self.client = Client()
        self.client.force_login(owner)

    def get_body(self, process, sample):
        response = self.client.get(details_url(process, sample))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_split_on_page_of_split_sample(self):
        body = self.get_body(self.grandparent_split, self.grandparent)
        self.assertIn("The sample was split into the following pieces:", body)
        self.assertNotIn("The parental sample", body)

    def test_split_of_parent_on_page_of_piece(self):
        body = self.get_body(self.grandparent_split, self.parent)
        self.assertIn("The parental sample", body)
        self.assertIn(self.grandparent.name, body)
        self.assertIn("(this one)", body)
        self.assertNotIn("(the ancestor of this one)", body)

    def test_split_of_grandparent_on_page_of_grandchild(self):
        body = self.get_body(self.grandparent_split, self.child)
        self.assertIn("The parental sample", body)
        self.assertIn(self.grandparent.name, body)
        self.assertIn("(the ancestor of this one)", body)
        self.assertNotIn("(this one)", body.replace("(the ancestor of this one)", ""))
        body = self.get_body(self.parent_split, self.child)
        self.assertIn(self.parent.name, body)
        self.assertIn("(this one)", body)

    def test_ancestor_process_after_split_is_not_shown_on_piece(self):
        response = self.client.get(details_url(self.late_grandparent_substrate, self.parent))
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"after the split", self.get_body(self.late_grandparent_substrate, self.grandparent).encode())
