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

import django.test


class TestCase(django.test.TestCase):
    """Test case class with additional JuliaBase functionality.
    """

    def _remove_dynamic_fields(self, dictionary):
        for key, value in list(dictionary.items()):
            if key == "last_modified":
                del dictionary[key]
            elif isinstance(value, dict):
                self._remove_dynamic_fields(value)

    def assertJsonDictEqual(self, response, dictionary):
        data = response.json()
        self._remove_dynamic_fields(data)
        self.assertEqual(data, dictionary)
