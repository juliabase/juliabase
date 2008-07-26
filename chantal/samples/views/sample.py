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

@login_required
def show(request, sample_name):
    start = time.time()
    sample = utils.get_sample(sample_name)
    if not sample:
        raise Http404(_("Sample %s could not be found (neither as an alias).") % sample_name)
    if not request.user.has_perm("samples.view_sample") and sample.group not in request.user.groups.all() \
            and sample.currently_responsible_person != request.user:
        return HttpResponseRedirect("permission_error")
    processes = []
    for process in sample.processes.all():
        process, title, body = digest_process(process)
        processes.append({"timestamp": process.timestamp, "title": title, "operator": process.operator,
                          "body": body})
    request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    return render_to_response("show_sample.html",
                              {"title": _(u"History of sample “%s”") % sample.name, "processes": processes},
                              context_instance=RequestContext(request))

