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


from django.contrib import admin
from django.conf import settings
from samples.models import ExternalOperator, Sample, SampleAlias, SampleSplit, SampleDeath, Result, \
    SampleSeries, Initials, UserDetails, Process, Clearance, SampleClaim, StatusMessage, Task
from samples.models import FeedNewSamples, FeedMovedSamples, FeedNewPhysicalProcess, FeedEditedPhysicalProcess, \
    FeedResult, FeedCopiedMySamples, FeedEditedSamples, FeedSampleSplit, FeedEditedSampleSeries, FeedNewSampleSeries, \
    FeedMovedSampleSeries, FeedChangedTopic, FeedStatusMessage


class SampleAdmin(admin.ModelAdmin):
    raw_id_fields = ("processes",)


class ClearanceAdmin(admin.ModelAdmin):
    raw_id_fields = ("processes",)


class TaskAdmin(admin.ModelAdmin):
    raw_id_fields = ("finished_process", "samples")


admin.site.register(ExternalOperator)
admin.site.register(Sample, SampleAdmin)
admin.site.register(SampleAlias)
admin.site.register(SampleSplit)
admin.site.register(SampleDeath)
admin.site.register(Result)
admin.site.register(SampleSeries)
admin.site.register(Initials)
admin.site.register(UserDetails)
admin.site.register(Process)
admin.site.register(Clearance, ClearanceAdmin)
admin.site.register(SampleClaim)
admin.site.register(StatusMessage)
admin.site.register(Task, TaskAdmin)

admin.site.register(FeedNewSamples)
admin.site.register(FeedMovedSamples)
admin.site.register(FeedNewPhysicalProcess)
admin.site.register(FeedEditedPhysicalProcess)
admin.site.register(FeedResult)
admin.site.register(FeedCopiedMySamples)
admin.site.register(FeedEditedSamples)
admin.site.register(FeedSampleSplit)
admin.site.register(FeedEditedSampleSeries)
admin.site.register(FeedNewSampleSeries)
admin.site.register(FeedMovedSampleSeries)
admin.site.register(FeedChangedTopic)
admin.site.register(FeedStatusMessage)
