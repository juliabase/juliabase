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

from __future__ import absolute_import, unicode_literals, division

import re, string, codecs, os, os.path


def int_or_zero(number):
    """Converts ``number`` to an integer.  If this doesn't work, return ``0``.

    :param number: a string that is supposed to contain an integer number

    :type number: str or unicode or NoneType

    :return:
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

    :param name: the camel-cased identifier

    :type name: str

    :return:
      the identifier in underscore notation

    :rtype: str
    """
    result = []
    for i, character in enumerate(name):
        if i == 0:
            result.append(character.lower())
        elif character in string.ascii_uppercase and (i+1 < len(name) and name[i+1] not in string.ascii_uppercase):
            result.extend(("_", character.lower()))
        else:
            result.append(character.lower())
    return "".join(result)


class PlotError(Exception):
    """Raised if an error occurs while generating a plot.  Usually, it is raised in
    :py:meth:`samples.models.Process.draw_plot` and caught in
    :py:func:`samples.views.plots.show_plot`.
    """
    pass


def read_techplot_file(filename, columns=(0, 1)):
    """Read a datafile in TechPlot format and return the content of selected
    columns.

    :param filename: full path to the Techplot data file
    :param columns: the columns that should be read.  Defaults to the first two,
        i.e., ``(0, 1)``.  Note that the column numbering starts with zero.

    :type filename: str
    :type columns: list of int

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
        raise PlotError("Datafile “{0}” could not be opened.".format(os.path.basename(filename)))
    result = [[] for i in range(len(columns))]
    for line in datafile:
        if start_values:
            if line.lower().startswith("end"):
                break
            cells = line.split()
            for column, result_array in zip(columns, result):
                try:
                    value = float(cells[column])
                except IndexError:
                    raise PlotError("Datafile “{0}” contained too few columns.".format(os.path.basename(filename)))
                except ValueError:
                    value = float("nan")
                result_array.append(value)
        elif line.lower().startswith("begin"):
            start_values = True
    datafile.close()
    return result


def mkdirs(path):
    """Creates a directory and all of its parents if necessary.  If the given
    path doesn't end with a slash, it's interpreted as a filename and removed.
    If the directory already exists, nothing is done.  (In particular, no
    exception is raised.)

    :param path: absolute path which should be created

    :type path: str
    """
    try:
        os.makedirs(os.path.dirname(path))
    except OSError:
        pass


def capitalize_first_letter(text):
    """Capitalise the first letter of the given string.

    :param text: text whose first letter should be capitalised

    :type text: unicode

    :return:
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

    :param text: the original string

    :type text: unicode

    :return:
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


def python_escape(text):
    """Escapes a string so that it can be used as a Python string literal.
    For example, it replaces all ``"`` with ``\\"``.

    :param text: the original string

    :type text: unicode

    :return:
      the Python-ready string

    :rtype: unicode
    """
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
