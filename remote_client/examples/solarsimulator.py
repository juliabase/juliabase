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
sys.path.append(os.path.abspath(".."))
from jb_remote_institute import *


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
    return header_data

        
login("juliabase", "12345")

for filepath in glob.glob("solarsimulator_raw_data/measurement-*.dat"):
    header_data = read_solarsimulator_file(filepath)
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

    for position in header_data["positions"].split():
        cell = SolarsimulatorCellMeasurement(measurement, position)
        cell.area = 1
        cell.eta = random.random() * 14
        cell.data_file = os.path.relpath(filepath, "solarsimulator_raw_data")
    
    measurement.submit()

logout()
