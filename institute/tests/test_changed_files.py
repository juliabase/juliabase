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
from remote_client.jb_remote.crawler_tools import changed_files, find_changed_files, defer_files, Path
from .tools import log


class Common:

    def touch(self, path, mtime=None):
        """Inspired by <https://stackoverflow.com/a/1160227>.
        """
        times = (mtime, mtime) if mtime is not None else None
        with os.fdopen(os.open(os.path.join(self.tempdir.name, path), flags=os.O_CREAT | os.O_APPEND)) as f:
            os.utime(f.fileno(), times)

    def relative(self, path):
        if not isinstance(path, (str, Path)):
            result = [self.relative(single_path) for single_path in path]
            result_set = set(result)
            self.assertEqual(len(result), len(result_set))
            return result_set
        return os.path.relpath(str(path), self.tempdir.name)

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

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.diffdir = tempfile.TemporaryDirectory()
        self.diff_file = os.path.join(self.diffdir.name, "test.pickle")
        self.touch("1.dat")
        self.touch("a.dat")

    def tearDown(self):
        self.tempdir.cleanup()
        self.diffdir.cleanup()


@override_settings(ROOT_URLCONF="institute.tests.urls")
class FindChangedFilesTest(Common, TestCase):

    def find_changed_files(self, *args, **kwargs):
        changed, removed = find_changed_files(self.tempdir.name, self.diff_file, *args, **kwargs)
        return self.relative(changed), self.relative(removed)

    def test_defer_files(self):
        self.assertEqual(self.find_changed_files(), ({"1.dat", "a.dat"}, set()))
        defer_files(self.diff_file, ["1.dat"])
        self.assertEqual(self.find_changed_files(), ({"1.dat"}, set()))

    def test_defer_too_old_file(self):
        self.touch("1.dat", 0)
        self.assertEqual(self.find_changed_files(), ({"1.dat", "a.dat"}, set()))
        defer_files(self.diff_file, ["1.dat"])
        self.assertEqual(self.find_changed_files(), (set(), set()))


@override_settings(ROOT_URLCONF="institute.tests.urls")
class ChangedFilesTest(Common, TestCase):

    def find_changed_files(self, *args, **kwargs):
        with changed_files(self.tempdir.name, self.diff_file, *args, **kwargs) as paths:
            changed_, removed_ = [], []
            for path in paths:
                if path.was_changed:
                    changed_.append(path)
                    path.check_off()
                elif path.was_removed:
                    removed_.append(path)
                    path.check_off()
        return self.relative(changed_), self.relative(removed_)

    def test_fail_during_iteration(self):
        position = log.tell()
        with changed_files(self.tempdir.name, self.diff_file) as paths:
            for path in paths:
                self.assertTrue(path.was_changed)
                failed_path = self.relative(path)
                path.check_off()
                raise Exception("Bad")
        log.seek(position)
        self.assertEqual(log.read().strip(), 'CRITICAL:root:Crawler error at "{}" (aborting): Bad'.format(failed_path))
        self.assertEqual(self.find_changed_files(), ({"1.dat", "a.dat"} - {failed_path}, set()))

    def test_dont_call_check_off(self):
        with changed_files(self.tempdir.name, self.diff_file) as paths:
            for path in paths:
                self.assertTrue(path.was_changed)
                if os.path.basename(str(path)) != "1.dat":
                    path.check_off()
        self.assertEqual(self.find_changed_files(), ({"1.dat"}, set()))

    def test_call_check_off_twice(self):
        with changed_files(self.tempdir.name, self.diff_file) as paths:
            for path in paths:
                self.assertTrue(path.was_changed)
                path.check_off()
                path.check_off()
        self.assertEqual(self.find_changed_files(), (set(), set()))

    def test_new_and_modified(self):
        with changed_files(self.tempdir.name, self.diff_file) as paths:
            for path in paths:
                self.assertTrue(path.was_changed)
                self.assertTrue(path.was_created)
                self.assertFalse(path.was_modified)
        with open(os.path.join(self.tempdir.name, "1.dat"), "w") as outfile:
            outfile.write(".")
        with changed_files(self.tempdir.name, self.diff_file) as paths:
            for path in paths:
                self.assertTrue(path.was_changed)
                self.assertTrue(path.was_created)
                self.assertFalse(path.was_modified)

    def test_too_old_file(self):
        self.touch("1.dat", 0)
        with changed_files(self.tempdir.name, self.diff_file) as paths:
            for path in paths:
                self.assertTrue(path.was_changed)
                if os.path.basename(str(path)) != "1.dat":
                    path.check_off()
        self.assertEqual(self.find_changed_files(), (set(), set()))
