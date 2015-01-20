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

import sys, os, datetime, glob
sys.path.append(os.path.abspath(".."))
from jb_remote_inm import *


def read_pds_file(filepath):
    result = {}
    for line in open(filepath):
        if line.startswith("# -"):
            break
        key, __, value = line[1:].partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "timestamp":
            result[key] = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        else:
            result[key] = value
    return result

        
setup_logging("console")
login("juliabase", "12345")

for filepath in sorted(glob.glob("pds_raw_data/*.dat")):
    pds_header_data = read_pds_file(filepath)
    try:
        sample_id = get_sample(pds_header_data["sample"])
    except SampleNotFound as exception:
        sample = exception.sample
        sample.currently_responsible_person = pds_header_data["operator"]
        sample.current_location = "PDS lab"
        sample.topic = "Legacy"
        sample_id = sample.submit()

        substrate = Substrate()
        substrate.timestamp = pds_header_data["timestamp"] - datetime.timedelta(minutes=1)
        substrate.timestamp_inaccuracy = 3
        substrate.sample_ids = [sample_id]
        substrate.material = "corning"
        substrate.operator = "n.burkhardt"
        substrate.submit()
    pds_measurement = PDSMeasurement()
    pds_measurement.operator = pds_header_data["operator"]
    pds_measurement.timestamp = pds_header_data["timestamp"]
    pds_measurement.number = pds_header_data["number"]
    pds_measurement.apparatus = "pds" + pds_header_data["apparatus"]
    pds_measurement.raw_datafile = os.path.basename(filepath)
    pds_measurement.sample_id = sample_id
    pds_measurement.submit()

logout()
