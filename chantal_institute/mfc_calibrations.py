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

"""This module contains the classes for using the calibration factors of the
mass flow controllers.
"""

from __future__ import absolute_import, unicode_literals
from numpy import exp
import codecs
import re
from datetime import date

mfc_calibration_cls = {}

date_pattern = re.compile(r"#?(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{2,4})")
def parse_date(datestring):
    """Converts a date string into a ``datetime.date`` object.

    :Parameter:
     - `datestring`: the date string in the format ``DD.MM.YY(YY)``.

    :type datestring: unicode

    :Return:
     a python specific date object

    :rtype: datetime.date
    """
    match = date_pattern.match(datestring)
    year = int(match.group("year"))
    if year < 100:
        year = 1900 + year if year > 40 else 2000 + year
    return date(year, int(match.group("month")), int(match.group("day")))

def open_data_file(filepath):
    """This method tries to open the file with the windows or dos encoding.
    If it fails, it opens the file with the default builtin ``open()`` method.

    :Parameter:
     - `filepath`: the name and the path to the file

    :type filepath: str

    :Return:
     a filehandle object representing the file

    :rtype: file
    """
    try:
        file = codecs.open(filepath, encoding="cp1252")
    except UnicodeDecodeError:
        try:
            file = codecs.open(filepath, encoding="cp437")
        except UnicodeDecodeError:
            file = open(filepath)
    return file

def get_calibrations_from_datafile(filepath, apparatus):
    """This method reads the mass flow controller calibration values
    from the data file and returns them as a list of calibration objects.
    The calibration class is chosen by the name of the related apparatus.

    :Parameters:
     - `filepath`: the path to the calibration data file
     - `apparatus`: the name of the apparatus

    :type filepath: str
    :type apparatus: str

    :Return:
     a list consisting the calibration data objects

    :rtype: list
    """
    calibrations = []
    for line in open_data_file(filepath):
        line = line.strip()
        if not line:
            continue
        if line.startswith("["):
            calibrations.append(mfc_calibration_cls[apparatus](parse_date(line.strip("[]"))))
        else:
            mfc_name, calibration_factors = line.split(":")
            calibrations[-1].mfc_factors[mfc_name.lower()] = calibration_factors.split()
    return calibrations


class MFCCalibrations(object):
    """The common class for all mfc calibration classes.
    It should be derived by all other calibration classes.
    """
    def __init__(self, date):
        self.date = date

    def __cmp__(self, other):
        if self.date < other.date:
            return -1
        elif self.date == other.date:
            return 0
        elif self.date > other.date:
            return 1

    def __eq__(self, other):
        return self.date == other.date

    def __ge__(self, other):
        return self.date >= other.date

    def __gt__(self, other):
        return self.date > other.date

    def __le__(self, other):
        return self.date <= other.date

    def __lt__(self, other):
        return self.date < other.date


class LADACalibration(MFCCalibrations):
    """The class to calibrate the mfc's for the LADA Deposition
    apparatus.

    To use this class for the calibration values, pass `apparatus=lada`
    to the get_calibrations_from_datafile() method.

    See `views.samples.lada_depositions.calculate_silane_concentration` for
    usage.
    """
    def __init__(self, date):
        super(LADACalibration, self).__init__(date)
        self.mfc_factors = {}

    def get_real_flow(self, gas_flow, mfc_name):
        gas_flow = float(gas_flow)
        try:
            factors = self.mfc_factors[mfc_name]
        except KeyError:
            factors = [1, 1]
        if len(factors) == 2:
            factors.extend((0, 0))
        elif len(factors) == 1:
            factors.extend((0, 0, 0))
        gasfactor, value_a, value_b, value_c = map(float, factors)
        return (value_a + value_b * exp(value_c * gas_flow)) * gas_flow * gasfactor

mfc_calibration_cls["lada"] = LADACalibration
