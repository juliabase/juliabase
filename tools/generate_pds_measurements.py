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
energy/eV     absorption/cm^-1""".format(number, datetime.datetime(2014, 10, 7, 10, number, 0).strftime("%Y-%m-%d %H:%M:%S"),
                                         sample_name)
    absorptions = 1 / (1 / (random.gauss(1, 0.2) * numpy.exp((energies - 1) * 10)) + 1 / 10000) + \
                  max(random.gauss(10, 10), 0) + 30 * numpy.random.sample((len(energies),))
    data = [energies, absorptions]
    numpy.savetxt(os.path.join(rootdir, "measurement-{}.dat".format(number)), numpy.transpose(data), "%06.5f",
                  header=header)
