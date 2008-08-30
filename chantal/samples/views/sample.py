#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404, HttpResponseRedirect
import django.forms as forms
from chantal.samples.models import Sample
from chantal.samples import models
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from . import utils
from django.utils.translation import ugettext as _, ugettext_lazy

class IsMySampleForm(forms.Form):
    _ = ugettext_lazy
    is_my_sample = forms.BooleanField(label=_(u"is amongst My Samples"), required=False)

class SampleForm(forms.ModelForm):
    _ = ugettext_lazy
    currently_responsible_person = utils.OperatorChoiceField(label=_(u"Currently responsible person"),
                                                             queryset=django.contrib.auth.models.User.objects.all())
    class Meta:
        model = models.Sample
        exclude = ("name", "split_origin", "processes")

@login_required
def edit(request, sample_name):
    sample, redirect = utils.lookup_sample(sample_name, request)
    if redirect:
        return redirect
    old_group, old_responsible_person = sample.group, sample.currently_responsible_person
    if sample.currently_responsible_person != request.user:
        return HttpResponseRedirect("permission_error")
    user_details = request.user.get_profile()
    if request.method == "POST":
        sample_form = SampleForm(request.POST, instance=sample)
        if sample_form.is_valid():
            sample = sample_form.save()
            if sample.group and sample.group != old_group:
                for user in sample.group.user_set.all():
                    user.get_profile().my_samples.add(sample)
            if sample.currently_responsible_person != old_responsible_person:
                sample.currently_responsible_person.get_profile().my_samples.add(sample)
            request.session["success_report"] = _(u"Sample %s was successfully changed in the database.") % sample.name
            return HttpResponseRedirect(
                "../../" + utils.parse_query_string(request).get("next", "samples/%s" % utils.name2url(sample.name)))
    else:
        sample_form = SampleForm(instance=sample)
    return render_to_response("edit_sample.html", {"title": _(u"Edit sample “%s”") % sample.name,
                                                   "sample_name": sample.name, "sample": sample_form},
                              context_instance=RequestContext(request))

def get_allowed_processes(user, sample):
    processes = []
    processes.extend(utils.get_allowed_result_processes(user, samples=[sample]))
    if sample.currently_responsible_person == user:
        processes.append({"name": _(u"split"), "link": "split/%s" % utils.name2url(sample.name)})
        # FixMe: Add sample death
    # FixMe: Add other processes, deposition, measurements, if the user is allowed to do it
    return processes

@login_required
def show(request, sample_name):
    start = time.time()
    sample, redirect = utils.lookup_sample(sample_name, request)
    if redirect:
        return redirect
    user_details = request.user.get_profile()
    if request.method == "POST":
        is_my_sample_form = IsMySampleForm(request.POST)
        if is_my_sample_form.is_valid():
            if is_my_sample_form.cleaned_data["is_my_sample"]:
                user_details.my_samples.add(sample)
                request.session["success_report"] = _(u"Sample %s was added to Your Samples.") % sample.name
            else:
                user_details.my_samples.remove(sample)
                request.session["success_report"] = _(u"Sample %s was removed from Your Samples.") % sample.name
    else:
        start = time.time()
        is_my_sample_form = IsMySampleForm(initial={"is_my_sample": sample in user_details.my_samples.all()})
        request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    processes = utils.ProcessContext(request.user, sample).collect_processes()
    request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    return render_to_response("show_sample.html", {"processes": processes, "sample": sample,
                                                   "can_edit": request.user == sample.currently_responsible_person,
                                                   # FixMe: calling get_allowed_processes is too expensive
                                                   "can_add_process": bool(get_allowed_processes(request.user, sample)),
                                                   "is_my_sample_form": is_my_sample_form},
                              context_instance=RequestContext(request))

@login_required
def add_process(request, sample_name):
    sample, redirect = utils.lookup_sample(sample_name, request)
    if redirect:
        return redirect
    user_details = request.user.get_profile()
    processes = get_allowed_processes(request.user, sample)
    if not processes:
        return HttpResponseRedirect("permission_error")
    return render_to_response("add_process.html",
                              {"title": _(u"Add process to sample “%s”" % sample.name),
                               "processes": processes,
                               "query_string": "sample=%s&next=samples/%s" % (sample_name, utils.name2url(sample_name))},
                              context_instance=RequestContext(request))
