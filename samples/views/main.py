#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string, time
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
from django.utils.translation import ugettext, ungettext
import django
from django.conf import settings

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

def breakup_time(seconds):
    def test_timeunit(seconds, size_of_timeunit_in_seconds, translation_function, current_timeunit_list):
        size_of_timeunit_in_seconds = int(round(size_of_timeunit_in_seconds))
        number_of_timeunits = seconds // size_of_timeunit_in_seconds
        if number_of_timeunits:
            current_timeunit_list.append(translation_function(number_of_timeunits) % {"count": number_of_timeunits })
        return number_of_timeunits * size_of_timeunit_in_seconds
    current_timeunit_list = []
    seconds = int(round(seconds))

    chunks = ((365.2425*24*3600, lambda n: ungettext("%(count)d year", "%(count)d years", n)),
              (30.436875*24*3600, lambda n: ungettext("%(count)d month", "%(count)d months", n)),
              (7*24*3600, lambda n: ungettext("%(count)d week", "%(count)d weeks", n)),
              (24*3600, lambda n: ungettext("%(count)d day", "%(count)d days", n)),
              (3600, lambda n: ungettext("%(count)d hour", "%(count)d hours", n)),
              (60, lambda n: ungettext("%(count)d minute", "%(count)d minutes", n)),
              (1, lambda n: ungettext("%(count)d second", "%(count)d seconds", n)),
              )
    for duration, translation_function in chunks:
        seconds -= test_timeunit(seconds, duration, translation_function, current_timeunit_list)
    assert not seconds
    if not current_timeunit_list:
        current_timeunit_list = [ungettext("%(count)d second", "%(count)d seconds", 0) % {"count": 0 }]
    if len(current_timeunit_list) == 1:
        return current_timeunit_list[0]
    else:
        _ = ugettext
        return _(", ").join(current_timeunit_list[:-1]) + _(", and ") + current_timeunit_list[-1]

def about(request):
    web_server_uptime = \
        _("up and running for %(time)s") % { "time": breakup_time(time.time()-settings.APACHE_STARTUP_TIME)}
    os_uptime = float(open("/proc/uptime").read().split()[0])
    os_uptime = _("up and running for %(time)s") % { "time": breakup_time(os_uptime)}
    return render_to_response("about.html", {"title": _(u"Chantal is presented to you by …"),
                                             "os_uptime": os_uptime,
                                             "web_server_version": settings.APACHE_VERSION,
                                             "web_server_uptime": web_server_uptime,
                                             "db_version": settings.MYSQL_VERSION,
                                             "language_version": settings.PYTHON_VERSION,
                                             "framework_version": django.get_version(),
                                             },
                              context_instance=RequestContext(request))
