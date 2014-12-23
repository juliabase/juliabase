#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


# FixMe: Layout files should be taken from cache if appropriate.

from __future__ import unicode_literals, absolute_import, division

import os.path, subprocess
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
import jb_common.utils.base
import samples.utils.views as utils
from institute import models
from institute import layouts


@login_required
def show_layout(request, process_id, sample_id):
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id))
    process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id)).actual_instance

    pdf_filename = "/tmp/layouts_{0}_{1}.pdf".format(process.id, sample.id)
    jb_common.utils.base.mkdirs(pdf_filename)
    layout = layouts.get_layout(sample, process)
    if not layout:
        raise Http404("error")
    layout.generate_pdf(pdf_filename)

    png_filename = os.path.join(settings.CACHE_ROOT, "layouts", "{0}-{1}.png".format(process.id, sample.id))
    jb_common.utils.base.mkdirs(png_filename)
    resolution = settings.THUMBNAIL_WIDTH / (layout.width / 72)
    subprocess.check_call(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pngalpha", "-r{0}".format(resolution), "-dEPSCrop",
                             "-sOutputFile=" + png_filename, pdf_filename])
    return jb_common.utils.base.static_file_response(png_filename)
