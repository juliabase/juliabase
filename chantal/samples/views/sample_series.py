#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples import models
from django.forms import ModelForm, Form
from django.utils.translation import ugettext as _, ugettext_lazy
from . import utils

class SampleSeriesForm(ModelForm):
    _ = ugettext_lazy
    def __init__(self, *args, **keyw):
        super(SampleSeriesForm, self).__init__(*args, **keyw)
        self.fields["name"].widget.attrs.update({"readonly": "readonly"})
        self.fields["timestamp"].widget.attrs.update({"readonly": "readonly"})
    class Meta:
        model = models.SampleSeries
        exclude = ("results",)
    
@login_required
def edit(request, name):
    sample_series = get_object_or_404(models.SampleSeries, name=name) if name else None
    if request.method == "POST":
        sample_series_form = SampleSeriesForm(request.POST, instance=sample_series)
    else:
        sample_series_form = SampleSeriesForm(instance=sample_series)
    result_processes = utils.ResultContext(request.user, sample_series).collect_processes()
    return render_to_response("edit_sample_series.html", {"sample_series": sample_series_form,
                                                          "result_processes": result_processes})
