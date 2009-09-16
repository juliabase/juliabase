#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""View and routines for the bulk view.  In the bulk view, the results of a
search are displayed in pages.  Additionally, it is used to visualise
references lists.
"""

from __future__ import absolute_import

from . import form_utils
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.views.decorators.http import last_modified, require_http_methods
from django.utils.http import urlencode
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from django.contrib.auth.decorators import login_required
from django import forms
from django.core.cache import cache
from django.conf import settings
from .. import refdb
from . import utils, form_utils


class SearchForm(forms.Form):
    u"""Form class for the search filters.  Currently, it only accepts a RefDB
    query string.
    """

    _ = ugettext_lazy
    query_string = forms.CharField(label=_("Query string"), required=False)


@login_required
def search(request):
    u"""Searchs for references and presents the search results.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    search_form = SearchForm(request.GET)
    return render_to_response("search.html", {"title": _(u"Search"), "search": search_form},
                              context_instance=RequestContext(request))


def form_fields_to_query(form_fields):
    query_string = form_fields.get("query_string", "")
    return query_string


class CommonBulkViewData(object):

    def __init__(self, query_string, offset, limit, refdb_connection, ids):
        self.query_string, self.offset, self.limit, self.refdb_connection, self.ids = \
            query_string, offset, limit, refdb_connection, ids

    def get_all_values(self):
        return self.query_string, self.offset, self.limit, self.refdb_connection, self.ids


def get_last_modification_date(request):
    query_string = form_fields_to_query(request.GET)
    offset = request.GET.get("offset")
    limit = request.GET.get("limit")
    try:
        offset = int(offset)
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    refdb_connection = refdb.get_connection(request.user)
    ids = refdb_connection.get_references(query_string, output_format="ids", offset=offset, limit=limit)
    request.common_data = CommonBulkViewData(query_string, offset, limit, refdb_connection, ids)
    return utils.last_modified(request.user, ids)

@login_required
@last_modified(get_last_modification_date)
@require_http_methods(["GET"])
def bulk(request):

    def build_page_link(new_offset):
        new_query_dict = request.GET.copy()
        new_query_dict["offset"] = new_offset
        new_query_dict["limit"] = limit
        return "?" + urlencode(new_query_dict) if 0 <= new_offset < number_of_references and new_offset != offset else None

    query_string, offset, limit, refdb_connection, ids = request.common_data.get_all_values()
    number_of_references = refdb_connection.count_references(query_string)
    prev_link = build_page_link(offset - limit)
    next_link = build_page_link(offset + limit)
    pages = []
    for i in range(number_of_references // limit + 1):
        link = build_page_link(i * limit)
        pages.append(link)
    all_references = cache.get_many(settings.REFDB_CACHE_PREFIX + id_ for id_ in ids)
    length_cache_prefix = len(settings.REFDB_CACHE_PREFIX)
    all_references = dict((cache_id[length_cache_prefix:], reference) for cache_id, reference in all_references.iteritems())
    missing_ids = set(ids) - set(all_references)
    if missing_ids:
        missing_references = refdb_connection.get_references(u" OR ".join(":ID:=" + id_ for id_ in missing_ids))
        missing_references = dict((reference.id, reference) for reference in missing_references)
        all_references.update(missing_references)
    references = [all_references[id_] for id_ in ids]
    for reference in references:
        reference.fetch(["shelves", "global_pdf_available", "users_with_offprint", "relevance", "comments",
                         "pdf_is_private", "creator", "institute_publication"], refdb_connection, request.user.pk)
        cache.set(settings.REFDB_CACHE_PREFIX + reference.id, reference)
        reference.selection_box = form_utils.SelectionBoxForm(prefix=reference.id)
    export_form = form_utils.ExportForm()
    add_to_shelf_form = form_utils.AddToShelfForm()
    add_to_list_form = form_utils.AddToListForm(request.user)
    reference_list = request.GET.get("list")
    if reference_list:
        verbose_listname = refdb.get_verbose_listname(reference_list, request.user)
        remove_from_list_form = form_utils.RemoveFromListForm(
            initial={"listname": reference_list}, verbose_listname=verbose_listname, prefix="remove")
    else:
        remove_from_list_form = None
    title = _(u"Bulk view") if not reference_list else _(u"List view of %s") % verbose_listname
    return render_to_response("bulk.html", {"title": title, "references": references,
                                            "prev_link": prev_link, "next_link": next_link, "pages": pages,
                                            "add_to_shelf": add_to_shelf_form, "export": export_form,
                                            "add_to_list": add_to_list_form,
                                            "remove_from_list": remove_from_list_form},
                              context_instance=RequestContext(request))
