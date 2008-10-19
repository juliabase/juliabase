#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Model for the main menu view and some miscellaneous views that don't have a
better place to be (yet).
"""

from __future__ import division
import string, time, os, datetime, re, pickle, locale
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples import models
from django.http import HttpResponsePermanentRedirect, HttpResponse, Http404
import django.forms as forms
from django.contrib.auth.decorators import login_required
import django.contrib.auth
from django.contrib.auth.forms import AuthenticationForm
import django.contrib.auth.models
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
import django
from django.conf import settings
from django.views.decorators.cache import cache_page, never_cache
from chantal.samples.views import utils
from chantal.samples.views.utils import help_link
from chantal.samples.views import permissions
from chantal.common import Availability

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
    user_details = utils.get_profile(request.user)
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

@cache_page(3600)
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
    last_timestamp = None
    for line in log_file:
        if "--- SCHEDULEREC STATUS BEGIN" in line:
            timestamp = datetime.datetime.strptime(line[:19], "%m/%d/%y   %H:%M:%S")
            if timestamp.date() == datetime.date.today():
                last_timestamp = timestamp.strftime(str(_("today, %H:%M")))
            elif timestamp.date() == datetime.date.today() - datetime.timedelta(1):
                last_timestamp = timestamp.strftime(str(_("yesterday, %H:%M")))
            else:
                last_timestamp = timestamp.strftime(str(_("%A, %b %d, %Y, %H:%M")))
            in_record = True
        elif "--- SCHEDULEREC STATUS END" in line:
            in_record = False
        elif in_record:
            match = backup_inspected_pattern.search(line)
            if match:
                result["ispected_objects"] = match.group(1).replace(",", "")
                result["last_backup_timestamp"] = last_timestamp
            match = backup_failed_pattern.search(line)
            if match:
                result["failed_objects"] = match.group(1).replace(",", "")
    log_file.close()
    return result

def get_availability_data():
    u"""Read the report file from the remote monitor program and generate a
    succinct report from it.  The remote monitor is a small program called
    ``remote_monitor.py`` which tries to login into the database every minute.
    Its successes and failures are logged in a pickle file.  This is read here
    and analysed.

    :Return:
      a dict with two keys: ``"availability"`` and ``"downtimes"``.  The first
      maps to a string describing the overall availability of the Chntal
      service, he latter maps to a list of strings describing all downtime
      intervals.

    :rtype: dict mapping str to unicode and list of unicode
    """
    result = {}
    try:
        availability = pickle.load(open("/home/www-data/online/remote_monitor.pickle", "rb"))
    except IOError:
        return None
    result["start_date"] = availability.start_of_log.strftime(str(_("%b %d, %Y, %H:%M")))
    accuracy = 100000000
    a = availability.availability
    a = int(round(a * accuracy))
    if availability.availability == accuracy:
        result["availability"] = _(u"100.0 %")
    else:
        result["availability"] = u"%s %%" % locale.str(a*100 / accuracy)
    result["downtimes"] = []
    for interval in availability.downtime_intervals[-10:]:
        minutes = int(round((interval[1] - interval[0]).seconds / 60))
        from_ = interval[0].strftime(str(_("%b %d, %Y, %H:%M")))
        if interval[0].date() == interval[1].date():
            to = interval[1].strftime(str(_("%H:%M")))
        else:
            to = interval[1].strftime(str(_("%b %d, %Y, %H:%M")))
        result["downtimes"].append(ungettext(u"%(from)s until %(to)s (%(minutes)d minute)",
                                             u"%(from)s until %(to)s (%(minutes)d minutes)", minutes) %
                                   {"from": from_, "to": to, "minutes": minutes})
    return result

logline_pattern = re.compile(r"(?P<date>[-0-9: ]+) (?P<type>[A-Z]+)\s+(?P<message>.*)")
u"""Format of a line in the backup cron job's logfile."""
def analyze_last_database_backup():
    u"""Read the logfile of the backup cron job and generate a report about the
    last backup tried (when it was made, whether it was successful or not).

    :Return:
      a dict with the two keys ``"last_backup"`` and ``"last_copy"``.  The
      first maps to a description of the last backup tried, the latter to a
      description about the last copy to the server “sonne” tried.  It may also
      be ``None`` is no logfile was found.

    :rtype: dict mapping str to unicode, or ``NoneType``
    """
    def format_timestamp(timestamp):
        if timestamp.date() == datetime.date.today():
            return timestamp.strftime(str(_("%H:%M today")))
        elif timestamp.date() == datetime.date.today() - datetime.timedelta(1):
            return timestamp.strftime(str(_("%H:%M yesterday")))
        else:
            return timestamp.strftime(str(_("%A, %b %d, %Y, %H:%M")))
    try:
        logfile = open("/home/www-data/backups/mysql/mysql_backup.log")
    except IOError:
        return None
    last_backup = last_copy = None
    for line in logfile:
        match = logline_pattern.match(line.strip())
        if match:
            timestamp = datetime.datetime.strptime(match.group("date"), "%Y-%m-%d %H:%M:%S")
            type_ = match.group("type")
            message = match.group("message")
            if type_ == "INFO" and message.startswith("Database dump was successfully created"):
                last_backup = _(u"successful, %s") % format_timestamp(timestamp)
            elif type_ == "INFO" and message.startswith("Database backups were successfully copied"):
                last_copy = _(u"successful, %s") % format_timestamp(timestamp)
            elif type_ == "ERROR" and message.startswith("Database dump failed"):
                last_backup = _(u"failed, %s") % format_timestamp(timestamp)
            elif type_ == "ERROR" and message.startswith("Copying of database tables to sonne failed"):
                last_copy = _(u"failed, %s") % format_timestamp(timestamp)
    if not last_backup:
        last_backup = _(u"no log data found")
    if not last_copy:
        last_copy = _(u"no log data found")
    return {"last_backup": last_backup, "last_copy": last_copy}

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
                                                  "adsm_results": get_adsm_results(),
                                                  "availability": get_availability_data(),
                                                  "last_db_backup": analyze_last_database_backup()},
                              context_instance=RequestContext(request))

class SearchDepositionsForm(forms.Form):
    u"""Tiny form class that just allows to enter a pattern for the deposition
    search.  Currently, the search is case-insensitive, and arbitrary parts of
    the deposition number are matched.
    """
    _ = ugettext_lazy
    number_pattern = forms.CharField(label=_(u"Deposition number pattern"), max_length=30)

max_results = 50
u"""Maximal number of search results to be displayed."""
@login_required
def deposition_search(request):
    u"""View for search for depositions.  Currently, this search is very
    rudimentary: It is only possible to search for substrings in deposition
    numbers.  Sometime this should be expanded for a more fine-grained search,
    possibly with logical operators between the search criteria.

    Note this this view is used for both getting the search request from the
    user *and* displaying the search results.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
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
    u"""View for showing depositions by deposition number, no matter which type
    of deposition they are.  It is some sort of dispatch view, which
    immediately redirecty to the actual deposition view.  Possibly it is
    superfluous, or at least only sensible to users who enter URL addresses
    directly.
    
    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: the number of the deposition to be displayed

    :type request: ``HttpRequest``
    :type deposition_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    deposition = get_object_or_404(models.Deposition, number=deposition_number).find_actual_instance()
    return HttpResponsePermanentRedirect(deposition.get_absolute_url())

@login_required
@never_cache
def primary_keys(request):
    u"""Generate a pickle document in plain text (*no* HTML!) containing
    mappings of names of database objects to primary keys.  While this can be
    used by everyone by entering the URL directly, this view is intended to be
    used only by the remote client program to get primary keys.  The reason for
    this is simple: In forms, you have to give primary keys in POST data sent
    to the web server.  However, a priori, the remote client doesn't know
    them.  Therefore, it can query this view to get them.

    The syntax of the query string to be appended to the URL is very simple.
    If you say::

        ...?samples=01B410,01B402

    you get the primary keys of those two samples::

        {"samples": {"01B410": 5, "01B402": 42}}

    The same works for ``"groups"`` and ``"users"``.  You can also mix all tree
    in the query string.  If you pass ``"*"`` instead of a values list, you get
    *all* primary keys.  For samples, however, this is limited to “My Samples”.

    The result is a pickled representation of the resulting nested dictionary.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    query_dict = utils.parse_query_string(request)
    result_dict = {}
    if "groups" in query_dict:
        if query_dict["groups"] == "*":
            result_dict["groups"] = dict(django.contrib.auth.models.Group.objects.values_list("name", "id"))
        else:
            groupnames = query_dict["groups"].split(",")
            result_dict["groups"] = dict(django.contrib.auth.models.Group.objects.filter(name__in=groupnames).
                                         values_list("name", "id"))
    if "samples" in query_dict:
        if query_dict["samples"] == "*":
            result_dict["samples"] = dict(utils.get_profile(request.user).my_samples.values_list("name", "id"))
        else:
            sample_names = query_dict["samples"].split(",")
            result_dict["samples"] = dict(models.Sample.objects.filter(name__in=sample_names).values_list("name", "id"))
    if "users" in query_dict:
        if query_dict["users"] == "*":
            result_dict["users"] = dict(django.contrib.auth.models.User.objects.values_list("username", "id"))
        else:
            user_names = query_dict["users"].split(",")
            # FixMe: Return only *active* users
            result_dict["users"] = dict(django.contrib.auth.models.User.objects.filter(username__in=user_names).
                                        values_list("username", "id"))
    return utils.respond_to_remote_client(result_dict)

def login_remote_client(request):
    u"""Login for the Chantal Remote Client.  It only supports the HTTP POST
    method and expects ``username`` and ``password``.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object.  It is a pickled boolean object, whether the
      login was successful or not.

    :rtype: ``HttpResponse``
    """
    try:
        username = request.POST["username"]
        password = request.POST["password"]
    except KeyError:
        return utils.respond_to_remote_client(False)
    user = django.contrib.auth.authenticate(username=username, password=password)
    if user is not None and user.is_active:
        django.contrib.auth.login(request, user)
        return utils.respond_to_remote_client(True)
    return utils.respond_to_remote_client(False)

def logout_remote_client(request):
    u"""By requesting this view, the Chantal Remote Client can log out.  This
    view can never fail.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object.  It is a pickled boolean object and always
      ``True``.

    :rtype: ``HttpResponse``
    """
    django.contrib.auth.logout(request)
    return utils.respond_to_remote_client(True)

def next_deposition_number(request, letter):
    u"""Send the next free deposition number to the Chantal Remote Client.  It
    only supports the HTTP POST method and expects ``username`` and
    ``password``.

    :Parameters:
      - `request`: the current HTTP Request object
      - `letter`: the letter of the deposition system, see
        `utils.get_next_deposition_number`.

    :type request: ``HttpRequest``
    :type letter: str

    :Returns:
      the next free deposition number for the given apparatus.

    :rtype: ``HttpResponse``
    """
    return utils.respond_to_remote_client(utils.get_next_deposition_number(letter))

@login_required
def switch_language(request):
    u"""This view parses the query string and extracts a language code from it,
    then switches the current user's prefered language to that language, and
    then goes back to the last URL.  This is used for realising the language
    switching by the flags on the top left.
    
    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    query_dict = utils.parse_query_string(request)
    language = query_dict.get("lang")
    if language in dict(models.languages):
        user_details = utils.get_profile(request.user)
        user_details.language = language
        user_details.save()
    return utils.successful_response(request)
