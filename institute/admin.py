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


from __future__ import absolute_import, unicode_literals

from django.contrib import admin
from institute.models.depositions import ClusterToolDeposition, ClusterToolHotWireLayer, \
    ClusterToolPECVDLayer, FiveChamberDeposition, FiveChamberLayer
from institute.models.physical_processes import PDSMeasurement, Substrate, SolarsimulatorMeasurement, \
    SolarsimulatorCellMeasurement, Structuring
from institute.models import SampleDetails, InformalLayer

admin.site.register(ClusterToolDeposition)
admin.site.register(ClusterToolHotWireLayer)
admin.site.register(ClusterToolPECVDLayer)
admin.site.register(FiveChamberDeposition)
admin.site.register(FiveChamberLayer)

admin.site.register(Substrate)
admin.site.register(PDSMeasurement)
admin.site.register(SolarsimulatorMeasurement)
admin.site.register(SolarsimulatorCellMeasurement)
admin.site.register(SampleDetails)

admin.site.register(InformalLayer)
admin.site.register(Structuring)
