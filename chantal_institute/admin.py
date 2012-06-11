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
from chantal_institute.models_depositions import SixChamberDeposition, SixChamberLayer, SixChamberChannel, LargeAreaDeposition, \
    LargeAreaLayer, OldClusterToolDeposition, OldClusterToolHotWireLayer, OldClusterToolPECVDLayer, \
    FiveChamberDeposition, FiveChamberLayer, LargeSputterDeposition, LargeSputterLayer, \
    NewClusterToolDeposition, NewClusterToolHotWireLayer, NewClusterToolPECVDLayer, NewClusterToolSputterLayer, \
    PHotWireDeposition, PHotWireLayer, LADADeposition, LADALayer, JANADeposition, JANALayer
from chantal_institute.models_physical_processes import HallMeasurement, PDSMeasurement, LumaMeasurement, DektakMeasurement, \
    ConductivityMeasurementSet, SingleConductivityMeasurement, RamanMeasurementOne, RamanMeasurementTwo, \
    RamanMeasurementThree, ManualEtching, ThroughputEtching, DSRMeasurement, DSRIVData, DSRSpectralData, IRMeasurement, \
    Substrate, CleaningProcess, SmallEvaporation, LargeEvaporation, LayerThicknessMeasurement, SolarsimulatorPhotoMeasurement, \
    SolarsimulatorDarkMeasurement, SolarsimulatorPhotoCellMeasurement, SolarsimulatorDarkCellMeasurement, Structuring, \
    SputterCharacterization, LargeAreaCleaningProcess
from chantal_institute.models import SampleDetails, InformalLayer, GroupMeetingSchedule

admin.site.register(SixChamberDeposition)
admin.site.register(SixChamberLayer)
admin.site.register(SixChamberChannel)
admin.site.register(LargeAreaDeposition)
admin.site.register(LargeAreaLayer)
admin.site.register(OldClusterToolDeposition)
admin.site.register(OldClusterToolHotWireLayer)
admin.site.register(OldClusterToolPECVDLayer)
admin.site.register(FiveChamberDeposition)
admin.site.register(FiveChamberLayer)
admin.site.register(LargeSputterDeposition)
admin.site.register(LargeSputterLayer)
admin.site.register(NewClusterToolDeposition)
admin.site.register(NewClusterToolHotWireLayer)
admin.site.register(NewClusterToolPECVDLayer)
admin.site.register(NewClusterToolSputterLayer)
admin.site.register(PHotWireDeposition)
admin.site.register(PHotWireLayer)
admin.site.register(Substrate)
admin.site.register(HallMeasurement)
admin.site.register(PDSMeasurement)
admin.site.register(LumaMeasurement)
admin.site.register(DektakMeasurement)
admin.site.register(ConductivityMeasurementSet)
admin.site.register(SingleConductivityMeasurement)
admin.site.register(RamanMeasurementOne)
admin.site.register(RamanMeasurementTwo)
admin.site.register(RamanMeasurementThree)
admin.site.register(DSRMeasurement)
admin.site.register(DSRIVData)
admin.site.register(DSRSpectralData)
admin.site.register(IRMeasurement)
admin.site.register(CleaningProcess)
admin.site.register(ManualEtching)
admin.site.register(ThroughputEtching)
admin.site.register(SmallEvaporation)
admin.site.register(LargeEvaporation)
admin.site.register(LayerThicknessMeasurement)
admin.site.register(SolarsimulatorPhotoMeasurement)
admin.site.register(SolarsimulatorDarkMeasurement)
admin.site.register(SolarsimulatorPhotoCellMeasurement)
admin.site.register(SolarsimulatorDarkCellMeasurement)
admin.site.register(SampleDetails)
admin.site.register(InformalLayer)
admin.site.register(GroupMeetingSchedule)
admin.site.register(Structuring)
admin.site.register(SputterCharacterization)
admin.site.register(LADADeposition)
admin.site.register(LADALayer)
admin.site.register(LargeAreaCleaningProcess)
admin.site.register(JANADeposition)
admin.site.register(JANALayer)
