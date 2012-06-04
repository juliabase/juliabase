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

from __future__ import absolute_import, unicode_literals, division
import codecs, math
import numpy
from samples.views import shared_utils


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


def read_dsr_plot_file(filename, columns=(0, 1)):
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
    try:
        datafile = codecs.open(filename, encoding="cp1252")
    except IOError:
        raise shared_utils.PlotError("datafile could not be opened")
    for line_number, line in enumerate(datafile, start=1):
        if not line.startswith(";") and line_number != 1:
            start_line_number = line_number
            datafile.close()
            return shared_utils._read_plot_file_beginning_at_line_number(filename, columns, start_line_number)


def read_luma_file(filepath):
    """Read a luma datafile.  This ready only the dark IV curve and the Voc/Jsc
    values for different illuminations.  The latter are guaranteed to be sorted
    by increasing Voc.

    :Parameters:
      - `filepath`: full path to the solarsimulator measurement data file

    :type filepath: str

    :Return:
      voltages, currents of the dark curve, Vocs, Jscs

    :rtype: list of float, list of float, list of float, list of float

    :Exceptions:
      - `PlotError`: if something wents wrong with interpreting the file (I/O,
        unparseble data)
    """
    try:
        datafile = codecs.open(filepath, encoding="utf-8")
    except IOError:
        raise shared_utils.PlotError("datafile could not be opened")
    passed_empty_lines = 0
    dark_curve_u, dark_curve_j = [], []
    vocs, jscs = None, None
    for line in datafile:
        if line.strip() == "":
            passed_empty_lines += 1
        elif not line.startswith("#"):
            if passed_empty_lines == 2:
                j, u = line.split()[:2]
                u, j = float(u), float(j)
                dark_curve_u.append(u)
                dark_curve_j.append(j)
            elif passed_empty_lines == 4:
                if line.startswith("Voc/V"):
                    vocs = [float(voc) for voc in line.split()[1:]]
                elif line.startswith("Jsc/(mA/cm²)"):
                    jscs = [float(jsc) for jsc in line.split()[1:]]
    luma_points = sorted(zip(vocs, jscs))
    vocs, jscs = [], []
    for voc, jsc in luma_points:
        vocs.append(voc)
        jscs.append(jsc)
    return dark_curve_u, dark_curve_j, vocs, jscs


def evaluate_luma(dark_curve_u, dark_curve_j, vocs, jscs):
    """Calculate the series resistances and the ideality factor n from Luma
    measurements.  The actual series resistance is the limit of those values
    for U → ∞.

    :Parameters:
      - `dark_curve_u`: voltage values of the dark IV curve
      - `dark_curve_j`: current density values of the dark IV curve
      - `vocs`: Voc values for different filters in Luma, must be monotonically
        increasing
      - `jscs`: Jsc values for different filters in Luma

    :type dark_curve_u: list of float
    :type dark_curve_j: list of float
    :type vocs: list of float
    :type jscs: list of float

    :Return:
      the Rs values for every Voc value in `vocs`, in Ω·cm²; the voltages for
      the n curve, and the n values for these voltages

    :rtype: list of float, list of float, list_of_float
    """
    dark_curve_u, dark_curve_j = numpy.array(dark_curve_u), numpy.array(dark_curve_j)
    if not numpy.all(numpy.diff(dark_curve_j) > 0):
        raise shared_utils.PlotError("dark currents are not monotonically increasing")
    r_s = []
    for voc, jsc in zip(vocs, jscs):
        voltage_dark = numpy.interp(jsc, dark_curve_j, dark_curve_u, left=numpy.nan, right=numpy.nan)
        try:
            r_s.append((voltage_dark - voc) / jsc)
        except ZeroDivisionError:
            r_s.append(numpy.nan)
    voltages, n = [], []
    prefactor = 0.0258520283727  # kT/e in volts
    for i, voc in enumerate(vocs[:-1]):
        next_voc = vocs[i + 1]
        voltage = (voc + next_voc) / 2
        slope = (math.log(jscs[i + 1]) - math.log(jscs[i])) / (next_voc - voc)
        voltages.append(voltage)
        n.append(1 / (prefactor * slope))
    return r_s, voltages, n
