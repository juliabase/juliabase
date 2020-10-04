# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.



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
