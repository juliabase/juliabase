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

"""This is simply a helper program to get the demo site complete.  It fetches
the ID of the sample 14S-001 and attaches informal layers to it by leading an
ad-hoc generated fixture.  This is not very elegangt but as long as there is no
facility in the remot client library to add informal stacks, this is the way to
go.
"""

from __future__ import unicode_literals

import sys, os, subprocess
sys.path.append(os.path.abspath(".."))
from jb_remote_institute import *


login("juliabase", "12345")
sample_id = Sample("14S-001").id
logout()


open("informal_stack.yaml", "w").write("""- fields: {{additional_process_data: '', always_collapsed: false, classification: 'a-Si:H',
    color: red, comments: '', doping: p, index: 2, process: null, sample_details: {0},
    structured: false, textured: false, thickness: '50.0', thickness_reliable: true,
    verified: true}}
  model: jb_institute.informallayer
  pk: 1
- fields: {{additional_process_data: '', always_collapsed: false, classification: 'a-Si:H',
    color: orange, comments: '', doping: i, index: 3, process: null, sample_details: {0},
    structured: false, textured: false, thickness: '120.0', thickness_reliable: true,
    verified: true}}
  model: jb_institute.informallayer
  pk: 2
- fields: {{additional_process_data: '', always_collapsed: false, classification: 'a-Si:H',
    color: green, comments: '', doping: n, index: 4, process: null, sample_details: {0},
    structured: false, textured: false, thickness: '50.0', thickness_reliable: true,
    verified: true}}
  model: jb_institute.informallayer
  pk: 3
- fields: {{additional_process_data: '', always_collapsed: false, classification: glass,
    color: lightblue, comments: '', doping: null, index: 1, process: null, sample_details: {0},
    structured: false, textured: false, thickness: '1100000.0', thickness_reliable: true,
    verified: true}}
  model: jb_institute.informallayer
  pk: 4
- fields: {{additional_process_data: '', always_collapsed: false, classification: silver,
    color: silver, comments: '', doping: null, index: 5, process: null, sample_details: {0},
    structured: true, textured: false, thickness: '800.0', thickness_reliable: true,
    verified: true}}
  model: jb_institute.informallayer
  pk: 5
""".format(sample_id))

subprocess.check_call(["python", "../../manage.py", "loaddata", "informal_stack.yaml"])
os.remove("informal_stack.yaml")
