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

import sys, os, datetime, random
sys.path.append(os.path.abspath(".."))
from jb_remote_inm import *


random.seed(8765432)
setup_logging("console")
login("juliabase", "12345")

def create_depo(timestamp, deposition_number, sample_name, comments=None):
    try:
        sample_id = get_sample(sample_name)
    except SampleNotFound as exception:
        sample = exception.sample
        sample.currently_responsible_person = "j.silverton"
        sample.current_location = "Juliette's office"
        sample.topic = "Juliette's PhD thesis"
        sample_id = sample.submit()

        substrate = Substrate()
        substrate.timestamp = timestamp - datetime.timedelta(minutes=1)
        substrate.timestamp_inaccuracy = 3
        substrate.sample_ids = [sample_id]
        substrate.material = "corning"
        substrate.operator = "e.monroe"
        substrate.submit()
    else:
        sample = Sample(id_=sample_id)
    sample.add_to_my_samples("j.silverton")

    deposition = ClusterToolDeposition()
    deposition.number = deposition_number
    deposition.sample_ids = [sample_id]
    deposition.operator = "e.monroe"
    deposition.timestamp = timestamp
    deposition.comments = comments

    layer = ClusterToolHotWireLayer(deposition)
    layer.time = "00:10:00"
    layer.base_pressure = int(random.uniform(2, 100)) / 10
    layer.wire_material = "rhenium"
    layer.sih4 = int(random.uniform(0, 5))
    layer.h2 = int(random.uniform(0, 2))
    layer.comments = "p-type layer"

    layer = ClusterToolPECVDLayer(deposition)
    layer.time = "00:55:00"
    layer.sih4 = int(random.uniform(0, 4))
    layer.h2 = int(random.uniform(0, 1))
    layer.chamber = "#3"
    layer.comments = "i-type layer"

    layer = ClusterToolHotWireLayer(deposition)
    layer.time = "00:10:00"
    layer.base_pressure = int(random.uniform(2, 100)) / 10
    layer.wire_material = "rhenium"
    layer.sih4 = int(random.uniform(0, 10))
    layer.h2 = int(random.uniform(0, 12))
    layer.comments = "n-type layer"

    deposition.submit()

create_depo(datetime.datetime(2014, 10, 1, 10, 30), "14C-001", "14-JS-1")
create_depo(datetime.datetime(2014, 10, 2, 11, 10), "14C-002", "14-JS-2")
create_depo(datetime.datetime(2014, 10, 2, 12, 10), "14C-003", "14-JS-3")
create_depo(datetime.datetime(2014, 10, 2, 13, 10), "14C-004", "14-JS-4")
create_depo(datetime.datetime(2014, 10, 2, 14, 10), "14C-005", "14-JS-5")
create_depo(datetime.datetime(2014, 10, 2, 15, 10), "14C-006", "14-JS-6")

logout()
