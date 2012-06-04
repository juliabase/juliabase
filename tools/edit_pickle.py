#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

from __future__ import division, unicode_literals
import cPickle as pickle
import os.path

pickle_file = "/home/chantal/crawler_data/maike.pickle"
log_file = "/home/chantal/crawler_data/solarsimulator_photo_measurement.log"
root_dir = b"/mnt/P/LABOR USER/maike_user/ascii files/"

statuses, pattern = pickle.load(open(pickle_file, "rb"))

for line in open(log_file, "r").readlines():
    if "ERROR" in line:
        start = line.index('"') + 1
        end = line.rindex('"')
        filepath = os.path.relpath(line[start:end], root_dir)
        del statuses[filepath]
pickle.dump((statuses, pattern), open(pickle_file, "wb"), pickle.HIGHEST_PROTOCOL)
