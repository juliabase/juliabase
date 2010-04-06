#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

from django.contrib import admin
from samples.models_common import ExternalOperator, Sample, SampleAlias, SampleSplit, Substrate, SampleDeath, Result, \
    SampleSeries, Initials, UserDetails
from samples.models_feeds import FeedNewSamples, FeedMovedSamples, FeedNewPhysicalProcess, FeedEditedPhysicalProcess, \
    FeedResult, FeedCopiedMySamples, FeedEditedSamples, FeedSampleSplit, FeedEditedSampleSeries, FeedNewSampleSeries, \
    FeedMovedSampleSeries, FeedChangedGroup

admin.site.register(ExternalOperator)
admin.site.register(Sample)
admin.site.register(SampleAlias)
admin.site.register(SampleSplit)
admin.site.register(Substrate)
admin.site.register(SampleDeath)
admin.site.register(Result)
admin.site.register(SampleSeries)
admin.site.register(Initials)
admin.site.register(UserDetails)

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
admin.site.register(FeedChangedGroup)
