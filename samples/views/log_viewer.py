#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""A view for log files of crawlers.
"""

from __future__ import absolute_import, unicode_literals

import datetime, re, os.path, codecs
from django.http import Http404
from django.shortcuts import render
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils.translation import ugettext as _
from samples import permissions
from samples.views.shared_utils import camel_case_to_underscores


start_pattern = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d INFO     started crawling")

def read_crawler_log(filepath):
    try:
        lines = codecs.open(filepath, encoding="utf-8").readlines()
    except IOError:
        return None, None
    start_index = len(lines) - 1
    while start_index >= 0 and not start_pattern.match(lines[start_index]):
        start_index -= 1
    if start_index < 0:
        return None, None
    content = ""
    for i in xrange(start_index, len(lines)):
        content += lines[i][20:]
    return content, datetime.datetime.strptime(lines[start_index][:19], "%Y-%m-%d %H:%M:%S")


@login_required
@require_http_methods(["GET"])
def view(request, process_class_name):
    """View for log files of crawlers.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_class_name`: the name of the crawler whose log file is about to be
        shown

    :type request: ``HttpRequest``
    :type process_class_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    for process_class in permissions.get_all_addable_physical_process_models().keys():
        if camel_case_to_underscores(process_class.__name__) == process_class_name:
            break
    else:
        raise Http404("Process class not found.")
    try:
        logs_whitelist = settings.CRAWLER_LOGS_WHITELIST
    except AttributeError:
        logs_whitelist = set()
    if process_class.__name__ not in logs_whitelist:
        permissions.assert_can_add_physical_process(request.user, process_class)
    assert "." not in process_class_name and "/" not in process_class_name
    filepath = os.path.join(settings.CRAWLER_LOGS_ROOT, process_class_name + ".log")
    log_content, log_timestamp = read_crawler_log(filepath)
    return render(request, "samples/log_viewer.html",
                  {"title": _("Log of crawler “{process_class_name}”").format(
                      process_class_name=process_class._meta.verbose_name_plural),
                   "log_content": log_content, "log_timestamp": log_timestamp})


@login_required
@require_http_methods(["GET"])
def list(request):
    """List all crawlers and link to their log files.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    try:
        logs_whitelist = settings.CRAWLER_LOGS_WHITELIST
    except AttributeError:
        logs_whitelist = set()
    crawlers = []
    for process_class in permissions.get_all_addable_physical_process_models().keys():
        if process_class.__name__ in logs_whitelist or \
                permissions.has_permission_to_add_physical_process(request.user, process_class):
            process_class_name = camel_case_to_underscores(process_class.__name__)
            filepath = os.path.join(settings.CRAWLER_LOGS_ROOT, process_class_name + ".log")
            if os.path.exists(filepath):
                crawlers.append((process_class._meta.verbose_name_plural, process_class_name))
    crawlers.sort()
    return render(request, "samples/list_crawlers.html", {"title": _("Crawler logs"), "crawlers": crawlers})
