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


"""Tests for the processes of a lab notebook, which shows all processes of a
class between two days, both days included.
"""

import datetime
import django.utils.timezone
from django.contrib.auth.models import User
from django.test import override_settings
from institute.models import Substrate
from .tools import TestCase


@override_settings(TIME_ZONE="Europe/Berlin")
class LabNotebookRangeTest(TestCase):
    fixtures = ["test_main"]

    def create_substrate(self, *timestamp):
        timestamp = django.utils.timezone.make_aware(datetime.datetime(*timestamp))
        return Substrate.objects.create(operator=User.objects.get(username="juliabase"), timestamp=timestamp,
                                        material="custom")

    def test_both_days_are_included_and_nothing_after_them(self):
        before = self.create_substrate(2024, 5, 1, 23, 59)
        first = self.create_substrate(2024, 5, 2, 0, 0)
        last = self.create_substrate(2024, 5, 3, 23, 59)
        after = self.create_substrate(2024, 5, 4, 0, 0)
        processes = Substrate.get_lab_notebook_context_range("2024-05-02", "2024-05-03")["processes"]
        self.assertEqual({process.pk for process in processes}, {first.pk, last.pk})
        self.assertNotIn(before.pk, {process.pk for process in processes})
        self.assertNotIn(after.pk, {process.pk for process in processes})
