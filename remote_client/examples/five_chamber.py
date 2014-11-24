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

import sys, os, datetime, random
sys.path.append(os.path.abspath(".."))
from jb_remote_institute import *


setup_logging("console")
login("juliabase", "12345")

def create_depo(timestamp, sample_name, comments=None):
    try:
        sample_id = get_sample(sample_name)
    except SampleNotFound as exception:
        sample = exception.sample
        sample.currently_responsible_person = "r.calvert"
        sample.current_location = "Rosalee's office"
        sample.topic = "Legacy"
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
    deposition.sample_ids = [sample_id]
    deposition.operator = "r.calvert"
    deposition.timestamp = timestamp
    deposition.comments = comments

    layer = FiveChamberLayer(deposition)
    layer.date = timestamp.date()
    layer.temperature_1 = int(random.uniform(150, 160))
    layer.temperature_2 = int(random.uniform(150, 180))
    layer.sih4 = int(random.uniform(0, 5))
    layer.h2 = int(random.uniform(0, 2))
    layer.chamber = "p"
    layer.layer_type = "p"

    layer = FiveChamberLayer(deposition)
    layer.date = timestamp.date()
    layer.temperature_1 = int(random.uniform(100, 160))
    layer.temperature_2 = int(random.uniform(170, 180))
    layer.sih4 = int(random.uniform(0, 4))
    layer.h2 = int(random.uniform(0, 1))
    layer.chamber = "i2"
    layer.layer_type = "i"

    layer = FiveChamberLayer(deposition)
    layer.date = timestamp.date()
    layer.temperature_1 = int(random.uniform(130, 150))
    layer.temperature_2 = int(random.uniform(155, 160))
    layer.sih4 = int(random.uniform(0, 10))
    layer.h2 = int(random.uniform(0, 12))
    layer.chamber = "n"
    layer.layer_type = "n"

    deposition.submit()

create_depo(datetime.datetime(2014, 11, 1, 10, 30), "14S-001")
create_depo(datetime.datetime(2014, 11, 2, 11, 10), "14S-002")
create_depo(datetime.datetime(2014, 11, 2, 12, 10), "14S-003","AFTER: chamber cleaned!")
create_depo(datetime.datetime(2014, 11, 2, 13, 10), "14S-004")
create_depo(datetime.datetime(2014, 11, 2, 14, 10), "14S-005")
create_depo(datetime.datetime(2014, 11, 2, 15, 10), "14S-006")

logout()
