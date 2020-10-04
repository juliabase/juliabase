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

from django.test import TestCase, override_settings
from remote_client.jb_remote.crawler_tools import Locked, PIDLock
from remote_client.jb_remote import settings
from .tools import log


@override_settings(ROOT_URLCONF="institute.tests.urls")
class LockingTest(TestCase):

    def test_locking(self):
        with PIDLock("test_program"):
            pass

    def test_double_locking(self):
        position = log.tell()
        with self.assertRaises(Locked):
            with PIDLock("test_program"), PIDLock("test_program", 0):
                pass
        log.seek(position)
        self.assertEqual(log.read().strip(),
                         f"WARNING:root:Lock {settings.CRAWLERS_DATA_DIR}/test_program.pid of other process active")
