#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string, time
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples import models
from django.http import HttpResponsePermanentRedirect
import django.forms as forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.sites.models import Site
import django.contrib.auth.models
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
import django
from django.conf import settings
from . import utils

class MySeries(object):
    def __init__(self, sample_series):
        self.sample_series = sample_series
        self.name = sample_series.name
        self.timestamp = sample_series.timestamp
        self.samples = []
        self.__is_complete = None
    def append(self, sample):
        assert self.__is_complete is None
        self.samples.append(sample)
    @property
    def is_complete(self):
        if self.__is_complete is None:
            sample_series_length = self.sample_series.samples.count()
            assert sample_series_length >= len(self.samples)
            self.__is_complete = sample_series_length == len(self.samples)
        return self.__is_complete

@login_required
def main_menu(request):
    user_details = request.user.get_profile()
    my_series = {}
    seriesless_samples = []
    for sample in user_details.my_samples.all():
        containing_series = sample.series.all()
        if not containing_series:
            seriesless_samples.append(sample)
        else:
            for series in containing_series:
                if series.name not in my_series:
                    my_series[series.name] = MySeries(series)
                my_series[series.name].append(sample)
    my_series = sorted(my_series.itervalues(), key=lambda series: series.timestamp, reverse=True)
    return render_to_response("main_menu.html", {"title": _(u"Main menu"),
                                                 "my_series": my_series,
                                                 "seriesless_samples": seriesless_samples,
                                                 "username": request.user.username,
                                                 "user_hash": utils.get_user_hash(request.user)},
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

class SearchDepositionsForm(forms.Form):
    _ = ugettext_lazy
    number_pattern = forms.CharField(label=_(u"Deposition number pattern"), max_length=30)

max_results = 50
@login_required
def deposition_search(request):
    found_depositions = []
    too_many_results = False
    if request.method == "POST":
        search_depositions_form = SearchDepositionsForm(request.POST)
        if search_depositions_form.is_valid():
            found_depositions = \
                models.Deposition.objects.filter(number__icontains=search_depositions_form.cleaned_data["number_pattern"])
            too_many_results = found_depositions.count() > max_results
            found_depositions = found_depositions.all()[:max_results] if too_many_results else found_depositions.all()
            found_depositions = [deposition.find_actual_instance() for deposition in found_depositions]
    else:
        search_depositions_form = SearchDepositionsForm()
    return render_to_response("search_depositions.html", {"title": _(u"Search for deposition"),
                                                          "search_depositions": search_depositions_form,
                                                          "found_depositions": found_depositions,
                                                          "too_many_results": too_many_results,
                                                          "max_results": max_results},
                              context_instance=RequestContext(request))

@login_required
def show_deposition(request, deposition_number):
    deposition = get_object_or_404(models.Deposition, number=deposition_number).find_actual_instance()
    return HttpResponsePermanentRedirect("../" + deposition.get_show_url())
