#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string, time
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples import models
from django.contrib.auth.decorators import login_required
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.sites.models import Site
import django.contrib.auth.models
from django import oldforms
from django.utils.translation import ugettext as _, ungettext
import django
from django.conf import settings

@login_required
def main_menu(request):
    return render_to_response("main_menu.html", {"title": _(u"Main menu")},
                              context_instance=RequestContext(request))

def permission_error(request, failed_action):
    return render_to_response("permission_error.html", {"title": _(u"Access denied")},
                              context_instance=RequestContext(request))

def breakup_time(seconds):
    def test_timeunit(seconds, size_of_timeunit_in_seconds, translation_function, current_timeunit_list):
        size_of_timeunit_in_seconds = int(round(size_of_timeunit_in_seconds))
        number_of_timeunits = seconds // size_of_timeunit_in_seconds
        if number_of_timeunits:
            current_timeunit_list.append(translation_function(number_of_timeunits) % {"count": number_of_timeunits })
        return number_of_timeunits * size_of_timeunit_in_seconds
    current_timeunit_list = []
    seconds = int(round(seconds))

    chunks = ((365.2425*24*3600, lambda n: ungettext(u"%(count)d year", u"%(count)d years", n)),
              (30.436875*24*3600, lambda n: ungettext(u"%(count)d month", u"%(count)d months", n)),
              (7*24*3600, lambda n: ungettext(u"%(count)d week", u"%(count)d weeks", n)),
              (24*3600, lambda n: ungettext(u"%(count)d day", u"%(count)d days", n)),
              (3600, lambda n: ungettext(u"%(count)d hour", u"%(count)d hours", n)),
              (60, lambda n: ungettext(u"%(count)d minute", u"%(count)d minutes", n)),
              (1, lambda n: ungettext(u"%(count)d second", u"%(count)d seconds", n)),
              )
    for duration, translation_function in chunks:
        seconds -= test_timeunit(seconds, duration, translation_function, current_timeunit_list)
    assert not seconds
    if not current_timeunit_list:
        current_timeunit_list = [ungettext(u"%(count)d second", u"%(count)d seconds", 0) % {"count": 0 }]
    if len(current_timeunit_list) == 1:
        return current_timeunit_list[0]
    elif len(current_timeunit_list) == 2:
        return current_timeunit_list[0] + _(u" and ") + current_timeunit_list[1]
    else:
        return _(u", ").join(current_timeunit_list[:-1]) + _(u", and ") + current_timeunit_list[-1]

def about(request):
    short_messages = [_(u"Chantal revision %s") % settings.CHANTAL_REVNO]
    return render_to_response("about.html", {"title": _(u"Chantal is presented to you by …"),
                                             "web_server_version": settings.APACHE_VERSION,
                                             "is_testserver": settings.IS_TESTSERVER,
                                             "db_version": settings.MYSQL_VERSION,
                                             "language_version": settings.PYTHON_VERSION,
                                             "framework_version": django.get_version().replace("-SVN-unknown", ""),
                                             "short_messages": short_messages
                                             },
                              context_instance=RequestContext(request))

def statistics(request):
    web_server_uptime = \
        _(u"for %(time)s") % {"time": breakup_time(time.time()-settings.APACHE_STARTUP_TIME)}
    db_uptime = _(u"for %(time)s") % {"time": breakup_time(time.time()-settings.MYSQL_STARTUP_TIME)}
    os_uptime = float(open("/proc/uptime").read().split()[0])
    os_uptime = _(u"for %(time)s") % {"time": breakup_time(os_uptime)}
    return render_to_response("statistics.html", {"title": _(u"Chantal server statistics"),
                                                  "os_uptime": os_uptime,
                                                  "web_server_uptime": web_server_uptime,
                                                  "db_uptime": db_uptime},
                              context_instance=RequestContext(request))

@login_required
def show_user(request, login_name):
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    try:
        userdetails = user.get_profile()
    except models.UserDetails.DoesNotExist:
        userdetails = None
    username = user.get_full_name()
    if not username:
        username = user.username
    return render_to_response("show_user.html", {"title": username, "user": user, "userdetails": userdetails},
                              context_instance=RequestContext(request))

