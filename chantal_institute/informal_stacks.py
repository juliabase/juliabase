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

"""Module for generating PDFs for layer stacks.  This is a rather complicated
multi-pass process because the sizes of the labels are a-priori unknown, so
they must be printed.  But they cannot be printed on the canvas because the
final size of the canvas is only known after the labels are printed.
Fortunately, ReportLab does not require labels to be actually printed for just
to measure them.

Moreover, labels may have to be relocated to the left-hand side of the stack or
to the lagend below because they are too big, which also means that the
`Paragraph` objects need to be re-created with different parameters.

Roughly speaking, we first measure all sizes and try to find the best positions
for then, *then* we create the PDF canvas and actually print them on it.

All dimension variables here are in big points (bp) because this is the native
unit of measurement in ReportLab.
"""


from __future__ import division, unicode_literals

import random, math, decimal
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.styles import PropertySet
from reportlab.lib.colors import black, getAllNamedColors
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import Paragraph


dimensions = {"stack_width": 3 * cm, "label_width": 3 * cm, "margin": 0.2 * cm, "red_line_width": 0.15 * cm,
              "red_line_skip": 0.1 * cm, "label_skip": 0.2 * cm, "scale_skip": 0.2 * cm, "legend_skip": 0.2 * cm,
              "scale_label_skip": 0.2 * cm}
"""Dictionary with all skips and lengths that can be changed even at runtime.

``stack_width``: the width of the stack diagram without any labels
``label_width``: the width of the labels at both sides of the stack
``margin``: the margin at a for edges around the whole diagram, excluding a
  possible red rim
``red_line_width``: the width of the red rim
``red_line_skip``: the distance between the red rim and the border of the PDF
``label_skip``: the distance of the labels and the stack
``scale_skip``: the vertical distance between the scale and the stack below
``legend_skip: the vertical distance between the legend and the stack above
``scale_label_skip``: the distance between the scale bar and the scale label
"""
parameters = {"roughness": 3, "grid_points": 24}
"""Dictionary with further parameters that can be changed even at runtime.

``roughness``: the roughness of the textured lines in bp
``grid_points``: number of grid points used for the textured line
"""


class SingleLabelStyle(PropertySet):
    """Style which is used for the labels on both sides of the stack.
    """
    defaults = {
        "fontName": "DejaVu", "fontSize": 10, "leading": 12, "leftIndent": 0, "rightIndent": 0, "firstLineIndent": 0,
        "alignment": TA_LEFT, "spaceBefore": 0, "spaceAfter": 0, "bulletFontName": "DejaVu", "bulletFontSize": 10,
        "bulletIndent": 0, "textColor": black, "backColor": None, "wordWrap": None, "borderWidth": 0, "borderPadding": 0,
        "borderColor": None, "borderRadius": None, "allowWidows": 1, "allowOrphans": 0, "textTransform": None}


class LegendLabelStyle(PropertySet):
    """Style which is used for the optional legend below the stack.
    """
    defaults = {
        "fontName": "DejaVu", "fontSize": 10, "leading": 12, "leftIndent": 14.5, "rightIndent": 0, "firstLineIndent":-14.5,
        "alignment": TA_LEFT, "spaceBefore": 0, "spaceAfter": 10, "bulletFontName": "DejaVu", "bulletFontSize": 10,
        "bulletIndent": 0, "textColor": black, "backColor": None, "wordWrap": None, "borderWidth": 0, "borderPadding": 0,
        "borderColor": None, "borderRadius": None, "allowWidows": 1, "allowOrphans": 0, "textTransform": None}

lineskip = SingleLabelStyle.defaults["leading"]
line_height = SingleLabelStyle.defaults["fontSize"]


def get_circled_number(number, largest_number):
    """Converts a number to a string using the nicest way possible.  If only
    numbers ≤ 10 occur in the diagram, the circled unicode numbers like “➉” are
    used.  Otherwise, a layout like “(10)” is used as a fallback.

    :Parameters:
      - `number`: the number to be converted
      - `largest_number`: the largest number which occurs in the diagram

    :type number: int
    :type largest_number: int

    :Return:
      a nice-looking string representation of the number

    :rtype: unicode
    """
    if largest_number > 10:
        return "({0})".format(number)
    else:
        return "➀➁➂➃➄➅➆➇➈➉"[number - 1]


class Path(object):
    """Helper class for drawing the layer stack.  It is used in a late stage
    of drawing the diagram, when the PDF canvas is already prepared.  It helps
    to draw the outline of a single layer consisting of basic shapes like
    vertical lines or textured horizontal lines.  This way, the caller has
    complete flexibility, which is needed because the properties of a layer
    (structured, textured, collapsed) can be arbitrarily combinated.

    :ivar textured_points: the grid points for the textured line; it consists
      of (x, y) pairs of coordinates.  The y coordinate oscillates around zero.

    :ivar edge_indices: The indices within `textured_points` of the places
      where the vertical edges of the layer join the horizonal edges.  This is
      needed for structured layers: Here, we have two columns the horizontal
      edges of which lie somewhere in the middle of the layer.  This list
      consists of four elements, namely the left and right index of the left
      column, and the left and right index of the right column.

    :ivar voffset: The vertical coordinate of the lower edge of the layer.
      ``voffset`` + ``height`` = ``accumulated_height``.

    :type textured_points: list of (float, float)
    :type edge_indices: list of int
    :type voffset: float
    """

    def __init__(self, canvas, segment, height, accumulated_height, textured, bottom_layer, fill_color=None):
        """Class constructor.

        :Parameters:
          - `canvas`: the PDF canvas object
          - `segment`: The layer segment to be drawn.  It may be ``"whole"``,
            ``"left"``, or ``"right"``.  The latter two are used for structured
            samples to draw the two columns they consist of.
          - `height`: height of the layer
          - `accumulated_height`: height of the layer measured from the very
            bottom of the stack
          - `textured`: whether the layer is textured
          - `bottom_layer`: the next non-structured layer below the current one
          - `fill_color`: the color of the filling; if not given, just the outline
            is drawn

        :type canvas: `canvas.Canvas`
        :type segment: str
        :type height: float
        :type accumulated_height: float
        :type textured: bool
        :type bottom_layer: `Layer`
        :type fill_color: str
        """
        self.canvas, self.segment, self.height, self.accumulated_height, self.fill_color = \
            canvas, segment, height, accumulated_height, fill_color

        random.seed(1)
        self.textured_points = [(dimensions["stack_width"] / parameters["grid_points"] * i,
                                 random.uniform(-parameters["roughness"], parameters["roughness"]))
                                for i in range(parameters["grid_points"] + 1)]
        self.edge_indices = [int(round(x * parameters["grid_points"])) for x in [1 / 8, 3 / 8, 5 / 8, 7 / 8]]

        self.voffset = 0 if fill_color or not bottom_layer else bottom_layer.accumulated_height
        bottom_textured = bottom_layer and bottom_layer.textured
        self.p = canvas.beginPath()
        if segment == "whole":
            self.bottom_left = (0,
                                0 if fill_color else self.voffset + (self.textured_points[0][1] if bottom_textured else 0))
            self.top_left = (self.bottom_left[0], (self.textured_points[0][1] if textured else 0) + accumulated_height)
            self.bottom_right = (dimensions["stack_width"],
                                 0 if fill_color else self.voffset + (self.textured_points[-1][1] if bottom_textured else 0))
            self.top_right = (self.bottom_right[0], (self.textured_points[-1][1] if textured else 0) + accumulated_height)
        elif segment == "left":
            self.bottom_left = (self.textured_points[self.edge_indices[0]][0], 0 if fill_color else
                                self.voffset + (self.textured_points[self.edge_indices[0]][1] if bottom_textured else 0))
            self.top_left = (self.bottom_left[0],
                             (self.textured_points[self.edge_indices[0]][1] if textured else 0) + accumulated_height)
            self.bottom_right = (self.textured_points[self.edge_indices[1]][0], 0 if fill_color else
                                 self.voffset + (self.textured_points[self.edge_indices[1]][1] if bottom_textured else 0))
            self.top_right = (self.bottom_right[0],
                              (self.textured_points[self.edge_indices[1]][1] if textured else 0) + accumulated_height)
        else:
            self.bottom_left = (self.textured_points[self.edge_indices[2]][0], 0 if fill_color else
                                self.voffset + (self.textured_points[self.edge_indices[2]][1] if bottom_textured else 0))
            self.top_left = (self.bottom_left[0],
                             (self.textured_points[self.edge_indices[2]][1] if textured else 0) + accumulated_height)
            self.bottom_right = (self.textured_points[self.edge_indices[3]][0], 0 if fill_color else
                                 self.voffset + (self.textured_points[self.edge_indices[3]][1] if bottom_textured else 0))
            self.top_right = (self.bottom_right[0],
                              (self.textured_points[self.edge_indices[3]][1] if textured else 0) + accumulated_height)
        self.p.moveTo(*self.bottom_left)

    def draw_vertical_line(self, direction):
        """Draws a vertical line of the layer (segment).

        :Parameters:
          - `direction`: the direction the line should be drawn; may be
            ``"up"`` or ``"down"``

        :type direction: str
        """
        if direction == "up":
            self.p.lineTo(*self.top_left)
        else:
            self.p.lineTo(*self.bottom_right)

    def draw_horizontal_line(self, direction):
        """Draws a straight horizontal line of the layer (segment).

        :Parameters:
          - `direction`: the direction the line should be drawn; may be
            ``"right"`` or ``"left"``

        :type direction: str
        """
        if direction == "right":
            self.p.lineTo(*self.top_right)
        else:
            self.p.lineTo(*self.bottom_left)

    def draw_textured_line(self, direction):
        """Draws a textured (= jagged) horizontal line of the layer (segment).

        :Parameters:
          - `direction`: the direction the line should be drawn; may be
            ``"right"`` or ``"left"``

        :type direction: str
        """
        if direction == "right":
            if self.segment == "left":
                points = [(x, self.accumulated_height + offset)
                          for x, offset in self.textured_points[self.edge_indices[0] + 1:self.edge_indices[1] + 1]]
            elif self.segment == "right":
                points = [(x, self.accumulated_height + offset)
                          for x, offset in self.textured_points[self.edge_indices[2] + 1:self.edge_indices[3] + 1]]
            else:
                points = [(x, self.accumulated_height + offset) for x, offset in self.textured_points[1:]]
        else:
            if self.segment == "left":
                points = [(x, offset + self.voffset)
                          for x, offset in self.textured_points[self.edge_indices[1] - 1:self.edge_indices[0] - 1:-1]]
            elif self.segment == "right":
                points = [(x, offset + self.voffset)
                          for x, offset in self.textured_points[self.edge_indices[3] - 1:self.edge_indices[2] - 1:-1]]
            else:
                points = [(x, offset + self.voffset) for x, offset in self.textured_points[-2::-1]]
        for x, y in points:
            self.p.lineTo(x, y)

    def draw_collapsed_line(self, direction):
        """Draws an interrupted vertical line of the layer (segment) in order
        to denote a collapsed layer.

        :Parameters:
          - `direction`: the direction the line should be drawn; may be
            ``"up"`` or ``"down"``

        :type direction: str
        """
        gap = 3
        protusion = 3
        mid_edge = self.accumulated_height - self.height / 2
        if direction == "up":
            x = self.top_left[0]
            y = mid_edge - gap / 2
            self.p.lineTo(x, y)
            self.p.moveTo(x + protusion, y + protusion)
            self.p.lineTo(x - protusion, y - protusion)
            self.p.moveTo(x, y)
            y = mid_edge + gap / 2
            self.p.moveTo(x, y)
            self.p.moveTo(x + protusion, y + protusion)
            self.p.lineTo(x - protusion, y - protusion)
            self.p.moveTo(x, y)
            self.p.lineTo(*self.top_left)
        else:
            x = self.bottom_right[0]
            y = mid_edge + gap / 2
            self.p.lineTo(x, y)
            self.p.moveTo(x - protusion, y - protusion)
            self.p.lineTo(x + protusion, y + protusion)
            self.p.moveTo(x, y)
            y = mid_edge - gap / 2
            self.p.moveTo(x, y)
            self.p.moveTo(x - protusion, y - protusion)
            self.p.lineTo(x + protusion, y + protusion)
            self.p.moveTo(x, y)
            self.p.lineTo(*self.bottom_right)

    def draw(self):
        """Actually draws the filled or outlined path on the canvas.
        """
        if self.fill_color:
            self.canvas.setFillColor(getAllNamedColors()[self.fill_color])
            self.canvas.drawPath(self.p, fill=True, stroke=False)
        else:
            self.canvas.drawPath(self.p, fill=False, stroke=True)


class Layer(object):
    """Class which holds one layer of a stack.

    :ivar name: the name or label of the layer

    :ivar nm: The thickness of the layer in nm.  This should be negative
      (e.g. −1) for mere treatments like an HF dip.

    :ivar color: the color name of the layer; it must be a color name known to
      ReportLab

    :ivar structured: whether the layer is not completely covering but
      structured

    :ivar textured: whether the top surface of the layer is textured by e.g. an
      etching process

    :ivar verified: whether the accuracy of the data of this layer has been
      verified my a human

    :ivar label: the typeset label of the label

    :ivar label_height: the height of the label

    :ivar one_liner: whether the typeset label consists of only a single line

    :ivar collapsed: whether the layer should be displayed collapsed (i.e. with
      broken vertical edges) because it would be too thick otherwise

    :ivar height: the height of the printed layer

    :ivar accumulated_height: the height of the printed layer measured from the
      common baseline at the very bottom of the stack

    :ivar bottom_layer: the next layer below this one which is not structured,
      i.e. covers the whole width; this is the layer the current one grows on;
      if it is ``None``, the current layer „grows“ on the very bottom of the
      stack.

    :type name: unicode
    :type nm: float
    :type color: str
    :type structured: bool
    :type textured: bool
    :type verified: bool
    :type label: `Paragraph`
    :type label_height: float
    :type one_liner: bool
    :type collapsed: bool
    :type height: float
    :type accumulated_height: float
    :type bottom_layer: `layer`
    """

    def __init__(self, informal_layer):
        """Class constructor.

        :Parameters:
          - `informal_layer`: the informal layer object from the database

        :type informal_layer: ``models.InformalLayer``
        """
        self.nm, self.color, self.structured, self.textured, self.verified, self.collapsed = \
            float(informal_layer.thickness), informal_layer.color, informal_layer.structured, \
            informal_layer.textured, informal_layer.verified, informal_layer.always_collapsed or None
        if informal_layer.classification and informal_layer.doping:
            name = informal_layer.get_doping_display() + "-" + informal_layer.get_classification_display()
        else:
            name = informal_layer.get_classification_display()
        if name:
            if informal_layer.comments:
                name += ", " + informal_layer.comments
        else:
            name = informal_layer.comments
        if informal_layer.thickness_reliable and informal_layer.thickness >= 0:
            name = "{0} ({1})".format(name, self.format_thickness(informal_layer.thickness))
        if not self.verified:
            name = """<font color="red"><strong>{0} ??</strong></font>""".format(name)
        self.name = name
        self.label = self.label_height = self.one_liner = self.height = self.accumulated_height = self.bottom_layer = None

    @staticmethod
    def format_thickness(nm):
        """Create a pretty-printed version of the thickness value including a
        unit of measument.

        :Parameters:
          - `nm`: The thickness of the layer in nm.  This should be negative
            (e.g. −1) for mere treatments like an HF dip.  Note that it is not
            a float but a decimal value.

        :type nm: `decimal.Decimal`

        :Return:
          the pretty-printed version of the thickness including the unit

        :rtype: unicode
        """
        if nm >= decimal.Decimal("1e6"):
            value = nm / decimal.Decimal("1e6")
            unit = "mm"
        elif nm >= decimal.Decimal("1e3"):
            value = nm / decimal.Decimal("1e3")
            unit = "µm"
        else:
            value = nm
            unit = "nm"
        value = unicode(value)
        if "." in value:
            value = value.rstrip("0")
            if value.endswith("."):
                value = value[:-1]
        return "{0} {1}".format(value, unit)

    def draw(self, canvas):
        """Draw this layer on the PDF canvas.  It draws both the outline and
        the filling.

        :Parameters:
          - `canvas`: the PDF canvas object

        :type canvas: `Canvas`
        """
        def draw_column(column):
            path = Path(canvas, column, self.height, self.accumulated_height, self.textured, self.bottom_layer, self.color)
            path.draw_vertical_line("up")
            if self.textured:
                path.draw_textured_line("right")
            else:
                path.draw_horizontal_line("right")
            path.draw_vertical_line("down")
            path.draw_horizontal_line("left")
            path.draw()

            path = Path(canvas, column, self.height, self.accumulated_height, self.textured, self.bottom_layer)
            if self.collapsed:
                path.draw_collapsed_line("up")
            else:
                path.draw_vertical_line("up")
            if self.textured:
                path.draw_textured_line("right")
            else:
                path.draw_horizontal_line("right")
            if self.collapsed:
                path.draw_collapsed_line("down")
            else:
                path.draw_vertical_line("down")
            if self.bottom_layer and self.bottom_layer.textured:
                path.draw_textured_line("left")
            else:
                path.draw_horizontal_line("left")
            path.draw()
        if self.structured:
            draw_column("left")
            draw_column("right")
        else:
            draw_column("whole")


class Scale(object):
    """Class which holds the scale of the diagram.  This covers two tasks:
    First, to draw the scale at the top of the diagram, and secondly, to
    convert lengths given in nm to bp.

    :ivar scale: the scale factor of the diagram

    :ivar magnitude: the order of magnitude of the scale bar

    :ivar factor: the factor of the scale bar.  The height of the scale bar in
      nm is

      ::

          factor * 10 ** magnitude

    :ivar scale_height: the height of the scale bar in bp

    :type scale: float
    :type magnitude: int
    :type factor: int
    :type scale_height: float
    """

    def __init__(self, layers):
        """Find the optimal scaling for the diagram.

        :Parameters:
          - `layers`: all layers of the stack

        :type layers: list of `Layer`

        :Return:
          The scaling in bp/nm, the height of the scale bar in bp, the factor of
          the scale bar, and its magnitude.  The height of the scale bar in nm is

          ::

              factor * 10 ** magnitude

        :rtype: float, float, int, int
        """
        thicknesses = [layer.nm for layer in layers if layer.nm > 0]
        thicknesses.sort(reverse=True)
        if thicknesses:
            self.scale = 2 * 10 ** (1 / 10) * lineskip / thicknesses[len(thicknesses) // 2]
        else:
            self.scale = 2 * 10 ** (1 / 10) * lineskip / 1000
        # In order to snap the scale to discrete values
        self.scale = 10 ** (round(math.log10(self.scale) * 5) / 5)

        self.magnitude = 1
        while self.magnitude < 9:
            for self.factor in [1, 2, 5]:
                self.scale_height = self.scale * 10 ** self.magnitude * self.factor
                if self.scale_height > 0.7 * cm:
                    break
            else:
                self.magnitude += 1
                continue
            break

    def draw(self, canvas):
        """Draws the scale bar and its label on the PDF canvas.  Note that you
        must select the position of the scale by calling ``canvas.translate``
        before.

        :Parameters:
          - `canvas`: the PDF canvas to be used

        :type canvas: `Canvas`
        """
        protusion = 2
        canvas.line(0, 0, 0, self.scale_height)
        canvas.line(-protusion, 0, protusion, 0)
        canvas.line(-protusion, self.scale_height, protusion, self.scale_height)
        scale_label = unicode(self.factor) + \
            [None, "0 nm", "00 nm", " µm", "0 µm", "00 µm", " mm", "0 mm", "00 mm"][self.magnitude]
        canvas.drawString(dimensions["scale_label_skip"], self.scale_height / 2 - line_height / 2, scale_label)

    def __call__(self, length):
        """Converts from nm to bp.

        :Parameters:
          - `length`: the length in nm

        :type nm: float

        :Return:
          the length in bp

        :rtype: float
        """
        return self.scale * length


def build_stack(layers, scale):
    """Pre-calculate the layout of the stack and its labels.  Nothing is
    actually drawn here.  Instead, this routine calculates the layer heights on
    the canvas, as well as the label dimensions.  Both is used to calculate the
    total size of the diagram and to position the labels.  (*Then* it is
    possible to actuall create the ``Canvas`` object and to draw on it.  But
    this is not done here.)

    :Parameters:
      - `layers`: the layers to be drawn, in the chronological order of their
        making
      - `scale`: the scale of the diagram

    :type layers: list of `Layer`
    :type scale: `Scale`

    :Return:
      the height of the printed stack

    :rtype: float
    """
    style = SingleLabelStyle("label")
    total_height = 0
    for i, layer in enumerate(layers):
        layer.height = scale(layer.nm) if layer.nm > 0 else 0
        if layer.collapsed is None:
            layer.collapsed = layer.height > 10 * lineskip
        if layer.collapsed:
            layer.height = 2 * lineskip
        layer.label = Paragraph(layer.name, style)
        __, layer.label_height = layer.label.wrap(dimensions["label_width"], 10 * lineskip)
        layer.one_liner = len(layer.label.blPara.lines) == 1
        if i == 0:
            layer.bottom_layer = None
        elif layer.structured:
            layer.bottom_layer = layers[i - 1]
        else:
            j = i - 1
            while layers[j].structured or layers[j].nm < 0:
                j -= 1
                if j < 0:
                    layer.bottom_layer = None
                    break
            else:
                layer.bottom_layer = layers[j]
        total_height += layer.height
        layer.accumulated_height = total_height
    return total_height


class Label(object):
    """Class for labels of layers.

    :cvar needs_left_row: whether the space left to the stack must be used for
      labels, too; it is ``True`` iff at least one label is placed to the left
      of the stack

    :ivar text: the content of the label

    :ivar voffset: the vertical distance between the bottom of the stack
      diagram and the centre of the label

    :ivar right_row: see constructor

    :type needs_left_row: bool
    :type text: unicode
    :type voffset: float
    :type right_row: bool
    """
    needs_left_row = False

    def __init__(self, layer, right_row):
        """Class constructor.

        :Parameters:
          - `layer`: the layer of this label
          - `right_row`: whether the label should be placed to the right of the
            stack; if ``False``, it is positioned to the left

        :type layer: `Layer`
        :type right_row: bool
        """
        self.text, self.voffset, self.right_row = layer.name, layer.accumulated_height - layer.height / 2, right_row
        if not right_row:
            Label.needs_left_row = True

    def print_label(self, canvas):
        """Draws the label on the canvas.

        :Parameters:
          - `canvas`: the PDF canvas to be used

        :type canvas: `Canvas`
        """
        if self.needs_left_row:
            hoffset = dimensions["label_width"] + dimensions["stack_width"] + 2 * dimensions["label_skip"] \
                if self.right_row else 0
        else:
            hoffset = dimensions["stack_width"] + dimensions["label_skip"] if self.right_row else 0
        if not self.right_row:
            self.text = """<para alignment="right">{0}</para>""".format(self.text)
        style = SingleLabelStyle("label")
        paragraph = Paragraph(self.text, style)
        __, height = paragraph.wrap(dimensions["label_width"], 10 * lineskip)
        paragraph.drawOn(canvas, hoffset, self.voffset - height / 2)


class NumberedLabel(Label):
    """Class for labels which consists of (circled) numbers because the actual
    label(s) are too big to be printed next to the layer(s).  This may have a
    from–to form like “➁–➄” or may be a single number like “➆”.

    :cvar largest_number: the largest number that occurs in the diagram.  It is
      needed because if it exceeds 10, the circled numbers from Unicode aren't
      sufficient anymore (Unicode contains only 1–10).  Thus, we have to
      fallback to parentheses then for *all* numbers: (1), (2), etc.

    :ivar lower: see constructor

    :ivar upper: see constructor

    :ivar voffset: see constructor

    :ivar right_row: see constructor

    :type largest_number: int
    :type lower: int
    :type upper: int
    :type voffset: float
    :type right_row: bool
    """
    largest_number = None

    def __init__(self, lower, upper, voffset, right_row):
        """Class constructor.

        :Parameters:
          - `lower`: the lower boundary of the numbers interval
          - `upper`: the upper boundary of the numbers interval; thus, if this
            label contains only one number, ``upper`` − ``lower`` = 1
          - `voffset`: the vertical distance between the bottom of the stack
            diagram and the centre of the label
          - `right_row`: whether the label should be placed to the right of the
            stack; if ``False``, it is positioned to the left

        :type lower: int
        :type upper: int
        :type voffset: float
        :type right_row: bool
        """
        self.lower, self.upper, self.voffset, self.right_row = lower, upper, voffset, right_row
        NumberedLabel.largest_number = max(NumberedLabel.largest_number, upper - 1)
        if not right_row:
            Label.needs_left_row = True

    def print_label(self, canvas):
        if self.upper - self.lower == 1:
            self.text = get_circled_number(self.lower, self.largest_number)
        elif self.upper - self.lower == 2:
            self.text = ", ".join(get_circled_number(number, self.largest_number)
                                   for number in range(self.lower, self.upper))
        else:
            self.text = "{0}–{1}".format(get_circled_number(self.lower, self.largest_number),
                                          get_circled_number(self.upper - 1, self.largest_number))
        super(NumberedLabel, self).print_label(canvas)


def place_labels(layers):
    """Finds the best places for all labels.  Additionally, move labels for
    which there is not enough free space to the legend.

    :Parameters:
      - `layers`: the layers to be drawn

    :type layers: list of `Layer`

    :Return:
      all labels, all labels intended to be displaced to the legend

    :rtype: list of `Label`, list of unicode
    """
    labels = []
    displaced_labels = []
    i = 0
    while i < len(layers):
        layer = layers[i]
        if layer.height >= layer.label_height:
            labels.append(Label(layer, right_row=True))
        else:
            j = i + 1
            collective_height = layer.height
            while j < len(layers) and layers[j].height < line_height:
                collective_height += layers[j].height
                j += 1
            if j - i == 1 and layer.one_liner:
                labels.append(Label(layer, right_row=j == len(layers)))
            else:
                current_delayed_number = len(displaced_labels) + 1
                right_row = collective_height >= line_height
                voffset = layers[j - 1].accumulated_height - collective_height / 2
                labels.append(
                    NumberedLabel(current_delayed_number, current_delayed_number + j - i, voffset, right_row))
                displaced_labels.extend(layer.name for layer in layers[i:j])
            i = j - 1
        i += 1
    return labels, displaced_labels


def build_legend(displaced_labels, width):
    """Creates the legend without actually drawing it.

    :Parameters:
      - `displaced_labels`: all labels intended to be displaced to the legend
      - `width`: the width of the printed legend

    :type displaced_labels: list of unicode
    :type width: float

    :Return:
      All items of the legend as ReportLab paragraphs, the height of the
      printed legend

    :rtype: list of `Paragraph`, float
    """
    style = LegendLabelStyle("legend")
    legend = []
    for i, label in enumerate(displaced_labels):
        number = i + 1
        legend.append(
            Paragraph("""<bullet>{0}</bullet>{1}""".format(get_circled_number(number, NumberedLabel.largest_number), label),
                      style))
    total_height = 0
    for item in legend:
        total_height += item.wrap(width, 100 * lineskip)[1]
    if legend:
        total_height += (len(legend) - 1) * 0.3 * lineskip
    return legend, total_height


def generate_diagram(filepath, layers, title, subject):
    """Generates the stack diagram and writes it to a PDF file.

    :Parameters:
      - `filepath`: the path to the PDF file that should be written
      - `layers`: the layers of the stack in chronological order
      - `title`: the title of the PDF file
      - `subject`: the subject of the PDF file

    :type filepath: str
    :type layers: list of `Layer`
    :type title: unicode
    :type subject: unicode
    """
    scale = Scale(layers)
    stack_height = build_stack(layers, scale)
    labels, displaced_labels = place_labels(layers)
    total_margin = dimensions["margin"]
    full_label_width = dimensions["label_skip"] + dimensions["label_width"]
    width = dimensions["stack_width"] + 2 * total_margin + full_label_width
    if Label.needs_left_row:
        width += full_label_width
    legend, legend_height = build_legend(displaced_labels, width)
    height = scale.scale_height + stack_height + legend_height + 2 * total_margin + dimensions["scale_skip"]
    if legend:
        height += dimensions["legend_skip"]
    verified = all(layer.verified for layer in layers)
    if not verified:
        red_line_space = dimensions["red_line_skip"] + dimensions["red_line_width"]
        width += 2 * red_line_space
        height += 2 * red_line_space
        total_margin += red_line_space

    c = canvas.Canvas(filepath, pagesize=(width, height), pageCompression=True)
    c.setAuthor("Chantal samples database")
    c.setTitle(title)
    c.setSubject(subject)
    c.setLineJoin(1)
    c.setLineCap(1)

    if not verified:
        red_line_position = dimensions["red_line_width"] / 2 + dimensions["red_line_skip"]
        c.saveState()
        c.setStrokeColor(getAllNamedColors()["red"])
        c.setLineWidth(dimensions["red_line_width"])
        c.rect(red_line_position, red_line_position, width - 2 * red_line_position, height - 2 * red_line_position)
        c.restoreState()
    c.translate(total_margin, total_margin)
    yoffset = 0
    for item in reversed(legend):
        item.drawOn(c, 0, yoffset)
        yoffset += item.height + 0.3 * lineskip
    if legend:
        c.translate(0, legend_height + dimensions["legend_skip"])
    for label in labels:
        label.print_label(c)
    c.saveState()
    if Label.needs_left_row:
        c.translate(full_label_width, 0)
    layers = [layer for layer in reversed(layers) if layer.nm >= 0]
    for i, layer in enumerate(layers):
        layer.draw(c)
    c.restoreState()
    c.translate(full_label_width if Label.needs_left_row else 0, stack_height + dimensions["scale_skip"])
    scale.draw(c)
    c.showPage()
    c.save()


if __name__ == "__main__":
    layers = [Layer("Glas", 2e3, "lightblue", textured=True),
              Layer("Eine <i>wirklich</i> <b>wunderschöne</b> <a href='http://www.fz-juelich.de'>αβγ</a>-Schicht", 1e2,
                    "red", textured=True, verified=True),
              Layer("i", decimal.Decimal("999"), "orange", structured=True, textured=True, thickness_reliable=True),
              Layer("s", -1, "blue", textured=True),
              Layer("s", -1, "blue", textured=True),
              Layer("s", -1, "blue", textured=True),
              Layer("HF", -1, "blue", textured=True),
              Layer("n", 2e2, "green", textured=True),
              ]
    layers = [Layer("Glas", decimal.Decimal("1.1e6"), "lightblue", thickness_reliable=True, verified=True),
              Layer("ZnO", decimal.Decimal("800"), "lightgrey", thickness_reliable=True, verified=True),
              Layer("n", decimal.Decimal("25"), "green", thickness_reliable=True, verified=True),
              Layer("i", decimal.Decimal("150"), "orange", thickness_reliable=True, verified=True),
              Layer("p", decimal.Decimal("80"), "red", thickness_reliable=True, verified=True),
              Layer("HF", decimal.Decimal("-1"), "blue", thickness_reliable=True, verified=True),
              Layer("ZnO", decimal.Decimal("120"), "lightgrey", thickness_reliable=True, verified=True, structured=True),
              Layer("Silber", decimal.Decimal("700"), "grey", thickness_reliable=True, verified=True, structured=True,
                    collapsed=True),
              ]
    generate_diagram("test.pdf", layers, "10-TB-testsample", "Layer stack of 10-TB-testsample")
