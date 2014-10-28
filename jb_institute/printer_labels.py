#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

"""Module for generating PDFs for the label printer.  These labels contain the
sample name and a QR code with the sample ID.  The most challenging task here
is to bring even long sample names on the label properly by compressing them
and/or splitting them into two lines.

All dimension variables here are in big points (bp) because this is the native
unit of measurement in ReportLab.
"""

from __future__ import division, unicode_literals, absolute_import
import django.utils.six as six
from django.utils.six.moves import cStringIO

import re
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
import jb_institute.reportlab_config


__all__ = ["printer_label"]


width = 4.5 * cm
height = 0.9 * cm
horizontal_margin = 0.05 * cm
vertical_margin = 0.05 * cm
vertical_relative_offset = 0.2
max_width_text = width - height - 2 * horizontal_margin
fontsize = height - 2 * vertical_margin
fontsize_half = height / 2 - 2 * vertical_margin


class ExcessException(Exception):
    """Raised if a single line becomes too long for the label.  While some
    horizontal compression of the glyphs is allowed, it may become too much.
    In this case, `ExcessException` is thrown.
    """
    pass

def print_line(canvas, y, fontsize, line, force=False):
    """Prints one line of text on the left-hand side of the label.

    :Parameters:
      - `canvas`: ReportLab canvas object
      - `y`: vertical coordinate of the lower left corner of the printed text.
        Note that the origin of the coordinate system is the lower left of the
        paper.
      - `fontsize`: font size of the text
      - `line`: the text to be printed; it must not contain line breaks
      - `force`: whether `ExcessException` should be raised if the text has to
        be compressed too much; if ``True``, the text may be compressed as much
        as necessary

    :type canvas: ``reportlab.pdfgen.canvas.Canvas``
    :type y: float
    :type fontsize: float
    :type line: unicode
    :type force: bool

    :Exceptions:
      - `ExcessException`: if the line is too long and `force` is ``False``
    """
    textobject = canvas.beginText()
    textobject.setFont(jb_institute.reportlab_config.default_fontname, fontsize)
    width = canvas.stringWidth(line, jb_institute.reportlab_config.default_fontname, fontsize)
    excess = width / max_width_text
    if excess > 2 and not force:
        raise ExcessException
    elif excess > 1:
        textobject.setHorizScale(100 / excess)
    textobject.setTextOrigin(horizontal_margin, y + vertical_margin + vertical_relative_offset * fontsize)
    textobject.textOut(line)
    canvas.drawText(textobject)


break_position_pattern = re.compile(r"(?<!\w|\()[^)]|\(", re.UNICODE)

def best_split(text):
    """Split `text` into to parts.  Both parts are supporsted to be similarly
    long.  Moreover, the point of splitting should be at an acceptable
    position, e.g. after a hyphen.  But if the is not possible, it is split in
    the middle.

    :Parameters:
      `text`: the text to be split

    :type text: unicode

    :Return:
      The first and the second part of `text` into which it was split.

    :rtype: unicode, unicode
    """
    half_position = len(text) // 2
    best_break_position = (None, None)
    for match in break_position_pattern.finditer(text):
        if match.start() > 0:
            distance = abs(match.start() - half_position)
            if distance < 5 and (best_break_position[0] is None or distance < best_break_position[0]):
                best_break_position = (distance, match.start())
    split = half_position if best_break_position[1] is None else best_break_position[1]
    return text[:split], text[split:]


def printer_label(sample):
    """Generate the PDF of a sample for the label printer.

    :Parameters:
      - `sample`: the sample the label of which should be generated

    :type sample: ``samples.models.Sample``

    :Return:
      the PDF as a byte stream

    :rtype: str
    """
    output = cStringIO.StringIO()
    text = sample.name
    c = canvas.Canvas(output, pagesize=(width, height))
    c.setAuthor("JuliaBase samples database")
    c.setTitle(text)
    c.setSubject("Label of {0} for the label printer".format(text))
    try:
        print_line(c, 0, fontsize, text)
    except ExcessException:
        first, second = best_split(text)
        print_line(c, height / 2, fontsize_half, first, force=True)
        print_line(c, 0, fontsize_half, second, force=True)
    c.drawImage(ImageReader("http://chart.apis.google.com/chart?chs=116x116&cht=qr&chl={0}&chld=H|1".format(sample.id)),
                width - height, 0, height, height)
    c.showPage()
    c.save()
    return output.getvalue()
