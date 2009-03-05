#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views with statistical data visualisation, and the “about” view.  So far, I
have only one comprehensive statistics page.  However, I need many helper
functions for it.
"""

from __future__ import division
import pickle, time, datetime, re, locale
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings
import django
from chantal.common import Availability
from chantal.samples.views import utils


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
                last_timestamp = utils.unicode_strftime(timestamp, _("today, %H:%M"))
            elif timestamp.date() == datetime.date.today() - datetime.timedelta(1):
                last_timestamp = utils.unicode_strftime(timestamp, _("yesterday, %H:%M"))
            else:
                last_timestamp = utils.unicode_strftime(timestamp, _("%A, %b %d, %Y, %H:%M"))
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
    result["start_date"] = utils.unicode_strftime(availability.start_of_log, _("%b %d, %Y, %H:%M"))
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
        from_ = utils.unicode_strftime(interval[0], _("%b %d, %Y, %H:%M"))
        if interval[0].date() == interval[1].date():
            to = utils.unicode_strftime(interval[1], _("%H:%M"))
        else:
            to = utils.unicode_strftime(interval[1], _("%b %d, %Y, %H:%M"))
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
            return utils.unicode_strftime(timestamp, _("%H:%M today"))
        elif timestamp.date() == datetime.date.today() - datetime.timedelta(1):
            return utils.unicode_strftime(timestamp, _("%H:%M yesterday"))
        else:
            return utils.unicode_strftime(timestamp, _("%A, %b %d, %Y, %H:%M"))
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
            # FixMe: It should only save the last timestamp and generate the
            # message string after the loop.
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
                                             "matplotlib_version": settings.MATPLOTLIB_VERSION,
                                             "framework_version": django.get_version().replace("-SVN-unknown", ""),
                                             "short_messages": short_messages
                                             },
                              context_instance=RequestContext(request))

