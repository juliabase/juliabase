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



"""Tests for the fonts of the drawings, e.g. the stack diagrams.
"""

import os, shutil, tempfile
from unittest import skipUnless
from django.test import SimpleTestCase
from institute import reportlab_config


class FontsTest(SimpleTestCase):

    def test_helvetica_without_dejavu(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(reportlab_config.register_fonts(root), "Helvetica")

    @skipUnless(all(os.path.exists(os.path.join(reportlab_config.dejavu_root, filename))
                    for filename in reportlab_config.dejavu_fonts.values()), "DejaVu is not installed.")
    def test_helvetica_with_only_some_styles_of_dejavu(self):
        """Debian's “fonts-dejavu-core” lacks the oblique styles."""
        with tempfile.TemporaryDirectory() as root:
            for filename in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
                shutil.copy(os.path.join(reportlab_config.dejavu_root, filename), root)
            self.assertEqual(reportlab_config.register_fonts(root), "Helvetica")
            for filename in ("DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"):
                shutil.copy(os.path.join(reportlab_config.dejavu_root, filename), root)
            self.assertEqual(reportlab_config.register_fonts(root), "DejaVu")
