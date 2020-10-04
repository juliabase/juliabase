# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import random, os, datetime, itertools, glob
import numpy


numpy.random.seed(8765432)
random.seed(8765432)
rootdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../remote_client/examples/solarsimulator_raw_data"))
voltages = numpy.arange(-0.1, 1.001, 0.01)


for filepath in glob.glob(os.path.join(rootdir, "measurement-*.dat")):
    os.remove(filepath)


shapes_inm = {"1": ((18, 18.5), (10, 10)),
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
areas_inm = {position: shapes_inm[1][0] * shapes_inm[1][1] / 100 for position, shapes_inm in shapes_inm.items()}

shapes_acme = {"1A": ((4.42, 29.12), (2.6, 2.6)),
               "1B": ((12.22, 29.12), (2.6, 2.6)),
               "1C": ((20.02, 29.12), (2.6, 2.6)),
               "1D": ((27.82, 29.12), (2.6, 2.6)),
               "2A": ((4.42, 22.62), (3.9, 3.9)),
               "2B": ((12.22, 22.62), (3.9, 3.9)),
               "2C": ((20.02, 22.62), (3.9, 3.9)),
               "2D": ((27.82, 22.62), (3.9, 3.9)),
               "3A": ((4.42, 16.12), (2.6, 2.6)),
               "3B": ((12.22, 16.12), (2.6, 2.6)),
               "3C": ((20.02, 16.12), (2.6, 2.6)),
               "3D": ((27.82, 16.12), (2.6, 2.6)),
               "4A": ((4.42, 8.32), (3.9, 3.9)),
               "4B": ((12.22, 8.32), (3.9, 3.9)),
               "4C": ((20.02, 8.32), (3.9, 3.9)),
               "4D": ((27.82, 8.32), (3.9, 3.9)),
               "5A": ((4.42, 3.12), (2.6, 2.6)),
               "5B": ((12.22, 3.12), (2.6, 2.6)),
               "5C": ((20.02, 3.12), (2.6, 2.6)),
               "5D": ((27.82, 3.12), (2.6, 2.6))}
areas_acme = {position: shape_acme[1][0] * shape_acme[1][1] / 100 for position, shape_acme in shapes_acme.items()}


def create_data(x_scale, y_scale, y_offset):
    return y_scale * (numpy.exp((voltages - 0.8) * x_scale) - 1 - y_offset + 0.3 * (numpy.random.sample((len(voltages),)) - 0.5))


measurement_index = 1


for sample_name in ("14-JS-{}".format(number) for number in range(1, 7)):
    measured_positions = []
    for position in range(1, 37):
        if random.random() > 0.6:
            measured_positions.append(str(position))

    header = """Timestamp: {timestamp}
Operator: {operator}
Comments:
Sample: {sample}
Layout: {layout}
Irradiation: {irradiation}
Temperature: {temperature}
Positions: {positions}
Areas: {areas}
----------------------------------------------------------------------
U/V{column_headers}"""
    header_data = {"timestamp": datetime.datetime(2014, 10, 8, 10, measurement_index, 0).strftime("%Y-%m-%d %H:%M:%S"),
                   "operator": "h.griffin",
                   "sample": sample_name,
                   "layout": "inm standard",
                   "irradiation": "AM1.5",
                   "temperature": "23.5",
                   "positions": " ".join(measured_positions),
                   "areas": " ".join(str(areas_inm[position]) for position in measured_positions),
                   "column_headers": len(measured_positions) * "  I/A"}
    data = [voltages]
    for position in measured_positions:
        area = areas_inm[position]
        data.append(create_data(random.gauss(10, 3), random.gauss(0.01 * area, 0.003 * area), random.gauss(0, 0.01)))
    numpy.savetxt(os.path.join(rootdir, "measurement-{}.dat".format(measurement_index)), numpy.transpose(data), "%06.5f",
                  header=header.format(**header_data))
    measurement_index += 1
    if random.random() > 0.3:
        header_data["timestamp"] = datetime.datetime(2014, 10, 8, 10, measurement_index, 0).strftime("%Y-%m-%d %H:%M:%S")
        header_data["irradiation"] = "BG7"
        for i in range(1, len(data)):
            data[i] *= numpy.random.sample((len(voltages),)) * 0.05 + 0.2
        numpy.savetxt(os.path.join(rootdir, "measurement-{}.dat".format(measurement_index)), numpy.transpose(data), "%06.5f",
                      header=header.format(**header_data))
        measurement_index += 1


for sample_name in ("14S-{:03}".format(number) for number in range(1, 7)):
    measured_positions = []
    for position in (a + b for a, b in itertools.product("1234", "ABCD")):
        if random.random() > 0.3:
            measured_positions.append(position)

    header = """Timestamp: {timestamp}
Operator: {operator}
Comments: {comments}
Sample: {sample}
Layout: {layout}
Irradiation: {irradiation}
Temperature: {temperature}
Positions: {positions}
Areas: {areas}
----------------------------------------------------------------------
U/V{column_headers}"""
    header_data = {"timestamp": datetime.datetime(2014, 10, 8, 10, measurement_index, 0).strftime("%Y-%m-%d %H:%M:%S"),
                   "operator": "r.calvert",
                   "comments": "Click on cells to change data.",
                   "sample": sample_name,
                   "layout": "acme1",
                   "irradiation": "AM1.5",
                   "temperature": "23.5",
                   "positions": " ".join(measured_positions),
                   "areas": " ".join(str(areas_acme[position]) for position in measured_positions),
                   "column_headers": len(measured_positions) * "  I/A"}
    data = [voltages]
    for position in measured_positions:
        area = areas_acme[position]
        data.append(create_data(random.gauss(10, 3), random.gauss(0.01 * area, 0.003 * area), random.gauss(0, 0.01)))
    numpy.savetxt(os.path.join(rootdir, "measurement-{}.dat".format(measurement_index)), numpy.transpose(data), "%06.5f",
                  header=header.format(**header_data))
    measurement_index += 1
    if random.random() > 0.2:
        header_data["timestamp"] = datetime.datetime(2014, 10, 8, 10, measurement_index, 0).strftime("%Y-%m-%d %H:%M:%S")
        header_data["irradiation"] = "BG7"
        header_data["comments"] = r"There was a *small* crack in the filter.  Note that $I_{\mathrm{sc}}$ is actually" \
                                  r"$J_{\mathrm{sc}} = \frac{I_{\mathrm{sc}}}{A}$."
        for i in range(1, len(data)):
            data[i] *= numpy.random.sample((len(voltages),)) * 0.05 + 0.2
        numpy.savetxt(os.path.join(rootdir, "measurement-{}.dat".format(measurement_index)), numpy.transpose(data), "%06.5f",
                      header=header.format(**header_data))
        measurement_index += 1
