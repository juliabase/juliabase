#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

from django.template import RequestContext
from django.shortcuts import render_to_response
from django import forms
import django.core.urlresolvers
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from .. import refdb, models
from . import utils


class SimpleSearchForm(forms.Form):
    u"""Form class for the simple search filters.  Currently, it only accepts a
    RefDB query string.
    """

    _ = ugettext_lazy
    query_string = forms.CharField(label=_("Query string"), required=False)


class ChangeListForm(forms.Form):
    _ = ugettext_lazy
    new_list = forms.ChoiceField(label=_("New list"))

    def __init__(self, user, *args, **kwargs):
        super(ChangeListForm, self).__init__(*args, **kwargs)
        self.fields["new_list"].choices, __ = refdb.get_lists(user)
        self.fields["new_list"].initial = models.UserDetails.objects.get(user=user).current_list


@login_required
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
    current_list = models.UserDetails.objects.get(user=request.user).current_list
    references = refdb.get_connection(request.user).get_references(":ID:>0", listname=current_list)
    print len(references)
    return render_to_response("main_menu.html", {"title": _(u"Main menu"), "search": search_form, "references": references,
                                                 "change_list": change_list_form},
                              context_instance=RequestContext(request))


@login_required
def change_list(request):
    change_list_form = ChangeListForm(request.user, request.POST)
    if change_list_form.is_valid():
        user_details = models.UserDetails.objects.get(user=request.user)
        user_details.current_list = change_list_form.cleaned_data["new_list"]
        user_details.save()
        next_url = django.core.urlresolvers.reverse(main_menu)
        return utils.HttpResponseSeeOther(next_url)
    # With an unmanipulated browser, you never get this far
    return render_to_response("change_list.html", {"title": _(u"Change default list"), "change_list": change_list_form},
                              context_instance=RequestContext(request))
