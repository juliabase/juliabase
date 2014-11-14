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

import sys, os, datetime
sys.path.append(os.path.abspath(".."))
from jb_remote_institute import *

login("juliabase", "12345")

sample_id = get_or_create_sample("14-TB-1", "Corning", datetime.datetime.now())

pds_measurement = PDSMeasurement()
pds_measurement.number = 1
pds_measurement.apparatus = "pds1"
pds_measurement.raw_datafile = "measurement-1.dat"
pds_measurement.sample_id = sample_id
pds_measurement.submit()

logout()
