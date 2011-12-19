#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

from __future__ import unicode_literals

from django.test import TestCase
import samples.views.shared_utils


class SharedUtilsTest(TestCase):

    def test_capitalize_first_letter(self):
        self.assertEqual(samples.views.shared_utils.capitalize_first_letter("hello World"), "Hello World")
        self.assertEqual(samples.views.shared_utils.capitalize_first_letter("ärgerlich"), "Ärgerlich")
