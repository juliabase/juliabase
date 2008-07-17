#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples.models import Sample
from django.contrib.auth.decorators import login_required

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
    sample = get_object_or_404(Sample, pk=sample_name)
    processes = []
    for process in sample.processes.all():
        process, title, body = digest_process(process)
        processes.append({"timestamp": process.timestamp, "title": title, "operator": process.operator,
                          "body": body})
    return render_to_response("show_sample.html", {"name": sample.name, "processes": processes},
                              context_instance=RequestContext(request))

