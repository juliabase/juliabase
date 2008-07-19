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
from django.utils.translation import ugettext_lazy as _

@login_required
def main_menu(request):
    return render_to_response("main_menu.html", {"title": _("Main menu")},
                              context_instance=RequestContext(request))

def permission_error(request, failed_action):
    return render_to_response("permission_error.html", {"title": _("Access denied")},
                              context_instance=RequestContext(request))

def login(request, redirect_field_name=REDIRECT_FIELD_NAME):
    "Displays the login form and handles the login action."
    manipulator = AuthenticationForm()
    redirect_to = request.REQUEST.get(redirect_field_name, '')
    if request.POST:
        errors = manipulator.get_validation_errors(request.POST)
        if not errors:
            # Light security check -- make sure redirect_to isn't garbage.
            if not redirect_to or '//' in redirect_to or ' ' in redirect_to:
                from django.conf import settings
                redirect_to = settings.LOGIN_REDIRECT_URL
            from django.contrib.auth import login
            user = manipulator.get_user()
            login(request, user)
            try:
                request.session["django_language"] = user.get_profile().language
            except chantal.samples.models.UserDetails.DoesNotExist:
                pass
            if request.session.test_cookie_worked():
                request.session.delete_test_cookie()
            return HttpResponseRedirect(redirect_to)
    else:
        errors = {}
    request.session.set_test_cookie()

    if Site._meta.installed:
        current_site = Site.objects.get_current()
    else:
        current_site = RequestSite(request)

    return render_to_response("login.html", {
        'form': oldforms.FormWrapper(manipulator, request.POST, errors),
        redirect_field_name: redirect_to,
        'site_name': current_site.name,
    }, context_instance=RequestContext(request))
