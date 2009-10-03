#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""The main menu view.
"""

from __future__ import absolute_import

from django.template import RequestContext
from django.shortcuts import render_to_response
from django import forms
import django.core.urlresolvers
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import condition, require_http_methods
from django.utils.translation import ugettext as _, ugettext_lazy
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

    def __init__(self, user, *args, **kwargs):
        super(ChangeListForm, self).__init__(*args, **kwargs)
        self.fields["new_list"].choices, __ = refdb.get_lists(user)
        self.fields["new_list"].initial = models.UserDetails.objects.get(user=user).current_list


def embed_common_data(request):
    u"""Add a ``common_data`` attribute to request, containing various data
    used across the view.  See ``utils.CommonBulkViewData`` for further
    information.  If the GET parameters of the view are invalid, a
    ``RedirectException`` is raised so that the user can see and correct the
    errors.

    :Parameters:
      - `request`: current HTTP request object

    :type request: ``HttpRequest``
    """
    refdb_connection = refdb.get_connection(request.user)
    current_list = models.UserDetails.objects.get(user=request.user).current_list
    ids = refdb.get_connection(request.user).get_references(":ID:>0", output_format="ids", listname=current_list)
    request.common_data = utils.CommonBulkViewData(refdb_connection, ids)
    request.common_data.current_list = current_list


def get_last_modification_date(request):
    embed_common_data(request)
    last_modified = utils.last_modified(request.user, request.common_data.ids)
    last_modified = max(last_modified, request.user.refdb_user_details.settings_last_modified)
    return last_modified


@login_required
@condition(last_modified_func=get_last_modification_date)
def main_menu(request):
    u"""Generates the main page with simple search and main reference list.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    search_form = SimpleSearchForm()
    change_list_form = ChangeListForm(request.user)
    current_list = request.common_data.current_list
    references = utils.fetch_references(request.common_data.refdb_connection, request.common_data.ids, request.user.id)
    return render_to_response("refdb/main_menu.html", {"title": _(u"Main menu"), "search": search_form,
                                                       "references": references, "change_list": change_list_form},
                              context_instance=RequestContext(request))


@login_required
@require_http_methods(["POST"])
def change_list(request):
    u"""GET-only view for changing the default references list on the main
    menue page.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    change_list_form = ChangeListForm(request.user, request.POST)
    if change_list_form.is_valid():
        user_details = models.UserDetails.objects.get(user=request.user)
        user_details.current_list = change_list_form.cleaned_data["new_list"]
        user_details.save()
        next_url = django.core.urlresolvers.reverse(main_menu)
        return utils.HttpResponseSeeOther(next_url)
    # With an unmanipulated browser, you never get this far
    return render_to_response("refdb/change_list.html",
                              {"title": _(u"Change default list"), "change_list": change_list_form},
                              context_instance=RequestContext(request))
