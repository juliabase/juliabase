#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Views with statistical data visualisation, and the “about” view.  So far, I
have only one comprehensive statistics page.  However, I need many helper
functions for it.
"""

from __future__ import absolute_import, division, unicode_literals

import pickle, time, datetime, re, locale, socket, shutil, subprocess, os, os.path
import memcache
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings
import django
from tools.common import Availability
from chantal_common import utils


backup_inspected_pattern = re.compile(r"Total number of objects inspected: *([0-9\,]+)")
backup_failed_pattern = re.compile(r"Total number of objects failed: *([0-9\,]+)")
def get_adsm_results(hostname):
    """Scans the logfile of the ADSM Tivoli client for the most recent
    successfull backup.

    :Parameters:
      - `hostname`: name of the node; may be ``mandy`` or ``olga``

    :type hostname: str

    :Return:
      dictionary with general information about the most recent Tivoli backup.

    :rtype: dict mapping str to unicode
    """
    result = {"log_file_error": False, "ispected_objects": None, "failed_objects": None, "last_backup_timestamp": None}
    tempfile_name = "/tmp/tivoli.log"
    if socket.gethostname() == hostname:
        shutil.copyfile("/tmp/adsm.sched.log", tempfile_name)
    else:
        other_ip = "192.168.26.130" if hostname == "mandy" else "192.168.26.131"
        returncode = subprocess.call(["rsync", "-az", other_ip + ":/tmp/adsm.sched.log", tempfile_name])
        if returncode != 0:
            result["log_file_error"] = True
            return result
    try:
        log_file = open(tempfile_name)
    except IOError:
        result["log_file_error"] = True
        return result
    in_record = False
    last_timestamp = None
    for line in log_file:
        if "--- SCHEDULEREC STATUS BEGIN" in line:
            try:
                timestamp = datetime.datetime.strptime(line[:19], "%m/%d/%y   %H:%M:%S")
            except ValueError:
                timestamp = datetime.datetime.strptime(line[:19], "%m/%d/%Y %H:%M:%S")
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
    os.remove(tempfile_name)
    return result


def get_availability_data():
    """Read the report file from the remote monitor program and generate a
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
        availability = pickle.load(open("/mnt/hobie/chantal_monitoring/remote_monitor.pickle", "rb"))
    except IOError:
        return None
    if not availability.start_of_log:
        return None
    result["start_date"] = utils.unicode_strftime(availability.start_of_log, _("%b %d, %Y, %H:%M"))
    accuracy = 100000000
    a = availability.availability
    a = int(round(a * accuracy))
    if availability.availability == accuracy:
        result["availability"] = _("100.0 %")
    else:
        result["availability"] = "{0} %".format(locale.str(a * 100 / accuracy))
    result["downtimes"] = []
    for interval in availability.downtime_intervals[-10:]:
        downtime = interval[1] - interval[0]
        minutes = int(round((downtime.seconds + downtime.days * 24 * 3600) / 60))
        from_ = utils.unicode_strftime(interval[0], _("%b %d, %Y, %H:%M"))
        if interval[0].date() == interval[1].date():
            to = utils.unicode_strftime(interval[1], _("%H:%M"))
        else:
            to = utils.unicode_strftime(interval[1], _("%b %d, %Y, %H:%M"))
        result["downtimes"].append(ungettext(
                "{from_} until {to} ({minutes} minute)",
                "{from_} until {to} ({minutes} minutes)", minutes).format(from_=from_, to=to, minutes=minutes))
    return result


logline_pattern = re.compile(r"(?P<date>[-0-9: ]+) (?P<type>[A-Z]+)\s+(?P<message>.*)")
"""Format of a line in the backup cron job's logfile."""
def analyze_last_database_backup():
    """Read the logfile of the backup cron job and generate a report about the
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
        logfile = open("/home/chantal/backups/postgresql/postgresql_backup.log")
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
                last_backup = _("successful, {timestamp}").format(timestamp=format_timestamp(timestamp))
            elif type_ == "INFO" and message.startswith("Database backups were successfully copied"):
                last_copy = _("successful, {timestamp}").format(timestamp=format_timestamp(timestamp))
            elif type_ == "ERROR" and message.startswith("Database dump failed"):
                last_backup = _("failed, {timestamp}").format(timestamp=format_timestamp(timestamp))
            elif type_ == "ERROR" and message.startswith("Copying of database tables to sonne failed"):
                last_copy = _("failed, {timestamp}").format(timestamp=format_timestamp(timestamp))
    if not last_backup:
        last_backup = _("no log data found")
    if not last_copy:
        last_copy = _("no log data found")
    return {"last_backup": last_backup, "last_copy": last_copy}


def get_cache_connections():
    """Returns the connections statistics of the memcached servers in the
    cluster.

    :Return:
      the total number of current memcached connections, the maximal number of
      current memcached connections, or ``(0, 0)`` if memcached is not used

    :rtype: int, int
    """
    if settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.memcached.MemcachedCache":
        memcached_client = memcache.Client(settings.CACHES["default"]["LOCATION"])
        servers = memcached_client.get_stats()
        number_of_servers = len(servers)
        connections = sum(int(server[1]["curr_connections"]) for server in servers)
    else:
        number_of_servers = 0
        connections = 0
    max_connections = 0
    try:
        for line in open("/etc/memcached.conf"):
            if line.startswith("-c"):
                max_connections = int(line.split()[1])
                break
        else:
            max_connections = 1024
    except:
        pass
    max_connections *= number_of_servers
    return connections, max_connections


def statistics(request):
    """View for various internal server statistics and plots.  Note that you
    needn't be logged in for accessing this.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return render_to_response("chantal_ipv/statistics.html",
                              {"title": _("Chantal server statistics"),
                               "adsm_results_mandy": get_adsm_results("mandy"),
                               "adsm_results_olga": get_adsm_results("olga"),
                               "availability": get_availability_data(),
                               "last_db_backup": analyze_last_database_backup(),
                               "cache_hit_rate": int(round((utils.cache_hit_rate() or 0) * 100)),
                               "cache_connections": get_cache_connections()},
                              context_instance=RequestContext(request))


def about(request):
    """The “about” view.  It displays general superficial information about
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
    short_messages = [_("Chantal revision {revision_number}").format(revision_number=settings.CHANTAL_REVNO)]
    django_version = django.get_version()
    return render_to_response("chantal_ipv/about.html",
                              {"title": _("Chantal is presented to you by …"),
                               "web_server_version": settings.APACHE_VERSION,
                               "is_testserver": settings.IS_TESTSERVER,
                               "db_version": settings.POSTGRESQL_VERSION,
                               "language_version": settings.PYTHON_VERSION,
                               "matplotlib_version": settings.MATPLOTLIB_VERSION,
                               "framework_version": django_version,
                               "short_messages": short_messages
                               },
                              context_instance=RequestContext(request))
