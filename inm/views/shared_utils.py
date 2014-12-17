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
from django.utils.six.moves import cStringIO as StringIO

import datetime, re
import numpy
from samples.views import shared_utils
from samples import models


def read_solarsimulator_plot_file(filename, position):
    """Read a datafile from a solarsimulator measurement and return the content of
    the voltage column and the selected current column.

    :param filename: full path to the solarsimulator measurement data file
    :param position: the position of the cell the currents of which should be read.

    :type filename: str
    :type position: str

    :return:
      all voltages in Volt, then all currents in Ampere

    :rtype: list of float, list of float

    :raises PlotError: if something wents wrong with interpreting the file (I/O,
        unparseble data)
    """
    try:
        datafile_content = StringIO(open(filename).read())
    except IOError:
        raise shared_utils.PlotError("Data file could not be read.")
    for line in datafile_content:
        if line.startswith("# Positions:"):
            positions = line.partition(":")[2].split()
            break
    else:
        positions = []
    try:
        column = positions.index(position) + 1
    except ValueError:
        raise shared_utils.PlotError("Cell position not found in the datafile.")
    datafile_content.seek(0)
    try:
        return numpy.loadtxt(datafile_content, usecols=(0, column), unpack=True)
    except ValueError:
        raise shared_utils.PlotError("Data file format was invalid.")


deposition_index_pattern = re.compile(r"\d{3,4}")

def get_next_deposition_number(letter):
    """Find a good next deposition number.  For example, if the last run was
    called “08B-045”, this routine yields “08B-046” (unless the new year has
    begun).

    :param letter: the indentifying letter of the deposition apparatus.  For
        example, it is ``"B"`` for the 6-chamber deposition.

    :type letter: str

    :return:
      A so-far unused deposition number for the current calendar year for the
      given deposition apparatus.
    """
    prefix = r"{0}{1}-".format(datetime.date.today().strftime("%y"), letter)
    prefix_length = len(prefix)
    pattern_string = r"^{0}[0-9]+".format(re.escape(prefix))
    deposition_numbers = \
        models.Deposition.objects.filter(number__regex=pattern_string).values_list("number", flat=True).iterator()
    numbers = [int(deposition_index_pattern.match(deposition_number[prefix_length:]).group())
               for deposition_number in deposition_numbers]
    next_number = max(numbers) + 1 if numbers else 1
    return prefix + "{0:03}".format(next_number)


def get_next_deposition_or_process_number(letter, process_cls):
    """This function works like the `get_next_deposition_number` from
    `samples.utils`, but it also searches throught a given process that is
    using the same pool of numbers such as the deposition.

    For example see the FiveChamberDeposition and the FiveChamberEtching.
    There are two different processes that are made on the same apparatus and
    therefore have the same numbers.

    :param letter: the indentifying letter of the deposition apparatus.  For
        example, it is ``"B"`` for the 6-chamber deposition.
    :param process_cls: the model class from the process who has the same
      type of numbers such as the deposition.

    :type letter: str
    :type process_cls: `samples.models.PhysicalProcess`

    :return:
      A so-far unused deposition number for the current calendar year for the
      given deposition apparatus.
    """
    prefix = "{year}{letter}-".format(year=datetime.date.today().strftime("%y"), letter=letter)
    numbers = map(int, map(lambda string: string[len(prefix):],
                           set(models.Deposition.objects.filter(number__startswith=prefix).values_list('number', flat=True). \
                               iterator()) |
                           set(process_cls.objects.filter(number__startswith=prefix).values_list('number', flat=True). \
                               iterator())))
    next_number = max(numbers) + 1 if numbers else 1
    return prefix + "{0:03}".format(next_number)
