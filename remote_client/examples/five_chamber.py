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
from jb_remote_institute import *

login("juliabase", "12345")

timestamp = datetime.datetime.now()
try:
    sample_id = get_sample("14-EM-1")
except SampleNotFound as exception:
    sample = exception.sample
    sample.currently_responsible_person = "r.calvert"
    sample.topic = "Legacy"
    sample_id = sample.submit()

    substrate = Substrate()
    substrate.timestamp =  - datetime.timedelta(minutes=1)
    substrate.timestamp_inaccuracy = 3
    substrate.sample_ids = [sample_id]
    substrate.material = "corning"
    substrate.operator = "r.calvert"
    substrate.submit()

deposition = FiveChamberDeposition()
deposition.sample_ids = [sample_id]
layer = FiveChamberLayer(deposition)
layer.date = datetime.date.today()
layer.chamber = "p"

deposition.submit()

logout()
