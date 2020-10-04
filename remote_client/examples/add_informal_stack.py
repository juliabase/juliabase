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


"""This is simply a helper program to get the demo site complete.  It fetches
the ID of the sample 14S-001 and attaches informal layers to it by leading an
ad-hoc generated fixture.  This is not very elegangt but as long as there is no
facility in the remote client library to add informal stacks, this is the way
to go.
"""

import sys, os, subprocess
sys.path.append(os.path.abspath(".."))
from jb_remote_inm import *


setup_logging("console")
login("juliabase", "12345")
sample_id = Sample("14S-001").id
logout()


open("/tmp/informal_stack.yaml", "w").write("""- fields: {{additional_process_data: '', always_collapsed: false, classification: 'a-Si:H',
    color: red, comments: '', doping: p, index: 2, process: null, sample_details: {0},
    structured: false, textured: false, thickness: '50.0', thickness_reliable: true,
    verified: true}}
  model: institute.informallayer
  pk: 1
- fields: {{additional_process_data: '', always_collapsed: false, classification: 'a-Si:H',
    color: orange, comments: '', doping: i, index: 3, process: null, sample_details: {0},
    structured: false, textured: false, thickness: '120.0', thickness_reliable: true,
    verified: true}}
  model: institute.informallayer
  pk: 2
- fields: {{additional_process_data: '', always_collapsed: false, classification: 'a-Si:H',
    color: green, comments: '', doping: n, index: 4, process: null, sample_details: {0},
    structured: false, textured: false, thickness: '50.0', thickness_reliable: true,
    verified: true}}
  model: institute.informallayer
  pk: 3
- fields: {{additional_process_data: '', always_collapsed: false, classification: glass,
    color: lightblue, comments: '', doping: null, index: 1, process: null, sample_details: {0},
    structured: false, textured: false, thickness: '1100000.0', thickness_reliable: true,
    verified: true}}
  model: institute.informallayer
  pk: 4
- fields: {{additional_process_data: '', always_collapsed: false, classification: silver,
    color: silver, comments: '', doping: null, index: 5, process: null, sample_details: {0},
    structured: true, textured: false, thickness: '800.0', thickness_reliable: true,
    verified: true}}
  model: institute.informallayer
  pk: 5
""".format(sample_id))

subprocess.check_call(["../../manage.py", "loaddata", "/tmp/informal_stack.yaml"])
os.remove("/tmp/informal_stack.yaml")
