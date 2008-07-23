#!/usr/bin/env python
# -*- coding: utf-8 -*-

from chantal.samples import models
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.decorators import login_required

@login_required
def split_and_rename(request, process_id):
    process = models.Process.objects.get(pk=process_id)
    process_name = unicode(process)
    samples = process.samples.all()
    for sample in samples: print sample
    return render_to_response("split_and_rename.html", {"title": _("Bulk sample rename for %s") % process_name},
                              context_instance=RequestContext(request))
