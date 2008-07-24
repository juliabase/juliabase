#!/usr/bin/env python
# -*- coding: utf-8 -*-

from chantal.samples import models
from django.template import RequestContext
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.decorators import login_required

def has_permission_for_process(request, process):
    return "samples.change_" + process.find_actual_process().__class__.__name__.lower() in request.user.get_all_permissions()

@login_required
def split_and_rename(request, process_id):
    process = get_object_or_404(models.Process, pk=process_id)
    print "change_" + process.find_actual_process().__class__.__name__.lower()
    if not has_permission_for_process(request, process):
        return HttpResponseRedirect("permission_error")
    process_name = unicode(process)
    samples = process.samples.all()
    return render_to_response("split_and_rename.html", {"title": _("Bulk sample rename for %s") % process_name},
                              context_instance=RequestContext(request))
