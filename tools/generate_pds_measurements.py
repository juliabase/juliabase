#!/usr/bin/env python3
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

import os, random, datetime, glob
import numpy


numpy.random.seed(8765432)
random.seed(8765432)
rootdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../remote_client/examples/pds_raw_data"))
energies = numpy.arange(0.8, 2.5, 0.02)


for filepath in glob.glob(os.path.join(rootdir, "measurement-*.dat")):
    os.remove(filepath)


for number, sample_name in enumerate(("14-JS-{}".format(number) for number in range(1, 7)), 1):
    header = """Number: {}
Timestamp: {}
Operator: n.burkhardt
Comments:
Sample: {}
Apparatus: 1
----------------------------------------------------------------------
energy/eV     absorption/cm^-1""".format(number, datetime.datetime(2014, 11, 7, 10, number, 0).strftime("%Y-%m-%d %H:%M:%S"),
                                         sample_name)
    absorptions = 1 / (1 / (random.gauss(1, 0.2) * numpy.exp((energies - 1) * 10)) + 1 / 10000) + \
                  max(random.gauss(10, 10), 0) + 30 * numpy.random.sample((len(energies),))
    data = [energies, absorptions]
    numpy.savetxt(os.path.join(rootdir, "measurement-{}.dat".format(number)), numpy.transpose(data), "%06.5f",
                  header=header)
