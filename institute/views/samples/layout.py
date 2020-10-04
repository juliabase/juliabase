# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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


import os, subprocess, uuid
from io import BytesIO
from functools import partial
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
import jb_common.utils.base
import samples.utils.views as utils
from institute import models
from institute import layouts


def generate_layout(sample, process):
    # FixMe: This should be implemented without writing to the disk.
    pdf_filename = "/tmp/layouts_{}.pdf".format(uuid.uuid4())
    layout = layouts.get_layout(sample, process)
    if not layout:
        raise Http404("error")
    layout.generate_pdf(pdf_filename)
    resolution = settings.THUMBNAIL_WIDTH / (layout.width / 72)
    content = subprocess.check_output(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pngalpha", "-r{0}".format(resolution),
                                       "-dEPSCrop", "-sOutputFile=-", pdf_filename])
    os.unlink(pdf_filename)
    return BytesIO(content)


@login_required
def show_layout(request, process_id, sample_id):
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id))
    process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id)).actual_instance
    png_filename = os.path.join("layouts", "{0}-{1}.png".format(process.id, sample.id))
    stream = jb_common.utils.base.get_cached_bytes_stream(
        png_filename, partial(generate_layout, sample, process), timestamps=[sample.last_modified, process.last_modified])
    return jb_common.utils.base.static_response(stream, png_filename)
