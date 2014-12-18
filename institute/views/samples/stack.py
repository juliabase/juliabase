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


"""View for showing an informal layer stack as a PDF file.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six

import subprocess
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template import defaultfilters
from django.utils.translation import ugettext as _
from samples import permissions
from samples.views import utils
import jb_common.utils
from jb_common.signals import storage_changed
from institute import models, informal_stacks


@login_required
def show_stack(request, sample_id, thumbnail):
    """Shows a particular informal layer stack.  Although its response is a bitmap
    rather than an HTML file, it is served by Django in order to enforce user
    permissions.

    :param request: the current HTTP Request object
    :param sample_id: the database ID of the sample
    :param thumbnail: whether we should deliver a thumbnail version

    :type request: HttpRequest
    :type process_id: unicode
    :type thumbnail: bool

    :return:
      the HTTP response object with the image

    :rtype: HttpResponse
    """
    sample_details = get_object_or_404(models.SampleDetails, pk=utils.convert_id_to_int(sample_id))
    sample = sample_details.sample
    permissions.get_sample_clearance(request.user, sample)
    if not sample_details.has_producible_stack_diagram():
        raise Http404("No stack diagram available.")
    locations = sample_details.get_stack_diagram_locations()
    filepath = locations["thumbnail_file" if thumbnail else "diagram_file"]
    if jb_common.utils.is_update_necessary(filepath, timestamps=[sample.last_modified]):
        jb_common.utils.mkdirs(filepath)
        if not thumbnail or jb_common.utils.is_update_necessary(locations["diagram_file"],
                                                                     timestamps=[sample.last_modified]):
            jb_common.utils.mkdirs(locations["diagram_file"])
            informal_stacks.generate_diagram(
                locations["diagram_file"], [informal_stacks.Layer(layer) for layer in sample_details.informal_layers.all()],
                six.text_type(sample), _("Layer stack of {0}").format(sample))
        if thumbnail:
            subprocess.call(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pngalpha", "-r100", "-dEPSCrop",
                             "-sOutputFile=" + locations["thumbnail_file"], locations["diagram_file"]])
        storage_changed.send(models.SampleDetails)
    return jb_common.utils.static_file_response(
        filepath, None if thumbnail else "{0}_stack.pdf".format(defaultfilters.slugify(six.text_type(sample))))
