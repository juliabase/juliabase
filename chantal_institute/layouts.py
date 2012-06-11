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

"""Helper routines for the various structuring layouts in the institute.
Layouts can create image maps for the browser so that one can click on single
structures on the layout.  And, they can draw themselves and write it to a PDF
file.

Layouts are set by the `chantal_institute.models.Structuring` process.  It defines
the structuring layout that was used for all following processes.  In the lab,
most layouts are realised with masks.

So far, we have only the cell structuring layouts implemented.  They are used
in the solarsimulator measurements.
"""

from __future__ import division, unicode_literals

from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
import reportlab.pdfbase.pdfmetrics
from django.conf import settings
import chantal_institute.models
from chantal_institute.reportlab_config import default_fontname
import samples.views.utils


class NoStructuringFound(Exception):
    """
    """
    def __init__(self, sample, timestamp):
        message = "No structuring process before {0} for sample {1} found.".format(timestamp, sample) if timestamp else \
            "No structuring process for sample {0} found.".format(sample)
        super(NoStructuringFound, self).__init__(message)


def get_current_structuring(sample, timestamp=None):
    """Returns the most recent structuring process of the given sample,
    optionally before a timestamp.  This timestamp typically is the timestamp
    of the process that needs the structuring, e.g. a MAIKE measurement.

    :Parameters:
      - `sample`: the sample whose last structuring should be found
      - `timestamp`: the found structuring is the latest structuring before or
        on this timestamp

    :type sample: `samples.Sample`
    :type timestamp: ``datetime.datetime``

    :Return:
      The last structuring object of the sample.  Note that it is not the
      actual instance of that structuring but an instance of the common base
      class.

    :rtype: `chantal_institute.models.Structuring`

    :Exceptions:
      - `NoStructuringFound`: if no matching structuring was found
    """
    query_set = chantal_institute.models.Structuring.objects.filter(samples=sample)
    if timestamp:
        query_set = query_set.filter(timestamp__lte=timestamp)
    try:
        return query_set.latest("timestamp")
    except chantal_institute.models.Structuring.DoesNotExist:
        raise NoStructuringFound(sample, timestamp)


def get_layout(sample, process):
    """Factory function for layouts.  It looks for the proper layout for the
    given process (in particular, it determines which structuring is “in
    charge” at the timestamp of the process), adapts it to the process and the
    sample, and returns it.

    FixMe: With another parameter, the caller should be enabled to limit the
    found layouts to those that are of a certain class (or its derivatives).
    For example, solarsimulator measurement only want ``CellsLayout`` because
    they need its interface.  Alternatively, this function does the limiting
    itself basing on the type of `process`.  However, this may be too implicit.

    :Parameters:
      - `sample`: the sample whose last structuring should be found
      - `process`: the process for which the structuring should be found,
        e.g. a solarsimulator measurement

    :type sample: `samples.Sample`
    :type process: `samples.Process`

    :Return:
      The layout object suitable for the given sample and process.  ``None`` if
      no layout layout could be determined, either because there is no
      ``Structuring`` process, or because it doesn't contain a layout for which
      there is a layout class.

    :rtype: `Layout` or ``NoneType``
    """
    try:
        current_structuring = get_current_structuring(sample, process.timestamp)
    except NoStructuringFound:
        return None
    else:
        layout_class = {"juelich standard": JuelichStandard, }.get(current_structuring.layout)
        return layout_class and layout_class(sample, process, current_structuring)


def _draw_constrained_text(canvas, text, x, y, fontsize, width, graylevel, background_color):
    """Draws a text *really* centred, i.e. it is also vertically centred in
    contrast to ReportLab's ``drawCentredString``.  The fontsize is scaled down
    if there is not enough space but there is a lower limit.  Furthermore, the
    fontsize can only be of certain values so that only a few fontsizes are on
    use on the image (which pleases the eye).

    :Parameters:
      - `canvas`: the ReportLab convas to draw on
      - `text`: the text to be printed
      - `x`: the x coordinate of the centre of the printed text
      - `y`: the y coordinate of the centre of the printed text (not the y
        coordinate of the baseline!)
      - `fontsize`: the desired fontsize; the font may be scaled down if there
        is not enough space
      - `width`: the available width for the text
      - `graylevel`: brightness of the text; ``0`` means black and ``1`` means
        white
      - `background_color`: the colour of the background to print on as an
        (red, green, blue) tuple; this is only used if the text is too wide and
        needs to be supported by a background rectangle

    :type canvas: `reportlab.pdfgen.canvas.Canvas`
    :type text: unicode
    :type x: float
    :type y: float
    :type fontsize: float
    :type width: float
    :type graylevel: float
    :type background_color: (float, float, float)
    """
    text_width_at_10pt = reportlab.pdfbase.pdfmetrics.stringWidth(text, default_fontname, 10)
    fitting_fontsize = width / text_width_at_10pt * 10
    fontsize = min(fitting_fontsize, fontsize)
    fontsize = int((fontsize - 1) / 2) * 2 + 1
    ascent, descent = reportlab.pdfbase.pdfmetrics.getAscentDescent(default_fontname, fontsize)
    if fontsize < 7:
        old_fontsize = fontsize
        fontsize = 7
        ascent, descent = fontsize / old_fontsize * ascent, fontsize / old_fontsize * descent
        text_width = text_width_at_10pt / 10 * fontsize
        canvas.setFillColorRGB(*background_color)
        canvas.rect(x - text_width / 2, y - ascent / 2 + descent, text_width, ascent - descent, stroke=0, fill=1)
    canvas.setFontSize(fontsize)
    canvas.setFillGray(graylevel)
    canvas.drawCentredString(x, y - ascent / 2, text)


class Layout(object):
    """Abstract base class for structuring layouts.  The main purpose of
    layouts is to have something to draw.

    Layout instances are always connected with one particular sample and one
    particular process.  Additionally, the ``Structuring`` process which led to
    this layout is stored in the instance.

    :ivar sample: the sample with this layout
    :ivar process: the process for which this layout is created (*not* the
      process that created this layout!
    :ivar structuring: the structuring process which was used to determine
      which layout to use

    :type sample: ``samples.models.Sample``
    :type process: ``samples.models.Process``
    :type structuring: `chantal_institute.models.Structuring`
    """

    def __init__(self, sample, process, structuring):
        self.sample = sample
        self.process = process
        self.structuring = structuring

    def draw_layout(self, filename):
        """Draws the layout and writes it to a PDF file.

        :Parameters:
          - `filename`: the full path to the PDF that should be created

        :type filename: unicode
        """
        raise NotImplementedError


class CellsLayout(Layout):
    """Abstract class for cell layouts.  These layouts are primarily used in
    solarsimulator measurements.  All cells are rectangles.  Try to make the
    height and width of the mask close to 80 because font sizes and line
    thicknesses are optimised for this size.

    :ivar height: height of the layout in arbitrary units
    :ivar width: width of the layout in arbitrary units
    :ivar shapes: all cells on the layout; this is a dictionary mapping the
      cell's position (which may be an ordinary number) to a tuple ((origin_x,
      origin_y), (width, height)).  “Origin” is the lower left corner of the
      cell's rectangle.

      The position of the cell must consist only of letters, digits,
      underscores and dashs.  Don't assume that it is case-sensitive.

    :type height: float
    :type width: float
    :type shapes: dict mapping unicode to ((float, float), (float, float))
    """
    height = None
    width = None
    shapes = {}

    def get_map_shapes(self):
        """Returns the data needed to build an HTML image map for the cell
        layout.

        :Return:
          the shapes for the image map, mapping the cell position to a
          dictionary containing two keys: ``"type"`` maps to the HTML area type
          (mostly ``"rect"``) and ``"coords"`` maps to the HTML area
          coordinates which is a string (which contains a comma-separated list
          of integers)

          Thus, the result may be for example::

              {"1": {"type": "rect", "coords": "432,543,532,653"},
               "2": {"type": "rect", "coords": "232,343,332,453"},
               ...
               }

        :rtype: dict mapping unicode to dict mapping str to str
        """
        map_shapes = {}
        resolution = settings.THUMBNAIL_WIDTH / self.width
        for key, coords in self.shapes.iteritems():
            map_shapes[key] = {"type": "rect",
                               "coords": ",".join(str(int(round(x * resolution))) for x in
                                                  (coords[0][0],
                                                   self.height - coords[0][1] - coords[1][1],
                                                   coords[0][0] + coords[1][0],
                                                   self.height - coords[0][1]))}
        return map_shapes

    @staticmethod
    def _get_colors_and_labels(solarsimulator_measurement):
        """Returns the colours and labels for all cells in a particular
        solarsimulator measurement.  This is a helper routine for
        `draw_layout`.

        :Parameters:
          - `solarsimulator_measurement`: the solarsimulator measurement for
            which the colouring should be determined

        :type solarsimulator_measurement:
          `chantal_institute.models.SolarsimulatorMeasurement`

        :Return:
          the colours and labels as a dictionary mapping the cell position to a
          tuple (colour, label), where “colour” is given as a (red, green,
          blue) tuple.

        :rtype: dict mapping unicode to ((float, float, float), unicode)
        """
        def map_value_to_RGB(value, thresholds):
            """Returns the cell colour associated with `value`.  `thresholds`
            is a list of threshold values.  It must contain 8 positive float
            items.

            `value` is η for AM1.5 measurements and Isc for BG7 and OG590
            measurements.  `thresholds` should be determined once by looking at
            the already-measured values: Each colour should occur with equal
            probability (the areas in the histogram of each colour are the
            same).
            """
            colors = [(0, 0, 0.5), (0, 0.6, 0.88), (0, 0.77, 0.8), (0.11, 0.64, 0.22), (0, 1, 0.2), (1, 0.9, 0),
                      (0.93, 0.68, 0.05), (1, 0.5, 0), (0.8, 0.07, 0)]
            assert len(thresholds) == len(colors) - 1
            i = 0
            while thresholds[i] < value:
                i += 1
                if i == len(thresholds):
                    return colors[-1]
            return colors[i]
        irradiance = solarsimulator_measurement.irradiance
        colors_and_labels = {}
        cell_measurements = solarsimulator_measurement.photo_cells.all()
        for cell in cell_measurements:
            if irradiance == "AM1.5":
                color = map_value_to_RGB(cell.eta, [0.33, 3.1, 5.3, 6.3, 7.0, 7.7, 8.4, 9.2])
                label = samples.views.utils.round(cell.eta, 3)
            elif irradiance == "OG590":
                color = map_value_to_RGB(cell.isc, [2.5, 3.6, 4.3, 5.0, 6.7, 9.1, 10, 12])
                label = samples.views.utils.round(cell.isc, 3)
            elif irradiance == "BG7":
                color = map_value_to_RGB(cell.isc, [1.66, 2.45, 2.65, 2.77, 2.87, 2.93, 3.00, 3.13])
                label = samples.views.utils.round(cell.isc, 3)
            else:
                color = (0, 0, 0)
                label = None
            colors_and_labels[cell.position] = (color, label)
        return colors_and_labels

    def draw_layout(self, filename):
        canvas = Canvas(filename, pagesize=(self.width * mm, self.height * mm))
        if isinstance(self.process, (chantal_institute.models.SolarsimulatorPhotoMeasurement)):
            colors_and_labels = self._get_colors_and_labels(self.process)
            if self.process.irradiance == "AM1.5":
                global_label = "η in %"
            elif self.process.irradiance in ["OG590", "BG7"]:
                global_label = "Isc in mA/cm²"
            else:
                global_label = None
            if global_label:
                fontsize = 8
                canvas.setFontSize(fontsize)
                descent = reportlab.pdfbase.pdfmetrics.getDescent(default_fontname, fontsize)
                canvas.drawCentredString(self.width * mm / 2, -descent, global_label)
        else:
            colors_and_labels = {}
        for cell_index, coords in self.shapes.iteritems():
            origin, dimensions = coords
            try:
                color, label = colors_and_labels[cell_index]
            except KeyError:
                color = (0.85, 0.85, 0.85)
                label = None
            canvas.setFillColorRGB(*color)
            canvas.rect(origin[0] * mm, origin[1] * mm, dimensions[0] * mm, dimensions[1] * mm, fill=1)
            if label:
                if 0.3 * color[0] + 0.59 * color[1] + 0.11 * color[2] < 0.3:
                    text_graylevel = 1
                else:
                    text_graylevel = 0
                _draw_constrained_text(canvas, label,
                                       (origin[0] + dimensions[0] / 2) * mm, (origin[1] + dimensions[1] / 2) * mm,
                                       9, dimensions[0] * mm, text_graylevel, background_color=color)
        resolution = settings.THUMBNAIL_WIDTH * 25.4 / self.width
        return canvas, resolution


class JuelichStandard(CellsLayout):
    height = 105 - 30
    width = 110 - 30
    shapes = {"1": ((18, 18.5), (10, 10)),
              "2": ((31.5, 18.5), (10, 10)),
              "3": ((43, 18.5), (10, 10)),
              "4": ((56.5, 18.5), (10, 10)),
              "5": ((68, 18.5), (10, 10)),
              "6": ((81.5, 18.5), (10, 10)),
              "7": ((18, 32.5), (10, 5)),
              "8": ((33, 32.5), (20, 5)),
              "9": ((60, 32.5), (2, 5)),
              "10": ((64, 32.5), (2, 5)),
              "11": ((68, 32.5), (2, 5)),
              "12": ((72, 32.5), (2, 5)),
              "13": ((81.5, 32.5), (10, 5)),
              "14": ((18, 43.5), (10, 10)),
              "15": ((31.5, 43.5), (10, 10)),
              "16": ((43, 43.5), (10, 10)),
              "17": ((56.5, 43.5), (10, 10)),
              "18": ((68, 43.5), (10, 10)),
              "19": ((81.5, 43.5), (10, 10)),
              "20": ((18, 57.5), (10, 5)),
              "21": ((35, 57.5), (2, 5)),
              "22": ((39, 57.5), (2, 5)),
              "23": ((43, 57.5), (2, 5)),
              "24": ((47, 57.5), (2, 5)),
              "25": ((58, 57.5), (20, 5)),
              "26": ((81.5, 57.5), (10, 5)),
              "27": ((18, 68.5), (10, 10)),
              "28": ((31.5, 68.5), (10, 10)),
              "29": ((43, 68.5), (10, 10)),
              "30": ((56.5, 68.5), (10, 10)),
              "31": ((68, 68.5), (10, 10)),
              "32": ((81.5, 68.5), (10, 10)),
              "33": ((18, 82.5), (10, 5)),
              "34": ((33, 82.5), (20, 5)),
              "35": ((58, 82.5), (20, 5)),
              "36": ((81.5, 82.5), (10, 5))}

    for cell_index, coords in shapes.iteritems():
        shapes[cell_index] = ((coords[0][0] - 15, coords[0][1] - 15), coords[1])

    _scaling = 80 / max(height, width)
    for cell_index, coords in shapes.iteritems():
        shapes[cell_index] = ((_scaling * coords[0][0], _scaling * coords[0][1]),
                              (_scaling * coords[1][0], _scaling * coords[1][1]))
    height *= _scaling
    width *= _scaling

