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
