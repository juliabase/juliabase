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

"""Helper routines for the various structuring layouts in the institute.
Layouts can create image maps for the browser so that one can click on single
structures on the layout.  And, they can draw themselves and write it to a PDF
file.

Layouts are set by the `institute.models.Structuring` process.  It defines the
structuring layout that was used for all following processes.  In the lab, most
layouts are realised with masks.

So far, we have only the cell structuring layouts implemented.  They are used
in the solarsimulator measurements.
"""

from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
import reportlab.pdfbase.pdfmetrics
from django.conf import settings
import jb_common.utils.base as utils
import institute.models
from institute.reportlab_config import default_fontname


class NoStructuringFound(Exception):
    def __init__(self, sample, timestamp):
        message = "No structuring process before {0} for sample {1} found.".format(timestamp, sample) if timestamp else \
            "No structuring process for sample {0} found.".format(sample)
        super().__init__(message)


def get_current_structuring(sample, timestamp=None):
    """Returns the most recent structuring process of the given sample, optionally
    before a timestamp.  This timestamp typically is the timestamp of the
    process that needs the structuring, e.g. a solarsimulator measurement.

    :param sample: the sample whose last structuring should be found
    :param timestamp: the found structuring is the latest structuring before or
        on this timestamp

    :type sample: `samples.models.Sample`
    :type timestamp: datetime.datetime

    :return:
      The last structuring object of the sample.  Note that it is not the
      actual instance of that structuring but an instance of the common base
      class.

    :rtype: `institute.models.Structuring`

    :raises NoStructuringFound: if no matching structuring was found
    """
    query_set = institute.models.Structuring.objects.filter(samples=sample)
    if timestamp:
        query_set = query_set.filter(timestamp__lte=timestamp)
    try:
        return query_set.latest("timestamp")
    except institute.models.Structuring.DoesNotExist:
        raise NoStructuringFound(sample, timestamp)


def get_layout(sample, process):
    """Factory function for layouts.  It looks for the proper layout for the
    given process (in particular, it determines which structuring is “in
    charge” at the timestamp of the process), adapts it to the process and the
    sample, and returns it.

    :param sample: the sample whose last structuring should be found
    :param process: the process for which the structuring should be found,
        e.g. a solarsimulator measurement

    :type sample: `samples.Sample`
    :type process: `samples.Process`

    :return:
      The layout object suitable for the given sample and process.  ``None`` if
      no layout layout could be determined, either because there is no
      ``Structuring`` process, or because it doesn't contain a layout for which
      there is a layout class.

    :rtype: `Layout` or NoneType
    """
    # FixMe: With another parameter, the caller should be enabled to limit the
    # found layouts to those that are of a certain class (or its derivatives).
    # For example, solarsimulator measurement only want ``CellsLayout`` because
    # they need its interface.  Alternatively, this function does the limiting
    # itself basing on the type of `process`.  However, this may be too
    # implicit.
    try:
        current_structuring = get_current_structuring(sample, process.timestamp)
    except NoStructuringFound:
        return None
    else:
        layout_class = {"inm standard": INMStandard,
                        "acme1": ACME1}.get(current_structuring.layout)
        return layout_class and layout_class(sample, process, current_structuring)


def _draw_constrained_text(canvas, text, x, y, fontsize, width, graylevel, background_color):
    """Draws a text *really* centred, i.e. it is also vertically centred in
    contrast to ReportLab's ``drawCentredString``.  The fontsize is scaled down
    if there is not enough space but there is a lower limit.  Furthermore, the
    fontsize can only be of certain values so that only a few fontsizes are on
    use on the image (which pleases the eye).

    :param canvas: the ReportLab convas to draw on
    :param text: the text to be printed
    :param x: the x coordinate of the centre of the printed text
    :param y: the y coordinate of the centre of the printed text (not the y
        coordinate of the baseline!)
    :param fontsize: the desired fontsize; the font may be scaled down if there
        is not enough space
    :param width: the available width for the text
    :param graylevel: brightness of the text; ``0`` means black and ``1`` means
        white
    :param background_color: the colour of the background to print on as an
        (red, green, blue) tuple; this is only used if the text is too wide and
        needs to be supported by a background rectangle

    :type canvas: canvas.Canvas
    :type text: str
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


class Layout:
    """Abstract base class for structuring layouts.  The main purpose of
    layouts is to have something to draw.

    Layout instances are always connected with one particular sample and one
    particular process.  Additionally, the ``Structuring`` process which led to
    this layout is stored in the instance.

    :ivar height: height of the layout in bp
    :ivar width: width of the layout in bp
    :ivar sample: the sample with this layout
    :ivar process: the process for which this layout is created (*not* the
      process that created this layout!
    :ivar structuring: the structuring process which was used to determine
      which layout to use

    :type height: float
    :type width: float
    :type sample: `samples.models.Sample`
    :type process: `samples.models.Process`
    :type structuring: `institute.models.Structuring`
    """
    width = 80 * mm
    height = 80 * mm

    def __init__(self, sample, process, structuring):
        self.sample = sample
        self.process = process
        self.structuring = structuring

    def draw_layout(self, canvas):
        """Draws the layout on the given canvas.  You must override this
        method.

        :param canvas: the ReportLab canvas

        :type filename: canvas.Canvas

        :return:
          the canvas object

        :rtype: canvas.Canvas
        """
        raise NotImplementedError

    def generate_pdf(self, filename):
        """Draws the layout and writes it to a PDF file.

        :param filename: the full path to the PDF that should be created

        :type filename: str
        """
        canvas = Canvas(filename, pagesize=(self.width, self.height))
        self.draw_layout(canvas)
        canvas.showPage()
        canvas.save()


class CellsLayout(Layout):
    """Abstract class for cell layouts.  These layouts are primarily used in
    solarsimulator measurements.  All cells are rectangles.  Try to make the
    height and width of the mask close to 80 because font sizes and line
    thicknesses are optimised for this size.

    :ivar shapes: all cells on the layout; this is a dictionary mapping the
      cell's position (which may be an ordinary number) to a tuple ((origin_x,
      origin_y), (width, height)).  “Origin” is the lower left corner of the
      cell's rectangle.

      The position of the cell must consist only of letters, digits,
      underscores and dashs.  Don't assume that it is case-sensitive.

    :type shapes: dict mapping str to ((float, float), (float, float))
    """
    shapes = {}

    def get_map_shapes(self):
        """Returns the data needed to build an HTML image map for the cell
        layout.

        :return:
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

        :rtype: dict mapping str to dict mapping str to str
        """
        map_shapes = {}
        resolution = settings.THUMBNAIL_WIDTH / self.width
        for key, coords in self.shapes.items():
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

        :param solarsimulator_measurement: the solarsimulator measurement for
            which the colouring should be determined

        :type solarsimulator_measurement:
          `institute.models.SolarsimulatorMeasurement`

        :return:
          the colours and labels as a dictionary mapping the cell position to a
          tuple (colour, label), where “colour” is given as a (red, green,
          blue) tuple.

        :rtype: dict mapping str to ((float, float, float), str)
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
        irradiation = solarsimulator_measurement.irradiation
        colors_and_labels = {}
        cell_measurements = solarsimulator_measurement.cells.all()
        for cell in cell_measurements:
            if irradiation == "AM1.5":
                color = map_value_to_RGB(cell.eta, [0.33, 3.1, 5.3, 6.3, 7.0, 7.7, 8.4, 9.2])
                label = utils.round(cell.eta, 3)
            elif irradiation == "OG590":
                color = map_value_to_RGB(cell.isc, [2.5, 3.6, 4.3, 5.0, 6.7, 9.1, 10, 12])
                label = utils.round(cell.isc, 3)
            elif irradiation == "BG7":
                color = map_value_to_RGB(cell.isc, [1.66, 2.45, 2.65, 2.77, 2.87, 2.93, 3.00, 3.13])
                label = utils.round(cell.isc, 3)
            else:
                color = (0, 0, 0)
                label = None
            colors_and_labels[cell.position] = (color, label)
        return colors_and_labels

    def draw_layout(self, canvas):
        if isinstance(self.process, (institute.models.SolarsimulatorMeasurement)):
            colors_and_labels = self._get_colors_and_labels(self.process)
            if self.process.irradiation == "AM1.5":
                global_label = "η in %"
            elif self.process.irradiation in ["OG590", "BG7"]:
                global_label = "Isc in mA/cm²"
            else:
                global_label = None
            if global_label:
                fontsize = 8
                canvas.setFontSize(fontsize)
                descent = reportlab.pdfbase.pdfmetrics.getDescent(default_fontname, fontsize)
                canvas.setFillColorRGB(0, 0, 0)
                canvas.drawCentredString(self.width / 2, -descent, global_label)
        else:
            colors_and_labels = {}
        for index, coords in self.shapes.items():
            origin, dimensions = coords
            try:
                color, label = colors_and_labels[index]
            except KeyError:
                color = (0.85, 0.85, 0.85)
                label = None
            canvas.setFillColorRGB(*color)
            canvas.rect(origin[0], origin[1], dimensions[0], dimensions[1], fill=1)
            if label:
                if 0.3 * color[0] + 0.59 * color[1] + 0.11 * color[2] < 0.3:
                    text_graylevel = 1
                else:
                    text_graylevel = 0
                _draw_constrained_text(canvas, label, (origin[0] + dimensions[0] / 2), (origin[1] + dimensions[1] / 2),
                                       9, dimensions[0], text_graylevel, background_color=color)
        return canvas


class INMStandard(CellsLayout):
    height = (105 - 30) * mm
    width = (110 - 30) * mm
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

    for index, coords in shapes.items():
        shapes[index] = ((coords[0][0] - 15, coords[0][1] - 15), coords[1])

    _scaling = 80 * mm / max(height, width)
    for index, coords in shapes.items():
        shapes[index] = ((_scaling * coords[0][0] * mm, _scaling * coords[0][1] * mm),
                         (_scaling * coords[1][0] * mm, _scaling * coords[1][1] * mm))
    height *= _scaling
    width *= _scaling


class ACME1(CellsLayout):
    width = 34.84 * mm
    height = 34.84 * mm
    shapes = {"1A": ((4.42, 29.12), (2.6, 2.6)),
              "1B": ((12.22, 29.12), (2.6, 2.6)),
              "1C": ((20.02, 29.12), (2.6, 2.6)),
              "1D": ((27.82, 29.12), (2.6, 2.6)),
              "2A": ((4.42, 22.62), (3.9, 3.9)),
              "2B": ((12.22, 22.62), (3.9, 3.9)),
              "2C": ((20.02, 22.62), (3.9, 3.9)),
              "2D": ((27.82, 22.62), (3.9, 3.9)),
              "3A": ((4.42, 16.12), (2.6, 2.6)),
              "3B": ((12.22, 16.12), (2.6, 2.6)),
              "3C": ((20.02, 16.12), (2.6, 2.6)),
              "3D": ((27.82, 16.12), (2.6, 2.6)),
              "4A": ((4.42, 8.32), (3.9, 3.9)),
              "4B": ((12.22, 8.32), (3.9, 3.9)),
              "4C": ((20.02, 8.32), (3.9, 3.9)),
              "4D": ((27.82, 8.32), (3.9, 3.9)),
              "5A": ((4.42, 3.12), (2.6, 2.6)),
              "5B": ((12.22, 3.12), (2.6, 2.6)),
              "5C": ((20.02, 3.12), (2.6, 2.6)),
              "5D": ((27.82, 3.12), (2.6, 2.6))}

    _scaling = 80 * mm / max(height, width)
    for cell_index, coords in shapes.items():
        shapes[cell_index] = ((_scaling * coords[0][0] * mm, _scaling * coords[0][1] * mm),
                              (_scaling * coords[1][0] * mm, _scaling * coords[1][1] * mm))
    height *= _scaling
    width *= _scaling
