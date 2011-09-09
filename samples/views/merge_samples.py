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

u"""
"""

from __future__ import absolute_import

import re, json
from django.utils.translation import ugettext as _, ugettext_lazy
from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.forms.util import ValidationError
import django.contrib.auth.models
from chantal_common.utils import append_error
from samples import models, permissions
from samples.views import utils
from django.contrib import messages
from samples.views import form_utils


class MergeSamplesForm(forms.Form):

    from_sample = form_utils.SampleField(label=_(u"merge sample"), required=False)
    to_sample = form_utils.SampleField(label=_(u"into sample"), required=False)

    def __init__(self, user, from_sample_preset, to_sample_preset, *args, **kwargs):
        super(MergeSamplesForm, self).__init__(*args, **kwargs)
        self.user = user
        samples = list(user.my_samples.all())
        if from_sample_preset:
            self.fields["from_sample"].initial = from_sample_preset.pk
        if to_sample_preset:
            self.fields["to_sample"].initial = to_sample_preset.pk
        self.fields["from_sample"].set_samples(samples, user)
        self.fields["to_sample"].set_samples(samples, user)

    def clean_from_sample(self):
        from_sample = self.cleaned_data["from_sample"]
        print self.cleaned_data["from_sample"]
        if from_sample and from_sample.split_origin or models.SampleSplit.objects.filter(parent=from_sample):
            raise ValidationError(_(u"It is not possible to merge a sample who was split or is a result of a split process."))
        return from_sample

    def clean(self):
        def has_process(sample, process_cls):
            for process in models.Process.objects.filter(samples=sample):
                process = process.actual_instance
                if isinstance(process, process_cls):
                    return process
            return None

        cleaned_data = self.cleaned_data
        from_sample = cleaned_data.get("from_sample")
        to_sample = cleaned_data.get("to_sample")
        if from_sample and to_sample:
            if not (from_sample.currently_responsible_person == to_sample.currently_responsible_person == self.user):
                append_error(self, _(u"The user must be the currently responsible person from both samples."))
                del cleaned_data[from_sample]
                del cleaned_data[to_sample]
            if from_sample == to_sample:
                append_error(self, _(u"You can't merge a sample into itself."))
                try:
                    del cleaned_data[from_sample]
                    del cleaned_data[to_sample]
                except KeyError:
                    pass
            sample_death = has_process(to_sample, models.SampleDeath)
            sample_split = has_process(to_sample, models.SampleSplit)
            latest_process = models.Process.objects.filter(samples=from_sample).order_by('timestamp').reverse()[0]
            if sample_death and sample_death.timestamp <= latest_process.timestamp:
                append_error(self, _(u"One or more processes would be after sample death from {0}.").format(to_sample.name))
                try:
                    del cleaned_data[from_sample]
                except KeyError:
                    pass
            if sample_split and sample_split.timestamp <= latest_process.timestamp:
                append_error(self, _(u"One or more processes would be after sample split from {0}.").format(to_sample.name))
                try:
                    del cleaned_data[from_sample]
                except KeyError:
                    pass
        elif from_sample and not to_sample:
            append_error(self, _(u"You must select a target sample."))
        return cleaned_data



def merge_samples(from_sample, to_sample):
    current_sample = to_sample
    to_sample_split_origin = to_sample.split_origin
    process_set = set(models.Process.objects.filter(samples=current_sample))
    for process in models.Process.objects.filter(samples=from_sample).order_by('timestamp').reverse():
        if to_sample_split_origin and to_sample_split_origin.timestamp >= process.timestamp:
            current_sample.processes = process_set
            current_sample = to_sample_split_origin.parent
            to_sample_split_origin = current_sample.split_origin
            process_set = set(models.Process.objects.filter(samples=current_sample))
        process_set.update([process])
    current_sample.processes = process_set
    sample_series = set(models.SampleSeries.objects.filter(samples=to_sample))
    sample_series.update(set(models.SampleSeries.objects.filter(samples=from_sample)))
    to_sample.series = sample_series
    sample_alias = models.SampleAlias()
    sample_alias.name = from_sample.name
    sample_alias.sample = to_sample
    sample_alias.save()
    from_sample.delete()



def extract_preset_sample_by_name(request, name):

    query_string_dict = utils.parse_query_string(request)
    if name in query_string_dict:
        try:
            return models.Sample.objects.get(name=query_string_dict[name])
        except models.Sample.DoesNotExist:
            pass



def is_referentially_valid(merge_samples_forms):
    u"""

    :Return:


    :rtype: bool
    """
    referentially_valid = True
    from_samples = set()
    for merge_samples_form in merge_samples_forms:
        if merge_samples_form.is_valid():
            from_sample = merge_samples_form.cleaned_data["from_sample"]
            if from_sample in from_samples:
                append_error(merge_samples_form, _(u"You can merge a sample only once."))
                referentially_valid = False
            elif from_sample:
                from_samples.add(from_sample)
    return referentially_valid


def from_post_data(request):
    merge_samples_forms = []
    for index in range(10):
        merge_samples_forms.append(MergeSamplesForm(request.user, extract_preset_sample_by_name(request,
                                                    "{0}_from_sample".format(index)),
                                                    extract_preset_sample_by_name(request, "{0}_to_sample".format(index)),
                                                    request.POST, prefix=str(index)))
    return merge_samples_forms


@login_required
def merge(request):

    if request.method == "POST":
        merge_samples_forms = from_post_data(request)
        all_valid = all([merge_samples_form.is_valid() for merge_samples_form in merge_samples_forms])
        referentially_valid = is_referentially_valid(merge_samples_forms)
        if all_valid and referentially_valid:
            for merge_samples_form in merge_samples_forms:
                from_sample = merge_samples_form.cleaned_data.get("from_sample")
                to_sample = merge_samples_form.cleaned_data.get("to_sample")
                if from_sample and to_sample:
                    merge_samples(from_sample, to_sample)
            return utils.successful_response(request, _(u"Samples were successfully merged."))
    else:
        merge_samples_forms = [MergeSamplesForm(request.user,
                                                extract_preset_sample_by_name(request, "{0}_from_sample".format(index)),
                                                extract_preset_sample_by_name(request, "{0}_to_sample".format(index)),
                                                prefix=str(index)) for index in range(10)]
    return render_to_response("samples/merge_samples.html", {"title": _(u"Merge samples"), "merge_forms": merge_samples_forms},
                              context_instance=RequestContext(request))
