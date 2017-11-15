#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
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

import tempfile, os
from django.test import TestCase, override_settings
from remote_client.jb_remote.crawler_tools import changed_files, find_changed_files, defer_files


@override_settings(ROOT_URLCONF="institute.tests.urls")
class FindChangedFilesTest(TestCase):

    def touch(self, path):
        """Inspired by <https://stackoverflow.com/a/1160227>.
        """
        with os.fdopen(os.open(os.path.join(self.tempdir.name, path), flags=os.O_CREAT | os.O_APPEND)) as f:
            os.utime(f.fileno())

    def relative(self, path):
        if not isinstance(path, str):
            result = [self.relative(single_path) for single_path in path]
            result_set = set(result)
            self.assertEqual(len(result), len(result_set))
            return result_set
        return os.path.relpath(path, self.tempdir.name)

    def find_changed_files(self, *args, **kwargs):
        changed, removed = find_changed_files(self.tempdir.name, self.diff_file, *args, **kwargs)
        return self.relative(changed), self.relative(removed)

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.diffdir = tempfile.TemporaryDirectory()
        self.diff_file = os.path.join(self.diffdir.name, "test.pickle")
        self.touch("1.dat")
        self.touch("a.dat")

    def test_basic(self):
        self.assertEqual(self.find_changed_files(), ({"1.dat", "a.dat"}, set()))
        self.assertEqual(self.find_changed_files(), (set(), set()))
        self.touch("2.dat")
        self.assertEqual(self.find_changed_files(), ({"2.dat"}, set()))

    def test_removed(self):
        self.assertEqual(self.find_changed_files(), ({"1.dat", "a.dat"}, set()))
        os.unlink(os.path.join(self.tempdir.name, "1.dat"))
        self.assertEqual(self.find_changed_files(), (set(), {"1.dat"}))

    def test_touched_only(self):
        self.assertEqual(self.find_changed_files(), ({"1.dat", "a.dat"}, set()))
        self.touch("1.dat")
        self.assertEqual(self.find_changed_files(), (set(), set()))

    def test_changed_content(self):
        self.assertEqual(self.find_changed_files(), ({"1.dat", "a.dat"}, set()))
        with open(os.path.join(self.tempdir.name, "1.dat"), "w") as outfile:
            outfile.write(".")
        self.assertEqual(self.find_changed_files(), ({"1.dat"}, set()))

    def test_pattern(self):
        self.assertEqual(self.find_changed_files(r"[a-z]\.dat"), ({"a.dat"}, set()))
        self.assertEqual(self.find_changed_files(r"[a-z]\.dat"), (set(), set()))
        self.assertEqual(self.find_changed_files(), ({"1.dat"}, set()))

    def test_defer_files(self):
        self.assertEqual(self.find_changed_files(), ({"1.dat", "a.dat"}, set()))
        defer_files(self.diff_file, ["1.dat"])
        self.assertEqual(self.find_changed_files(), ({"1.dat"}, set()))

    def tearDown(self):
        self.tempdir.cleanup()
        self.diffdir.cleanup()
