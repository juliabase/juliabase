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


from __future__ import absolute_import, unicode_literals
from chantal_ipv.views.samples import json_client


def clean_up_after_merging(from_sample, to_sample):
    """Deletes the duplicate substrate process after merging two samples.

    :Parameters:
     - `from_sample`: The sample which is merged into the other sample
     - `to_sample`: The sample which should contain the processes from the
       other sample

    :type from_sample: `models.Sample`
    :type to_sample: `models.Sample`
    """
    substrates_to_sample = json_client.get_substrates(to_sample)
    substrate_from_sample = json_client.get_substrate(from_sample)
    if len(substrates_to_sample) == 2:
        substrates_to_sample.remove(substrate_from_sample)
        substrate_to_sample = substrates_to_sample[0]
        substrate_to_sample.timestamp = min(substrate_to_sample.timestamp, substrate_from_sample.timestamp)
        if substrate_from_sample.comments not in substrate_to_sample.comments:
            substrate_to_sample.comments += "\n\n{comments}".format(comments=substrate_from_sample.comments)
        substrate_to_sample.save()
        substrate_from_sample.samples.remove(to_sample)
        if substrate_from_sample.samples.count() == 1:
            substrate_from_sample.delete()
