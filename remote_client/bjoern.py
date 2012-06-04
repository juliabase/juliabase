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

deposition_numbers = SixChamberDeposition.get_already_available_deposition_numbers()

bjoerns_samples = set()

for deposition_number in deposition_numbers:
    if int(deposition_number[:2]) >= 9:
        deposition = SixChamberDeposition(deposition_number)
        if deposition.operator == "b.grootoonk":
            id_ = deposition.sample_ids[0]
            sample = Sample(id_=id_)
            if sample.currently_responsible_person != "b.grootoonk":
                sample.currently_responsible_person = "b.grootoonk"
                sample.current_location = "Björns Büro"
                sample.topic = "nip n-side"
                sample.edit_description = "automatic move of sample to Björn"
                sample.submit()
            bjoerns_samples.add(id_)

chantal_remote.connection.open("change_my_samples", {"add": ",".join(bjoerns_samples)})

logout()
