# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""A view for log files of crawlers.
"""

import datetime, re, os.path, codecs
from django.http import Http404
from django.shortcuts import render
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils.translation import ugettext as _
import django.utils.timezone
from jb_common.utils.base import camel_case_to_underscores
from samples import permissions


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
    for i in range(start_index, len(lines)):
        content += lines[i][20:]
    return content, django.utils.timezone.make_aware(datetime.datetime.strptime(lines[start_index][:19], "%Y-%m-%d %H:%M:%S"))


@login_required
@require_http_methods(["GET"])
def view(request, process_class_name):
    """View for log files of crawlers.

    :param request: the current HTTP Request object
    :param process_class_name: the name of the crawler whose log file is about to be
        shown

    :type request: HttpRequest
    :type process_class_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    for process_class in permissions.get_all_addable_physical_process_models().keys():
        if camel_case_to_underscores(process_class.__name__) == process_class_name:
            break
    else:
        raise Http404("Process class not found.")
    try:
        logs_whitelist = set(settings.CRAWLER_LOGS_WHITELIST)
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

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    try:
        logs_whitelist = set(settings.CRAWLER_LOGS_WHITELIST)
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
