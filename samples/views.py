#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
import models

def show_sample(request, sample_name):
    sample = get_object_or_404(models.Sample, pk=sample_name)
    processes = []
    for process in sample.processes.all():
        processes.append({"timestamp": process.timestamp, "title": process.__class__.__name__})
    return render_to_response("show_sample.html", {"name": sample.name, "processes": processes})
