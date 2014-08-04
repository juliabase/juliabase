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
