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

from django.contrib import admin
from chantal_institute.models_depositions import ClusterToolDeposition, ClusterToolHotWireLayer, \
    ClusterToolPECVDLayer, FiveChamberDeposition, FiveChamberLayer
from chantal_institute.models_physical_processes import PDSMeasurement, Substrate, SolarsimulatorPhotoMeasurement, \
    SolarsimulatorPhotoCellMeasurement, Structuring
from chantal_institute.models import SampleDetails, InformalLayer

admin.site.register(ClusterToolDeposition)
admin.site.register(ClusterToolHotWireLayer)
admin.site.register(ClusterToolPECVDLayer)
admin.site.register(FiveChamberDeposition)
admin.site.register(FiveChamberLayer)

admin.site.register(Substrate)
admin.site.register(PDSMeasurement)
admin.site.register(SolarsimulatorPhotoMeasurement)
admin.site.register(SolarsimulatorPhotoCellMeasurement)
admin.site.register(SampleDetails)

admin.site.register(InformalLayer)
admin.site.register(Structuring)
