#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples.models import Sample
import chantal.samples.models
from django.contrib.auth.decorators import login_required
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.sites.models import Site
from django import oldforms
from django.http import HttpResponseRedirect

def parse_session_data(request):
    result = {}
    for key in ["db_access_time_in_ms", "success_report"]:
        if key in request.session:
            result[key] = request.session[key]
            del request.session[key]
    return result
