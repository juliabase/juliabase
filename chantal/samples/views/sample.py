#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string, time
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

def digest_process(process):
    process = process.find_actual_process()
    template = loader.get_template("show_"+camel_case_to_underscores(process.__class__.__name__)+".html")
    return process, process._meta.verbose_name, template.render(Context({"process": process}))

def collect_processes(sample, cutoff_timestamp=None):
    processes = []
    split_origin = sample.split_origin
    if split_origin:
        processes.extend(collect_processes(split_origin.parent, split_origin.timestamp))
    if cutoff_timestamp:
        processes_query = sample.processes.filter(timestamp__lte=cutoff_timestamp)
    else:
        processes_query = sample.processes.all()
    for process in processes_query:
        process, title, body = digest_process(process)
        title = unicode(title)
        title = title[0].upper() + title[1:]
        processes.append({"timestamp": process.timestamp, "title": title, "operator": process.operator,
                          "body": body})
    return processes
    
@login_required
def show(request, sample_name):
    start = time.time()
    sample = utils.get_sample(sample_name)
    if not sample:
        raise Http404(_("Sample %s could not be found (neither as an alias).") % sample_name)
    if not request.user.has_perm("samples.view_sample") and sample.group not in request.user.groups.all() \
            and sample.currently_responsible_person != request.user:
        return HttpResponseRedirect("permission_error")
    processes = collect_processes(sample)
    request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    return render_to_response("show_sample.html",
                              {"processes": processes, "sample": sample},
                              context_instance=RequestContext(request))

