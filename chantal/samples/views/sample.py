#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string, time, copy
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response
from django.http import Http404, HttpResponseRedirect
from chantal.samples.models import Sample
from django.contrib.auth.decorators import login_required
from . import utils

from django.utils.translation import ugettext_lazy as _

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
    
@login_required
def show(request, sample_name):
    start = time.time()
    sample = utils.get_sample(sample_name)
    if not sample:
        raise Http404(_(u"Sample %s could not be found (neither as an alias).") % sample_name)
    if not request.user.has_perm("samples.view_sample") and sample.group not in request.user.groups.all() \
            and sample.currently_responsible_person != request.user:
        return HttpResponseRedirect("permission_error")
    processes = collect_processes(ProcessContext(sample))
    request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    return render_to_response("show_sample.html", {"processes": processes, "sample": sample},
                              context_instance=RequestContext(request))

