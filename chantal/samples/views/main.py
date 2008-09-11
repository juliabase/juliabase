#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Model for the main menu view and some miscellaneous views that don't have a
better place to be (yet).
"""

import string, time, os, datetime, re
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples import models
from django.http import HttpResponsePermanentRedirect, HttpResponse, Http404
import django.forms as forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.sites.models import Site
import django.contrib.auth.models
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
import django
from django.conf import settings
from chantal.samples.views import utils
from chantal.samples.views.utils import help_link

class MySeries(object):
    u"""Helper class to pass sample series data to the main menu template.  It
    is used in `main_menu`.  This is *not* a data strcuture for sample series.
    It just stores all data needed to display a certain sample series to a
    certain user, besing on his groups an “My Samples”.

    :ivar sample_series: the sample series for which data should be collected
      in this object
    :ivar name: the name of the sample series
    :ivar timestamp: the creation timestamp of the sample series
    :ivar samples: all samples belonging to this sample series, *and* being
      part of “My Samples” of the current user
    :ivar is_complete: a read-only property.  If ``False``, there are samples
      in the sample series not included into the list because they were missing
      on “My Samples”.  In other words, the user deliberately gets an
      incomplete list of samples and should be informed about it.

    :type sample_series: `models.SampleSeries`
    :type name: unicode
    :type timestamp: ``datetime.datetime``
    :type samples: list of `models.Sample`
    :type is_complete: bool
    """
    def __init__(self, sample_series):
        self.sample_series = sample_series
        self.name = sample_series.name
        self.timestamp = sample_series.timestamp
        self.samples = []
        self.__is_complete = None
    def append(self, sample):
        u"""Adds a sample to this sample series view.

        :Parameters:
          - `sample`: the sample

        :type sample: `models.Sample`
        """
        assert self.__is_complete is None
        self.samples.append(sample)
    @property
    def is_complete(self):
        if self.__is_complete is None:
            sample_series_length = self.sample_series.samples.count()
            assert sample_series_length >= len(self.samples)
            self.__is_complete = sample_series_length == len(self.samples)
        return self.__is_complete

@help_link(_(u"MainMenu"))
@login_required
def main_menu(request):
    u"""The main menu view.  So far, it displays only the sample series in a
    dynamic way.  The rest is served static, which must be changed: The
    processes that are offered to you “for addition” must be according to your
    permissions for processes.  The same is true for “add samples” – this also
    is not allowed for everyone.
    
    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
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
    u"""This view is displayed if the user tries to request a URL for which he
    has no permission.  Typically, it is redirected to this view with a HTTP
    status 303 redirect, see for example `utils.lookup_sample`.
    
    :Parameters:
      - `request`: the current HTTP Request object
      - `failed_action`: the URL to the request that failed

    :type request: ``HttpRequest``
    :type failed_action: unicode

    :Returns:
      the HTTP response object with error 401 (not authorised).

    :rtype: `utils.HttpResponseUnauthorized`
    """
    return utils.HttpResponseUnauthorized(loader.render_to_string("permission_error.html", {"title": _(u"Access denied")},
                                                                  context_instance=RequestContext(request)))

def breakup_time(seconds):
    u"""Local helper routine for the `statistics` view.  It is used to
    calculate the uptime of Chantal components.

    :Parameters:
      - `seconds`: the number of seconds that should be expressed as a
        human-friendly string

    :type seconds: int

    :Return:
      a human-friendly string extressing the seconds in years, months, …, and
      seconds.

    :rtype: unicode
    """
    def test_timeunit(seconds, size_of_timeunit_in_seconds, translation_function, current_timeunit_list):
        u"""Calculates the number of time units that fit into the remaining
        seconds and generates a human-readable string for it.  For example,
        this function may be called for "weeks", and the seconds given
        correspond to 4 weeks and some more.  Then, the routine will append the
        string ``"4 weeks"`` to the output and return the remaining seconds
        (for becoming expressed in days, hours, minutes, and seconds).

        :Parameters:
          - `seconds`: the number of remaining seconds that should be expressed
            in a string
          - `size_of_timeunit_in_seconds`: in case of weeks, this would be
            3600·24·7.
          - `translation_function`: function to be called to generate the
            human-friendly string.  Typically, this is a wrapper around
            ``gettext.ungettext``.  This function must take exactly one
            parameter, namely an ``int`` containing the number of time units to
            be expressed.
          - `current_timeunit_list`: list with the so-far text snippets which,
            once neatly concatenated, form the final string.  This is the
            datastructure thatis created by subsequent calls of this function.

        :type seconds: int
        :type size_of_timeunit_in_seconds: int
        :type translation_function: func(int)
        :type current_timeunit_list: list of unicode

        :Return:
          the number of seconds that were “consumed” by this routine.

        :rtype: int
        """
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
    u"""The “about” view.  It displays general superficial information about
    Chantal.  This view is more or less static – it shows only the components
    of Chantal and versioning information.

    Note that you needn't be logged in for accessing this.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
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

backup_inspected_pattern = re.compile(r"Total number of objects inspected: *([0-9\,]+)")
backup_failed_pattern = re.compile(r"Total number of objects failed: *([0-9\,]+)")
def get_adsm_results():
    u"""Scans the logfile of the ADSM Tivoli client for the most recent
    successfull backup.

    :Return:
      dictionary with general information about the most recent Tivoli backup.

    :rtype: dict mapping str to unicode
    """
    result = {"log_file_error": False, "ispected_objects": None, "failed_objects": None, "last_backup_timestamp": None}
    try:
        log_file = open("/tmp/adsm.sched.log")
    except IOError:
        result["log_file_error"] = True
        return result
    in_record = False
    for line in log_file:
        if "--- SCHEDULEREC STATUS BEGIN" in line:
            timestamp = datetime.datetime.strptime(line[:19], "%m/%d/%y   %H:%M:%S")
            if timestamp.date() == datetime.date.today():
                result["last_backup_timestamp"] = \
                    timestamp.strftime(str(_("today, %H:%M")))
            elif timestamp.date() == datetime.date.today() - datetime.timedelta(1):
                result["last_backup_timestamp"] = \
                    timestamp.strftime(str(_("yesterday, %H:%M")))
            else:
                result["last_backup_timestamp"] = \
                    timestamp.strftime(str(_("%A, %b %d, %Y, %H:%M")))
            in_record = True
        elif "--- SCHEDULEREC STATUS END" in line:
            in_record = False
        elif in_record:
            match = backup_inspected_pattern.search(line)
            if match:
                result["ispected_objects"] = match.group(1).replace(",", "")
            match = backup_failed_pattern.search(line)
            if match:
                result["failed_objects"] = match.group(1).replace(",", "")
    log_file.close()
    return result

def statistics(request):
    u"""View for various internal server statistics and plots.  Note that you
    needn't be logged in for accessing this.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    web_server_uptime = \
        _(u"for %(time)s") % {"time": breakup_time(time.time()-settings.APACHE_STARTUP_TIME)}
    db_uptime = _(u"for %(time)s") % {"time": breakup_time(time.time()-settings.MYSQL_STARTUP_TIME)}
    os_uptime = float(open("/proc/uptime").read().split()[0])
    os_uptime = _(u"for %(time)s") % {"time": breakup_time(os_uptime)}
    return render_to_response("statistics.html", {"title": _(u"Chantal server statistics"),
                                                  "os_uptime": os_uptime,
                                                  "web_server_uptime": web_server_uptime,
                                                  "db_uptime": db_uptime,
                                                  "adsm_results": get_adsm_results()},
                              context_instance=RequestContext(request))

@login_required
def show_user(request, login_name):
    u"""View for showing basic information about a user, like phone number or
    email address.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    try:
        userdetails = user.get_profile()
    except models.UserDetails.DoesNotExist:
        userdetails = None
    username = models.get_really_full_name(user)
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
    return HttpResponsePermanentRedirect(deposition.get_absolute_url())
