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

import datetime, re
from samples.views import shared_utils
from samples import models


def read_solarsimulator_plot_file(filename, columns=(0, 1)):
    """Read a datafile from a solarsimulator measurement and return the content of selected
    columns.

    :Parameters:
      - `filename`: full path to the solarsimulator measurement data file
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
    return shared_utils._read_plot_file_beginning_after_start_value(filename, columns, start_value=";U/V", separator=",")


deposition_index_pattern = re.compile(r"\d{3,4}")

def get_next_deposition_number(letter):
    """Find a good next deposition number.  For example, if the last run was
    called “08B-045”, this routine yields “08B-046” (unless the new year has
    begun).

    :Parameters:
      - `letter`: the indentifying letter of the deposition apparatus.  For
        example, it is ``"B"`` for the 6-chamber deposition.

    :type letter: str

    :Return:
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
    """This function works like the `get_next_deposition_number` from `samples.utils`,
    but it also searches throught a given process that is using the same pool of
    numbers such as the deposition.

    For example see the FiveChamberDeposition and the FiveChamberEtching.
    There are two different processes that are made on the same apparatus and
    therefore have the same numbers.

    :Parameters:
      - `letter`: the indentifying letter of the deposition apparatus.  For
        example, it is ``"B"`` for the 6-chamber deposition.
      - `process_cls`: the model class from the process who has the same
      type of numbers such as the deposition.

    :type letter: str
    :type process_cls: `samples.models.PhysicalProcess`

    :Return:
      A so-far unused deposition number for the current calendar year for the
      given deposition apparatus.
    """
    prefix = "{year}{letter}-".format(year=datetime.date.today().strftime("%y"), letter=letter)
    numbers = map(int, map(lambda string: string[len(prefix):],
                           set(models.Deposition.objects.filter(number__startswith=prefix).values_list('number', flat=True).iterator()) |
                           set(process_cls.objects.filter(number__startswith=prefix).values_list('number', flat=True).iterator())))
    next_number = max(numbers) + 1 if numbers else 1
    return prefix + "{0:03}".format(next_number)


quirky_sample_name_pattern = re.compile(r"(?P<year>\d\d)(?P<letter>[BVHLCSbvhlcs])-?(?P<number>\d{1,4})"
                                        r"(?P<suffix>[-A-Za-z_/][-A-Za-z_/0-9]*)?$")
def normalize_legacy_sample_name(sample_name):
    """Convert an old, probably not totally correct sample name to a valid
    sample name.  For example, a missing dash after the deposition letter is
    added, and the deposition letter is converted to uppercase.

    :Parameters:
      - `sample_name`: the original quirky name of the sample

    :type sample_name: unicode

    :Return:
      the corrected sample name

    :rtype: unicode

    :Exceptions:
      - `ValueError`: if the sample name was broken beyond repair.
    """
    match = quirky_sample_name_pattern.match(sample_name)
    if not match:
        raise ValueError("Sample name is too quirky to normalize")
    parts = match.groupdict("")
    parts["number"] = int(parts["number"])
    parts["letter"] = parts["letter"].upper()
    return "{year}{letter}-{number:03}{suffix}".format(**parts)
