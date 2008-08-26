#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect
from chantal.samples import models
from django.forms import ModelForm, Form
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
from django.db.models import Q
from . import utils

class SampleSeriesForm(ModelForm):
    _ = ugettext_lazy
    samples = forms.ModelMultipleChoiceField(label=_(u"Samples"), queryset=None)
    def __init__(self, user_details, data=None, **keyw):
        sample_series = keyw.get("instance")
        super(SampleSeriesForm, self).__init__(data, **keyw)
        self.fields["samples"].queryset = \
            models.Sample.objects.filter(Q(series=sample_series) | Q(watchers=user_details)) if sample_series \
            else user_details.my_samples
        self.fields["samples"].widget.attrs.update({"size": "15", "style": "vertical-align: top"})
        self.fields["name"].widget.attrs.update({"size": "50"})
        if sample_series:
            self.fields["name"].widget.attrs.update({"readonly": "readonly"})
    class Meta:
        model = models.SampleSeries
        exclude = ("results", "timestamp")
    
@login_required
def edit(request, name):
    sample_series = get_object_or_404(models.SampleSeries, name=name) if name else None
    user_details = request.user.get_profile()
    if sample_series and sample_series.currently_responsible_person != request.user:
        return HttpResponseRedirect("permission_error")
    if request.method == "POST":
        sample_series_form = SampleSeriesForm(user_details, request.POST, instance=sample_series)
    else:
        sample_series_form = SampleSeriesForm(user_details, instance=sample_series)
    result_processes = utils.ResultContext(request.user, sample_series).collect_processes()
    title = _(u"Edit sample series “%s”" % sample_series.name) if sample_series else _(u"Create new sample series")
    return render_to_response("edit_sample_series.html", {"title": title,
                                                          "sample_series": sample_series_form,
                                                          "is_new": sample_series is None,
                                                          "name_prefix": u"%02d-%s" % (datetime.datetime.today().year % 100,
                                                                                       request.user.username),
                                                          "result_processes": result_processes},
                              context_instance=RequestContext(request))

