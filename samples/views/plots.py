#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for editing and creating results (aka result processes).
"""

from __future__ import absolute_import

import datetime, os, os.path, re
from django.template import RequestContext
from django.http import Http404, HttpResponse
import django.forms as forms
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from django.db.models import Q
import chantal_common.utils
from chantal_common.utils import append_error
from samples import models, permissions
from samples.views import utils, form_utils, feed_utils, csv_export


@login_required
def show_plot(request, process_id, number):
    u"""Shows a particular plot.  Although its response is a bitmap rather than
    an HTML file, it is served by Django in order to enforce user permissions.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the database ID of the process to show
      - `number`: the number of the image.  This is mostly ``0`` because most
        measurement models have only one graphics.

    :type request: ``HttpRequest``
    :type process_id: unicode
    :type number: unicode

    :Returns:
      the HTTP response object with the image

    :rtype: ``HttpResponse``
    """
    process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id))
    process = process.find_actual_instance()
    permissions.assert_can_view_physical_process(request.user, process)
    number = int(number)
    plot_locations = process.calculate_plot_locations(number)
    response = HttpResponse()
    response["X-Sendfile"] = plot_locations["plot_file"]
    response["Content-Type"] = "application/pdf"
    response["Content-Length"] = os.path.getsize(plot_locations["plot_file"])
    response["Content-Disposition"] = 'attachment; filename="{0}.pdf"'.format(process.get_plotfile_basename(number))
    return response
