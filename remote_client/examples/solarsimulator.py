#!/usr/bin/env python
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

import sys, os; sys.path.append(os.path.abspath(".."))

import os, datetime, glob, urllib
import numpy
import scipy.interpolate, scipy.optimize
from jb_remote_inm import *


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

for filepath in sorted(glob.glob("solarsimulator_raw_data/measurement-*.dat")):
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

    structuring = connection.open("structurings/by_sample/{0}?timestamp={1}".format(
        urllib.parse.quote_plus(str(sample_id)),
        urllib.parse.quote_plus(str(header_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")))))
    if not structuring:
        structuring = Structuring()
        structuring.sample_id = sample_id
        structuring.timestamp = header_data["timestamp"] - datetime.timedelta(minutes=1)
        structuring.operator = header_data["operator"]
        structuring.layout = header_data["layout"]
        structuring.submit()
    
    measurement = SolarsimulatorMeasurement()
    measurement.operator = header_data["operator"]
    measurement.timestamp = header_data["timestamp"]
    measurement.comments = header_data["comments"]
    measurement.sample_id = sample_id
    measurement.irradiation = header_data["irradiation"]
    measurement.temperature = header_data["temperature"]

    for position, area, data in zip(header_data["positions"].split(), header_data["areas"].split(), evaluated_data):
        cell = SolarsimulatorCellMeasurement(measurement, position)
        cell.area = area
        cell.isc = data["isc"]
        cell.eta = data["eta"]
        cell.data_file = os.path.relpath(filepath, "solarsimulator_raw_data")
    
    measurement.submit()

logout()
