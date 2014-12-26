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


from __future__ import absolute_import, unicode_literals, division

import codecs


class PlotError(Exception):
    """Raised if an error occurs while generating a plot.  Usually, it is raised in
    :py:meth:`samples.models.Process.draw_plot` and caught in
    :py:func:`samples.views.plots.show_plot`.
    """
    pass


def read_plot_file_beginning_at_line_number(filename, columns, start_line_number, end_line_number=None, separator=None):
    """Read a datafile and returns the content of selected columns beginning at
    start_line_number.  You shouldn't use this function directly. Use the
    specific functions instead.

    :param filename: full path to the data file
    :param columns: the columns that should be read.
    :param start_line_number: the line number where the data starts
    :param end_line_number: the line number where the record should end.
         The default is ``None``, means till end of file.
    :param separator: the separator which separates the values from each other.
        Default is ``None``

    :type filename: str
    :type columns: list of int
    :type start_line_number: int
    :type end_line_number: int or None
    :type separator: str or None

    :return:
      List of all columns.  Every column is represented as a list of floating
      point values.

    :rtype: list of list of float

    :raises PlotError: if something wents wrong with interpreting the file (I/O,
        unparseble data)
    """
    start_values = False
    try:
        datafile = codecs.open(filename, encoding="cp1252")
    except IOError:
        raise PlotError("datafile could not be opened")
    result = [[] for i in range(len(columns))]
    for line_number, line in enumerate(datafile, start=1):
        if start_values:
            if end_line_number and line_number > end_line_number:
                break
            if not line.strip():
                continue
            cells = line.strip().split(separator)
            for column, result_array in zip(columns, result):
                try:
                    value = float(cells[column].replace(",", "."))
                except IndexError:
                    raise PlotError("datafile contained too few columns")
                except ValueError:
                    value = float("nan")
                result_array.append(value)
        elif line_number == start_line_number - 1:
            start_values = True
    datafile.close()
    return result


def read_plot_file_beginning_after_start_value(filename, columns, start_value, end_value="", separator=None):
    """Read a datafile and return the content of selected columns after the
    start_value was detected.  You shouldn't use this function directly. Use
    the specific functions instead.

    :param filename: full path to the data file
    :param columns: the columns that should be read.
    :param start_value: the start_value indicates the line after the data
        should be read
    :param end_value: the end_value marks the line where the record should
        end.  The default is the empty string
    :param separator: the separator which separates the values from each
        other.  Default is ``None``

    :type filename: str
    :type columns: list of int
    :type start_value: str
    :type end_value: str
    :type separator: str or None

    :return:
      List of all columns.  Every column is represented as a list of floating
      point values.

    :rtype: list of list of float

    :raises PlotError: if something wents wrong with interpreting the file (I/O,
        unparseble data)
    """
    start_values = False
    try:
        datafile = codecs.open(filename, encoding="cp1252")
    except IOError:
        raise PlotError("datafile could not be opened")
    result = [[] for i in range(len(columns))]
    for line in datafile:
        if start_values:
            if end_value and line.lower().startswith(end_value):
                break
            if not line.strip():
                continue
            cells = line.strip().split(separator)
            for column, result_array in zip(columns, result):
                try:
                    value = float(cells[column].replace(",", "."))
                except IndexError:
                    raise PlotError("datafile contained too few columns")
                except ValueError:
                    value = float("nan")
                result_array.append(value)
        elif line.lower().startswith(start_value.lower()):
            start_values = True
    datafile.close()
    return result
