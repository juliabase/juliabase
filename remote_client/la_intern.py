#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from chantal_remote import *
import chantal_remote

import ConfigParser, os.path
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("/var/www/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

login(credentials["crawlers_login"], credentials["crawlers_password"])

deposition_numbers = LargeAreaDeposition.get_already_available_deposition_numbers()

samples = set()

for deposition_number in deposition_numbers:
    deposition = LargeAreaDeposition(deposition_number)
    for id_ in deposition.sample_ids:
        sample = Sample(id_=id_)
        sample.topic = "Large-Area intern"
        sample.edit_description = "automatic move of sample to topic LA intern"
        sample.submit()

logout()
