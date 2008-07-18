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

def db_access_time(request):
    """
    Returns context variables required by apps that use Django's authentication
    system.

    If there is no 'user' attribute in the request, uses AnonymousUser (from
    django.contrib.auth).
    """
    if "db_access_time_in_ms" in request.session:
        db_access_time_in_ms = request.session["db_access_time_in_ms"]
        del request.session["db_access_time_in_ms"]
        return {"db_access_time_in_ms": db_access_time_in_ms}
    else:
        return {}
