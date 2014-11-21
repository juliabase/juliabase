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

import random, os, datetime
import numpy


measurement_index = 1
rootdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../remote_client/examples/solarsimulator_raw_data"))
voltages = numpy.arange(-0.1, 1.001, 0.01)


def create_data():
    return numpy.exp(voltages) - 1.2

        
for sample_name in ("14C-{:03}".format(number) for number in range(1, 10)):
    header = """Number: {}
Timestamp: {}
Operator: {}
Comments: {}
Sample: {}
Layout: {}
Irradiance: {}
Temperature: {}
positions: {}
----------------------------------------------------------------------
U/V{}""".format(measurement_index, datetime.datetime(2014, 11, 8, 10, 0, 0).strftime("%Y-%m-%d %H:%M:%S"), "h.griffin", "",
                sample_name, "juelich standard", "AM1.5", "23.5", " ".join(str(cell_index) for cell_index in range(1, 37)),
                36 * "  I/A")
    data = [voltages]
    for cell_index in range(1, 37):
        data.append(create_data())
    numpy.savetxt(os.path.join(rootdir, "measurement-{}.dat".format(measurement_index)), numpy.transpose(data),
                  "%04.3f", header=header)
    measurement_index += 1
