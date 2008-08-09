#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404, HttpResponseRedirect
import django.forms as forms
from chantal.samples.models import Sample
from django.contrib.auth.decorators import login_required
from . import utils
from django.utils.translation import ugettext as _, ugettext_lazy

def collect_processes(process_context):
    processes = []
    split_origin = process_context.current_sample.split_origin
    if split_origin:
        processes.extend(collect_processes(process_context.split(split_origin)))
    for process in process_context.get_processes():
        processes.append(process_context.digest_process(process))
    return processes

class IsMySampleForm(forms.Form):
    is_my_sample = forms.BooleanField(label=_(u"is amongst My Samples"), required=False)

@login_required
def show(request, sample_name):
    start = time.time()
    lookup_result = utils.lookup_sample(sample_name)
    if lookup_result:
        return lookup_result
    user_details = request.user.get_profile()
    if request.method == "POST":
        is_my_sample_form = IsMySampleForm(request.POST)
        if is_my_sample_form.is_valid():
            if is_my_sample_form.cleaned_data["is_my_sample"]:
                user_details.my_samples.add(sample)
                request.session["success_report"] = _(u"Sample %s was added to Your Samples.") % sample_name
            else:
                user_details.my_samples.remove(sample)
                request.session["success_report"] = _(u"Sample %s was removed from Your Samples.") % sample_name
    else:
        # FixMe: DB access is probably not efficient
        start = time.time()
        is_my_sample_form = IsMySampleForm(initial={"is_my_sample": sample in user_details.my_samples.all()})
        request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    processes = collect_processes(utils.ProcessContext(request.user, sample))
    request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    return render_to_response("show_sample.html", {"processes": processes, "sample": sample,
                                                   "is_my_sample_form": is_my_sample_form},
                              context_instance=RequestContext(request))
