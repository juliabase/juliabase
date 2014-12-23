#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
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


from __future__ import unicode_literals
import os.path
import reportlab.rl_config
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


dejavu_root = "/usr/share/fonts/truetype/dejavu"
if os.path.exists(os.path.join(dejavu_root, "DejaVuSans.ttf")):
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(dejavu_root, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuOb", os.path.join(dejavu_root, "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuBd", os.path.join(dejavu_root, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuBdOb", os.path.join(dejavu_root, "DejaVuSans-BoldOblique.ttf")))
    default_fontname = "DejaVu"
    pdfmetrics.registerFontFamily(default_fontname, normal="DejaVu", bold="DejaVuBd", italic="DejaVuOb",
                                  boldItalic="DejaVuBdOb")
    reportlab.rl_config.canvas_basefontname = default_fontname
