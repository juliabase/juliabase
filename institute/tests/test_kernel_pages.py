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


"""Tests for pages of the “samples” app whose templates link to views that
only some institutes have, e.g. Chantal's “iek5”.  Without such an institute
app, the links are left out instead of the page crashing.
"""

import django.utils.timezone
from django.contrib.auth.models import User
from django.test import override_settings
from django.test.client import Client
from jb_common.models import Topic
from samples.models import Sample, SampleSeries
from institute.models import Substrate
from .tools import TestCase


@override_settings(ROOT_URLCONF="institute.tests.urls")
class KernelPagesTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.user = User.objects.get(username="juliabase")
        self.client = Client()
        self.client.force_login(self.user)

    def test_sample_series_page(self):
        sample_series = SampleSeries.objects.create(
            name="22-JB-series", currently_responsible_person=self.user, timestamp=django.utils.timezone.now(),
            topic=Topic.objects.first(), description="series description")
        sample_series.samples.add(Sample.objects.get(name="14-JS-1"))
        response = self.client.get(sample_series.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"runsheet icon", response.content)

    def test_process_with_several_samples(self):
        substrate = Substrate.objects.create(operator=self.user, timestamp=django.utils.timezone.now(), material="custom")
        samples = Sample.objects.filter(name__in=["14-JS-1", "14-JS-2"])
        substrate.samples.add(*samples)
        response = self.client.get(substrate.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for sample in samples:
            self.assertIn(f'<a href="{sample.get_absolute_url()}">{sample}</a>', content)
        self.assertNotIn('name="selected_samples"', content)
