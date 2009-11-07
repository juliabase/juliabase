#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.
#
#     Django-RefDB is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public
#     License as published by the Free Software Foundation, either
#     version 3 of the License, or (at your option) any later
#     version.
#
#     Django-RefDB is distributed in the hope that it will be
#     useful, but WITHOUT ANY WARRANTY; without even the implied
#     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#     PURPOSE.  See the GNU Affero General Public License for more
#     details.
#
#     You should have received a copy of the GNU Affero General
#     Public License along with Django-RefDB.  If not, see
#     <http://www.gnu.org/licenses/>.


u"""The main menu view.
"""

from __future__ import absolute_import

import hashlib
from django.template import RequestContext
from django.shortcuts import render_to_response
from django import forms
import django.core.urlresolvers
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import condition, require_http_methods
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal_common import utils as chantal_utils
from .. import refdb, models
from . import utils


class SimpleSearchForm(forms.Form):
    u"""Form class for the simple search filters.  Currently, it only accepts a
    RefDB query string.
    """
    _ = ugettext_lazy
    query_string = forms.CharField(label=_("Query string"), required=False)


class ChangeListForm(forms.Form):
    u"""Form class for changing the default references list which is displayed
    on the main menu page.
    """
    _ = ugettext_lazy
    new_list = forms.ChoiceField(label=_("New list"))

    def __init__(self, user, connection, *args, **kwargs):
        super(ChangeListForm, self).__init__(*args, **kwargs)
        self.fields["new_list"].choices, __ = refdb.get_lists(user, connection)
        self.fields["new_list"].initial = user.database_accounts.get(database=connection.database).current_list


def embed_common_data(request, database):
    u"""Add a ``common_data`` attribute to request, containing various data
    used across the view.  See ``utils.CommonBulkViewData`` for further
    information.  If the GET parameters of the view are invalid, a
    ``RedirectException`` is raised so that the user can see and correct the
    errors.

    If the ``request`` object already has ``common_data``, this function does
    nothing.

    :Parameters:
      - `request`: current HTTP request object
      - `database`: the name of the RefDB database

    :type request: ``HttpRequest``
    :type database: unicode
    """
    if not hasattr(request, "common_data"):
        refdb_connection = refdb.get_connection(request.user, database)
        current_list = request.user.database_accounts.get(database=database).current_list
        try:
            links = refdb_connection.get_extended_notes(
                ":NCK:=%s-%s" % (refdb.get_username(request.user.id), current_list))[0].links
        except IndexError:
            links = []
        # FixMe: Apart from "reference", the value can also be "refid", in
        # which case an ID is returned.  Those must be added to the resulting
        # list.
        citation_keys = [link[1] for link in links if link[0] == "reference"]
        ids = utils.citation_keys_to_ids(refdb_connection, citation_keys).values()
        references_last_modified = utils.last_modified(request.user, refdb_connection, ids)
        request.common_data = utils.CommonBulkViewData(
            refdb_connection, ids, current_list=current_list, references_last_modified=references_last_modified)


def get_last_modification_date(request, database):
    u"""Returns the last modification of the references found in the current
    references list on the main menu page.  Additionally, the last modification
    of user settings (language, current list) is taken into account.

    The routine is only used in the ``condition`` decorator in `main_menu`.

    :Parameters:
      - `request`: current HTTP request object
      - `database`: the name of the RefDB database

    :type request: ``HttpRequest``
    :type database: unicode

    :Return:
      timestamp of last modification of the displayed references and the main
      manu as a whole

    :rtype: ``datetime.datetime``
    """
    embed_common_data(request, database)
    last_modified = request.common_data.references_last_modified
    if last_modified:
        last_modified = max(last_modified, request.user.chantal_user_details.settings_last_modified)
    return last_modified


def get_etag(request, database):
    u"""Returns the ETag for the current main menu.  Unfortunately, Opera
    doesn't seem to send If-None-Match at all, an Firefox does only for the
    latest ETag – which means that Firefox only caches one snapshot of a page
    at the same time.  This way, the ETag is pretty useless since Last-Modified
    does a better job.  Anyway.

    The routine is only used in the ``condition`` decorator in `main_menu`.

    :Parameters:
      - `request`: current HTTP request object
      - `database`: the name of the RefDB database

    :type request: ``HttpRequest``
    :type database: unicode

    :Return:
      current ETag of the main menu

    :rtype: str
    """
    embed_common_data(request, database)
    etag = hashlib.sha1()
    etag.update(request.user.chantal_user_details.language)
    etag.update("--")
    etag.update(request.common_data.current_list)
    etag.update("--")
    etag.update("--".join(request.common_data.ids))
    etag.update("--")
    etag.update(repr(request.common_data.references_last_modified))
    return etag.hexdigest()


@login_required
@condition(get_etag, get_last_modification_date)
def main_menu(request, database):
    u"""Generates the main page with simple search and main reference list.

    :Parameters:
      - `request`: the current HTTP Request object
      - `database`: the name of the RefDB database

    :type request: ``HttpRequest``
    :type database: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    search_form = SimpleSearchForm()
    change_list_form = ChangeListForm(request.user, request.common_data.refdb_connection)
    current_list = request.common_data.current_list
    references = utils.fetch_references(request.common_data.refdb_connection, request.common_data.ids, request.user)
    return render_to_response("refdb/main_menu.html", {"title": _(u"Main menu"), "search": search_form,
                                                       "references": references, "change_list": change_list_form,
                                                       "database": database},
                              context_instance=RequestContext(request))


@login_required
@require_http_methods(["POST"])
def change_list(request, database):
    u"""GET-only view for changing the default references list on the main
    menue page.

    :Parameters:
      - `request`: the current HTTP Request object
      - `database`: the name of the RefDB database

    :type request: ``HttpRequest``
    :type database: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    change_list_form = ChangeListForm(request.user, refdb.get_connection(request.user, database), request.POST)
    if change_list_form.is_valid():
        database_account = request.user.database_accounts.get(database=database)
        database_account.current_list = change_list_form.cleaned_data["new_list"]
        database_account.save()
        next_url = django.core.urlresolvers.reverse(main_menu, kwargs={"database": database})
        return chantal_utils.HttpResponseSeeOther(next_url)
    # With an unmanipulated browser, you never get this far
    return render_to_response("refdb/change_list.html",
                              {"title": _(u"Change default list"), "change_list": change_list_form, "database": database},
                              context_instance=RequestContext(request))
