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

from django.http import HttpResponse
from jb_common import mimeparse


def respond_as_rdf(request, graph):
    requested_mime_type = mimeparse.best_match({"application/rdf+xml", "text/turtle"},
                                               request.META.get("HTTP_ACCEPT", "application/rdf+xml"))
    return HttpResponse(graph.serialize(format=requested_mime_type), content_type=requested_mime_type)
