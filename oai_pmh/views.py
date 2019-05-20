#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
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


from django.http import HttpResponse, Http404


def get_record(request):
    ...


def identity(request):
    ...


def list_identifiers(request):
    ...


def list_metadata_formats(request):
    ...


def list_records(request):
    ...


def list_sets(request):
    ...


views = {"GetRecord": get_record, "Identity": identity, "ListIdentifiers": list_identifiers,
         "ListMetadataFormats": list_metadata_formats, "ListRecords": list_records, "ListSets": list_sets}

def root(request):
    """TBD

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    verb = request.GET.get("verb")
    view_function = views.get(verb)
    if view_function:
        return view_function(request)
    else:
        raise Http404
