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

from __future__ import unicode_literals

import sys, os, datetime, glob, random
import numpy
import scipy.interpolate, scipy.optimize
sys.path.append(os.path.abspath(".."))
from jb_remote_institute import *


def evaluate_raw_data(voltages, current_curves, areas):

    def smooth(y, window_len=5):
        s = numpy.r_[2*y[0] - y[window_len:1:-1], y, 2*y[-1] - y[-1:-window_len:-1]]
        w = numpy.hanning(window_len)
        y_smooth = numpy.convolve(w / w.sum(), s, mode="same")
        return y_smooth[window_len-1:-window_len+1]

    evaluated_data = []
    for currents, area in zip(current_curves, areas):
        currents = smooth(currents) / float(area)
        data = {}
        data["isc"] = - numpy.interp(0, voltages, currents) * 1000
        interpolated_current = scipy.interpolate.interp1d(voltages, currents)
        def current(voltage):
            if voltage < voltages[0]:
                return currents[0]
            elif voltage > voltages[-1]:
                return currents[-1]
            else:
                return interpolated_current(voltage)
        power_max = - scipy.optimize.fmin(lambda voltage: voltage * current(voltage), 0.1, full_output=True, disp=False)[1]
        data["eta"] = power_max * 1000
        evaluated_data.append(data)
    return evaluated_data
        
    
def read_solarsimulator_file(filepath):
    header_data = {}
    for line in open(filepath):
        if line.startswith("# -"):
            break
        else:
            key, __, value = line[1:].partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "timestamp":
                header_data[key] = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            else:
                header_data[key] = value
    data = numpy.loadtxt(filepath, unpack=True)
    voltages, current_curves = data[0], data[1:]
    return header_data, evaluate_raw_data(voltages, current_curves, [float(area) for area in header_data["areas"].split()])


setup_logging("console")
login("juliabase", "12345")

for filepath in glob.glob("solarsimulator_raw_data/measurement-*.dat"):
    header_data, evaluated_data = read_solarsimulator_file(filepath)
    try:
        sample_id = get_sample(header_data["sample"])
    except SampleNotFound as exception:
        sample = exception.sample
        sample.currently_responsible_person = header_data["operator"]
        sample.current_location = "Solar simulator lab"
        sample.topic = "Legacy"
        sample_id = sample.submit()

        substrate = Substrate()
        substrate.timestamp = header_data["timestamp"] - datetime.timedelta(minutes=2)
        substrate.timestamp_inaccuracy = 3
        substrate.sample_ids = [sample_id]
        substrate.material = "corning"
        substrate.operator = header_data["operator"]
        substrate.submit()

    structuring = Structuring()
    structuring.sample_id = sample_id
    structuring.timestamp = header_data["timestamp"] - datetime.timedelta(minutes=1)
    structuring.operator = header_data["operator"]
    structuring.layout = header_data["layout"]
    structuring.submit()
    
    measurement = SolarsimulatorMeasurement()
    measurement.operator = header_data["operator"]
    measurement.timestamp = header_data["timestamp"]
    measurement.sample_id = sample_id
    measurement.irradiance = header_data["irradiance"]
    measurement.temperature = header_data["temperature"]

    for position, area, data in zip(header_data["positions"].split(), header_data["areas"].split(), evaluated_data):
        cell = SolarsimulatorCellMeasurement(measurement, position)
        cell.area = area
        cell.isc = data["isc"]
        cell.eta = data["eta"]
        cell.data_file = os.path.relpath(filepath, "solarsimulator_raw_data")
    
    measurement.submit()

logout()
