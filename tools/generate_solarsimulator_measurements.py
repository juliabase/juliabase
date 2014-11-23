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


shapes = {"1": ((18, 18.5), (10, 10)),
          "2": ((31.5, 18.5), (10, 10)),
          "3": ((43, 18.5), (10, 10)),
          "4": ((56.5, 18.5), (10, 10)),
          "5": ((68, 18.5), (10, 10)),
          "6": ((81.5, 18.5), (10, 10)),
          "7": ((18, 32.5), (10, 5)),
          "8": ((33, 32.5), (20, 5)),
          "9": ((60, 32.5), (2, 5)),
          "10": ((64, 32.5), (2, 5)),
          "11": ((68, 32.5), (2, 5)),
          "12": ((72, 32.5), (2, 5)),
          "13": ((81.5, 32.5), (10, 5)),
          "14": ((18, 43.5), (10, 10)),
          "15": ((31.5, 43.5), (10, 10)),
          "16": ((43, 43.5), (10, 10)),
          "17": ((56.5, 43.5), (10, 10)),
          "18": ((68, 43.5), (10, 10)),
          "19": ((81.5, 43.5), (10, 10)),
          "20": ((18, 57.5), (10, 5)),
          "21": ((35, 57.5), (2, 5)),
          "22": ((39, 57.5), (2, 5)),
          "23": ((43, 57.5), (2, 5)),
          "24": ((47, 57.5), (2, 5)),
          "25": ((58, 57.5), (20, 5)),
          "26": ((81.5, 57.5), (10, 5)),
          "27": ((18, 68.5), (10, 10)),
          "28": ((31.5, 68.5), (10, 10)),
          "29": ((43, 68.5), (10, 10)),
          "30": ((56.5, 68.5), (10, 10)),
          "31": ((68, 68.5), (10, 10)),
          "32": ((81.5, 68.5), (10, 10)),
          "33": ((18, 82.5), (10, 5)),
          "34": ((33, 82.5), (20, 5)),
          "35": ((58, 82.5), (20, 5)),
          "36": ((81.5, 82.5), (10, 5))}

areas = {position: shape[1][0] * shape[1][1] / 100 for position, shape in shapes.items()}


def create_data(x_scale, y_scale, y_offset):
    return y_scale * (numpy.exp((voltages - 0.8) * x_scale) - 1 - y_offset + 0.3 * (numpy.random.sample((len(voltages),)) - 0.5))


measured_positions = []
for position in range(1, 37):
    if random.random() > 0.6:
        measured_positions.append(str(position))

for sample_name in ("14C-{:03}".format(number) for number in range(1, 10)):
    header = """Number: {}
Timestamp: {}
Operator: {}
Comments: {}
Sample: {}
Layout: {}
Irradiance: {}
Temperature: {}
Positions: {}
Areas: {}
----------------------------------------------------------------------
U/V{}""".format(measurement_index, datetime.datetime(2014, 11, 8, 10, 0, 0).strftime("%Y-%m-%d %H:%M:%S"), "h.griffin", "",
                sample_name, "juelich standard", "AM1.5", "23.5", " ".join(measured_positions),
                " ".join(str(areas[position]) for position in measured_positions), len(measured_positions) * "  I/A")
    data = [voltages]
    for index in measured_positions:
        width, height = shapes[str(index)][1]
        area = width * height / 100
        data.append(create_data(random.gauss(10, 3), random.gauss(0.001 * area, 0.0003 * area), random.gauss(0, 0.01)))
    numpy.savetxt(os.path.join(rootdir, "measurement-{}.dat".format(measurement_index)), numpy.transpose(data), "%06.5f",
                  header=header)
    measurement_index += 1
