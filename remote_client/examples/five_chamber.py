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

def create_depo(timestamp, deposition_number, comments=None):
    sample_name = deposition_number
    try:
        sample_id = get_sample(sample_name)
    except SampleNotFound as exception:
        sample = exception.sample
        sample.currently_responsible_person = "r.calvert"
        sample.current_location = "Rosalee's office"
        sample.topic = "Cooperation with Paris University"
        sample_id = sample.submit()

        substrate = Substrate()
        substrate.timestamp = timestamp - datetime.timedelta(minutes=1)
        substrate.timestamp_inaccuracy = 3
        substrate.sample_ids = [sample_id]
        substrate.material = "corning"
        substrate.operator = "r.calvert"
        substrate.submit()
    else:
        sample = Sample(id_=sample_id)
    sample.add_to_my_samples("r.calvert")

    deposition = FiveChamberDeposition()
    deposition.number = deposition_number
    deposition.sample_ids = [sample_id]
    deposition.operator = "r.calvert"
    deposition.timestamp = timestamp
    deposition.comments = comments

    layer = FiveChamberLayer(deposition)
    layer.temperature_1 = int(random.uniform(150, 160))
    layer.temperature_2 = int(random.uniform(150, 180))
    layer.sih4 = int(random.uniform(0, 5))
    layer.h2 = int(random.uniform(0, 2))
    layer.chamber = "p"
    layer.layer_type = "p"

    layer = FiveChamberLayer(deposition)
    layer.temperature_1 = int(random.uniform(100, 160))
    layer.temperature_2 = int(random.uniform(170, 180))
    layer.sih4 = int(random.uniform(0, 4))
    layer.h2 = int(random.uniform(0, 1))
    layer.chamber = "i2"
    layer.layer_type = "i"

    layer = FiveChamberLayer(deposition)
    layer.temperature_1 = int(random.uniform(130, 150))
    layer.temperature_2 = int(random.uniform(155, 160))
    layer.sih4 = int(random.uniform(0, 10))
    layer.h2 = int(random.uniform(0, 12))
    layer.chamber = "n"
    layer.layer_type = "n"

    deposition.submit()

create_depo(datetime.datetime(2014, 10, 1, 10, 30), "14S-001")
create_depo(datetime.datetime(2014, 10, 2, 11, 10), "14S-002")
create_depo(datetime.datetime(2014, 10, 2, 12, 10), "14S-003","AFTER: chamber cleaned!")
create_depo(datetime.datetime(2014, 10, 2, 13, 10), "14S-004")
create_depo(datetime.datetime(2014, 10, 2, 14, 10), "14S-005")
create_depo(datetime.datetime(2014, 10, 2, 15, 10), "14S-006")

logout()
