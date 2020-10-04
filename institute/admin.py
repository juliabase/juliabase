# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


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
