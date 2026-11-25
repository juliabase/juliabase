# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2026 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""The process bodies of the sample data sheet, which the browser loads
separately from the data sheet itself.
"""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from samples import permissions
from samples.models import Sample
from samples.utils.views import digest_process
from samples.views.sample import find_sample_process, is_process_cleared


@login_required
@never_cache
@require_http_methods(["GET"])
def process_details(request, process_id, sample_id):
    """Returns the body of a process as shown on the data sheet of a sample, as
    an HTML fragment for htmx.  The user may load it exactly if the process is
    shown to them on the data sheet of this sample.  The response must not be
    cached by the browser because it depends on the user.

    :param request: the current HTTP Request object
    :param process_id: the ID of the process
    :param sample_id: the ID of the sample whose data sheet shows the process

    :type request: HttpRequest
    :type process_id: str
    :type sample_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse

    :raises Http404: if the sample does not exist or if the process is not
        shown on its data sheet
    :raises samples.permissions.PermissionError: if the user is not allowed to
        view the sample
    """
    sample = get_object_or_404(Sample, pk=int(sample_id))
    clearance = permissions.get_sample_clearance(request.user, sample)
    entry = find_sample_process(sample, int(process_id))
    if entry is None or not is_process_cleared(request.user, clearance, entry.process):
        raise Http404("The process is not shown on the data sheet of this sample.")
    process_context = digest_process(entry.process, request.user, entry.local_context)
    response = render(request, "samples/process_details.html",
                      {"process": process_context, "sample": {"sample": sample, "clearance": clearance}})
    # The HTML minifier (django-htmlmin) would turn the fragment into a
    # complete HTML document.
    response.minify_response = False
    return response
