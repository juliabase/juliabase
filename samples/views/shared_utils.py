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


"""General helper functions.  This is for low-level stuff.  Never import other
JuliaBase modules here, and avoid using Django, too.  The reason is that I'd
like to avoid cyclic imports, and I'd like to avoid being forced to ship the
whole of Django with the Remove Client (which uses this module).

Note that all names defined here are also available in `utils`, so this module
is really only interesting for the Remote Client.

Important: A *copy* of this module is bundled with the remote client, which is
part of the institute-specific package.  So synchronise it now and then with
its copy there.
"""

from __future__ import absolute_import, unicode_literals

import re, string, codecs, os, os.path


def int_or_zero(number):
    """Converts ``number`` to an integer.  If this doesn't work, return ``0``.

    :Parameters:
      - `number`: a string that is supposed to contain an integer number

    :type number: str or unicode or ``NoneType``

    :Return:
      the ``int`` representation of ``number``, or 0 if it didn't represent a
      valid integer number

    :rtype: int
    """
    try:
        return int(number)
    except (ValueError, TypeError):
        return 0


def camel_case_to_underscores(name):
    """Converts a CamelCase identifier to one using underscores.  For example,
    ``"MySamples"`` is converted to ``"my_samples"``, and ``"PDSMeasurement"``
    to ``"pds_measurement"``.

    :Parameters:
      - `name`: the camel-cased identifier

    :type name: str

    :Return:
      the identifier in underscore notation

    :rtype: str
    """
    result = []
    for i, character in enumerate(name):
        if i > 0 and character in string.ascii_uppercase + string.digits and (
            (i + 1 < len(name) and name[i + 1] not in string.ascii_uppercase + string.digits) or
            (name[i - 1] not in string.ascii_uppercase + string.digits)):
            result.append("_")
        result.append(character.lower())
    return "".join(result)


def camel_case_to_human_text(name):
    """Converts a CamelCase identifier to one intended to be read by humans.
    For example, ``"MySamples"`` is converted to ``"my samples"``, and
    ``"PDSMeasurement"`` to ``"PDS measurement"``.

    :Parameters:
      - `name`: the camel-cased identifier

    :type name: str

    :Return:
      the pretty-printed identifier

    :rtype: str
    """
    result = []
    for i, character in enumerate(name):
        if i > 0 and character in string.ascii_uppercase and (
            (i + 1 < len(name) and name[i + 1] not in string.ascii_uppercase) or
            (name[i - 1] not in string.ascii_uppercase)):
            result.append(" ")
        result.append(character if i + 1 >= len(name) or name[i + 1] in string.ascii_uppercase else character.lower())
    return "".join(result)


class PlotError(Exception):
    """Raised if an error occurs while generating a plot.  Usually, it is
    raised in `Process.pylab_commands` and caught in `Process.generate_plot`.
    """
    pass


def _read_plot_file_beginning_at_line_number(filename, columns, start_line_number, end_line_number=None, separator=None):
    """Read a datafile and returns the content of selected columns beginning at start_line_number.
    You shouldn't use this function directly. Use the specific functions instead.

    :Parameters:
      - `filename`: full path to the data file
      - `columns`: the columns that should be read.
      - `start_line_number`: the line number where the data starts
      - `end_line_number`: the line number where the record should end.
         The default is ``None``, means till end of file.
      - `separator`: the separator which separates the values from each other.
        Default is ``None``

    :type filename: str
    :type columns: list of int
    :type start_line_number: int
    :type end_line_number: int or None
    :type separator: str or None

    :Return:
      List of all columns.  Every column is represented as a list of floating
      point values.

    :rtype: list of list of float

    :Exceptions:
      - `PlotError`: if something wents wrong with interpreting the file (I/O,
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


def _read_plot_file_beginning_after_start_value(filename, columns, start_value, end_value="", separator=None):
    """Read a datafile and return the content of selected columns after the start_value was detected.
    You shouldn't use this function directly. Use the specific functions instead.

    :Parameters:
      - `filename`: full path to the data file
      - `columns`: the columns that should be read.
      - `start_value`: the start_value indicates the line after the data should be read
      - `end_value`: the end_value marks the line where the record should end.
         The default is the empty string
      - `separator`: the separator which separates the values from each other.
        Default is ``None``

    :type filename: str
    :type columns: list of int
    :type start_value: str
    :type end_value: str
    :type separator: str or None

    :Return:
      List of all columns.  Every column is represented as a list of floating
      point values.

    :rtype: list of list of float

    :Exceptions:
      - `PlotError`: if something wents wrong with interpreting the file (I/O,
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
                    value = float(cells[column])
                except IndexError:
                    raise PlotError("datafile contained too few columns")
                except ValueError:
                    value = float("nan")
                result_array.append(value)
        elif line.lower().startswith(start_value.lower()):
            start_values = True
    datafile.close()
    return result


def read_techplot_file(filename, columns=(0, 1)):
    """Read a datafile in TechPlot format and return the content of selected
    columns.

    :Parameters:
      - `filename`: full path to the Techplot data file
      - `columns`: the columns that should be read.  Defaults to the first two,
        i.e., ``(0, 1)``.  Note that the column numbering starts with zero.

    :type filename: str
    :type columns: list of int

    :Return:
      List of all columns.  Every column is represented as a list of floating
      point values.

    :rtype: list of list of float

    :Exceptions:
      - `PlotError`: if something wents wrong with interpreting the file (I/O,
        unparseble data)
    """
    return _read_plot_file_beginning_after_start_value(filename, columns, start_value="begin", end_value="end")


def mkdirs(path):
    """Creates a directory and all of its parents if necessary.  If the given
    path doesn't end with a slash, it's interpreted as a filename and removed.
    If the directory already exists, nothing is done.  (In particular, no
    exception is raised.)

    :Parameters:
      - `path`: absolute path which should be created

    :type path: str
    """
    try:
        os.makedirs(os.path.dirname(path))
    except OSError:
        pass


def remove_file(path):
    """Removes the file.  If the file didn't exist, this is a no-op.

    :Parameters:
      - `path`: absolute path to the file to be removed

    :type path: str

    :Return:
      whether the file was removed; if ``False``, it hadn't existed

    :rtype: bool
    """
    try:
        os.remove(path)
    except OSError:
        return False
    else:
        return True


def capitalize_first_letter(text):
    """Capitalise the first letter of the given string.

    :Parameters:
      - `text`: text whose first letter should be capitalised

    :type text: unicode

    :Return:
      the text with capitalised first letter

    :rtype: unicode
    """
    if text:
        return text[0].upper() + text[1:]
    else:
        return ""


def sanitize_for_markdown(text):
    """Convert a raw string to Markdown syntax.  This is used when external
    (legacy) strings are imported.  For example, comments found in data files
    must be sent through this function before being stored in the database.

    :Parameters:
      - `text`: the original string

    :type text: unicode

    :Return:
      the Markdown-ready string

    :rtype: unicode
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("_", "\\_").replace("*", "\\*").replace("`", "\\`"). \
        replace("\n#", "\n\\#").replace("\n>", "\n\\>").replace("\n+", "\n\\+").replace("\n-", "\n\\-")
    if text.startswith(tuple("#>+-")):
        text = "\\" + text
    # FixMe: Add ``flags=re.UNICODE`` with Python 2.7+
    paragraphs = re.split(r"\n\s*\n", text)
    for i, paragraph in enumerate(paragraphs):
        lines = paragraph.split("\n")
        for j, line in enumerate(lines):
            if len(line) < 70:
                lines[j] += "  "
        paragraphs[i] = "\n".join(lines)
    return "\n\n".join(paragraphs) + "\n"
