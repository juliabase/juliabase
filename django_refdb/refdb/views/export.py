#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""The references export view.

:var output_format_meta_info: dictionary which maps short names of export
formats to tuples which contain the MIME type and the file extention for that
export format

:type output_format_meta_info: dict mapping str to (str, str)
"""

from __future__ import absolute_import

from django.views.decorators.http import require_http_methods
from django.http import Http404, HttpResponse
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from django.contrib.auth.decorators import login_required
from .. import refdb


output_format_meta_info = {
    "ris": ("text/plain", ".ris"),
    "html": ("text/html", ".html"),
    "xhtml": ("application/xhtml+xml", ".xhtml"),
    "db31": ("text/plain", ".dbk"),
    "db31x": ("text/xml", ".dbk"),
    "db50": ("text/plain", ".dbk"),
    "db50x": ("text/xml", ".dbk"),
    "teix": ("text/xml", ".xml"),
    "tei5x": ("text/xml", ".xml"),
    "mods": ("text/xml", ".mods"),
    "bibtex": ("text/plain", ".bib"),
    "rtf": ("text/rtf", ".rtf")
    }
 
@login_required
@require_http_methods(["GET"])
def export(request, database):
    u"""GET-only view for exporting references into various output formats like
    RIS or BibTeX.

    :Parameters:
      - `request`: the current HTTP Request object
      - `database`: the name of the RefDB database

    :type request: ``HttpRequest``
    :type database: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    format = request.GET.get("format")
    try:
        content_type, file_extension = output_format_meta_info[format]
    except KeyError:
        error_string = _(u"No format given.") if not format else _(u"Format “%s” is unknown.") % format
        raise Http404(error_string)
    ids = set()
    for key, value in request.GET.iteritems():
        if key.endswith("-selected") and value == "on":
            ids.add(key.partition("-")[0])
    output = refdb.get_connection(request.user, database).get_references(u" OR ".join(":ID:=" + id_ for id_ in ids),
                                                                         output_format=format)
    response = HttpResponse(content_type=content_type + "; charset=utf-8")
    response['Content-Disposition'] = "attachment; filename=references" + file_extension
    response.write(output)
    return response
