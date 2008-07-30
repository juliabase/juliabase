#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string, time, copy
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response
from django.http import Http404, HttpResponseRedirect
import django.forms as forms
from chantal.samples.models import Sample
from django.contrib.auth.decorators import login_required
from . import utils
from django.utils.translation import ugettext as _, ugettext_lazy

def camel_case_to_underscores(name):
    result = []
    for i, character in enumerate(name):
        if i == 0:
            result.append(character.lower())
        elif character in string.ascii_uppercase:
            result.extend(("_", character.lower()))
        else:
            result.append(character)
    return "".join(result)

class ProcessContext(object):
    def __init__(self, original_sample):
        self.original_sample = self.current_sample = original_sample
        self.__process = self.cutoff_timestamp = self.html_body = None
    def __set_process(self, process):
        self.__process = process.find_actual_process()
    process = property(lambda self: self.__process, __set_process)
    def split(self, split):
        result = copy.copy(self)
        result.current_sample = split.parent
        result.cutoff_timestamp = split.timestamp
        return result
    def get_template_context(self):
        context_dict = {"process": self.__process}
        if hasattr(self.__process, "get_additional_template_context"):
            context_dict.update(self.__process.get_additional_template_context(self))
        return Context(context_dict)
    def get_processes(self):
        if self.cutoff_timestamp is None:
            return self.current_sample.processes.all()
        else:
            return self.current_sample.processes.filter(timestamp__lte=self.cutoff_timestamp)
    def digest_process(self, process):
        self.process = process
        template = loader.get_template("show_" + camel_case_to_underscores(self.__process.__class__.__name__) + ".html")
        name = unicode(self.__process._meta.verbose_name)
        return {"name": name[0].upper()+name[1:], "operator": self.__process.operator,
                "timestamp": self.__process.timestamp, "html_body": template.render(self.get_template_context())}

def collect_processes(process_context):
    processes = []
    split_origin = process_context.current_sample.split_origin
    if split_origin:
        processes.extend(collect_processes(process_context.split(split_origin)))
    for process in process_context.get_processes():
        processes.append(process_context.digest_process(process))
    return processes

class IsMySampleForm(forms.Form):
    is_my_sample = forms.BooleanField(label=_(u"is amongst my samples"), required=False)

@login_required
def show(request, sample_name):
    sample = utils.get_sample(sample_name)
    if not sample:
        raise Http404(_(u"Sample %s could not be found (neither as an alias).") % sample_name)
    if not request.user.has_perm("samples.view_sample") and sample.group not in request.user.groups.all() \
            and sample.currently_responsible_person != request.user:
        return HttpResponseRedirect("permission_error")
    user_profile = request.user.get_profile()
    if request.method == "POST":
        is_my_sample_form = IsMySampleForm(request.POST)
        if is_my_sample_form.is_valid():
            if is_my_sample_form.cleaned_data["is_my_sample"]:
                user_profile.my_samples.add(sample)
                request.session["success_report"] = _(u"Sample %s was added to Your Samples.") % sample_name
            else:
                user_profile.my_samples.remove(sample)
                request.session["success_report"] = _(u"Sample %s was removed from Your Samples.") % sample_name
    else:
        # FixMe: DB access is probably not efficient
        start = time.time()
        is_my_sample_form = IsMySampleForm(initial={"is_my_sample": sample in user_profile.my_samples.all()})
        request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    processes = collect_processes(ProcessContext(sample))
    return render_to_response("show_sample.html", {"processes": processes, "sample": sample,
                                                   "is_my_sample_form": is_my_sample_form},
                              context_instance=RequestContext(request))

