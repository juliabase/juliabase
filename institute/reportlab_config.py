# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2022 Forschungszentrum Jülich GmbH, Jülich, Germany
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


import os.path
import reportlab.rl_config
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


dejavu_root = "/usr/share/fonts/truetype/dejavu"
dejavu_fonts = {"DejaVu": "DejaVuSans.ttf", "DejaVuOb": "DejaVuSans-Oblique.ttf", "DejaVuBd": "DejaVuSans-Bold.ttf",
                "DejaVuBdOb": "DejaVuSans-BoldOblique.ttf"}


def register_fonts(root=dejavu_root):
    """Registers DejaVu Sans with ReportLab if all four of its styles are
    installed.  On Debian, only “fonts-dejavu-core” and “fonts-dejavu-extra”
    together provide them.  Otherwise, Helvetica is used.

    :param root: the directory of the DejaVu TrueType fonts

    :type root: str

    :returns:
      the name of the font to be used for text in drawings

    :rtype: str
    """
    paths = {name: os.path.join(root, filename) for name, filename in dejavu_fonts.items()}
    if not all(os.path.exists(path) for path in paths.values()):
        return "Helvetica"
    for name, path in paths.items():
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVuBd", italic="DejaVuOb",
                                  boldItalic="DejaVuBdOb")
    reportlab.rl_config.canvas_basefontname = "DejaVu"
    return "DejaVu"


default_fontname = register_fonts()
