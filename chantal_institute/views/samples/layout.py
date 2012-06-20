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


"""
FixMe: Layout files should be taken from cache if appropriate.
"""

from __future__ import unicode_literals
import os.path, subprocess
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
from samples.views import utils
import chantal_common.utils
from chantal_institute import models
from chantal_institute import layouts


@login_required
def show_layout(request, process_id, sample_id):
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id))
    process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id)).actual_instance

    pdf_filename = "/tmp/layouts_{0}_{1}.pdf".format(process.id, sample.id)
    chantal_common.utils.mkdirs(pdf_filename)
    layout = layouts.get_layout(sample, process)
    if not layout:
        raise Http404(unicode("error"))
    canvas, resolution = layout.draw_layout(pdf_filename)
    canvas.showPage()
    canvas.save()

    png_filename = os.path.join(settings.CACHE_ROOT, "layouts", "{0}-{1}.png".format(process.id, sample.id))
    chantal_common.utils.mkdirs(png_filename)
    subprocess.check_call(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pngalpha", "-r{0}".format(resolution), "-dEPSCrop",
                             "-sOutputFile=" + png_filename, pdf_filename])
    return chantal_common.utils.static_file_response(png_filename)
