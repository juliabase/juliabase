#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""The dispatch view.  This is a POST-only view which handles the complex form
at the bottom of the bulk view.  It may also be used as an API function.
"""

from __future__ import absolute_import

from . import form_utils
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.views.decorators.http import require_http_methods
from django.template import defaultfilters
import django.core.urlresolvers
from django.utils.http import urlencode
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from django.contrib.auth.decorators import login_required
from django import forms
from .. import refdb
from . import utils, form_utils


def add_references_to_list(ids, add_to_list_form, user):
    # add_to_list_form must be bound and valid
    if add_to_list_form.cleaned_data["existing_list"]:
        listname = add_to_list_form.cleaned_data["existing_list"]
    else:
        verbose_name = add_to_list_form.cleaned_data["new_list"]
        listname = defaultfilters.slugify(verbose_name)
    connection = refdb.get_connection(user)
    connection.pick_references(ids, listname)
    if add_to_list_form.cleaned_data["new_list"]:
        extended_note = connection.get_extended_notes(":NCK:=%s-%s" % (refdb.get_username(user.id), listname))[0]
        extended_note.set_text_content(verbose_name)
        connection.update_extended_notes(extended_note)


def is_referentially_valid(export_form, add_to_shelf_form, add_to_list_form, remove_from_list_form,
                           selection_box_forms, global_dummy_form):
    referentially_valid = True
    action = None
    actions = []
    if export_form.is_valid() and export_form.cleaned_data["format"]:
        actions.append("export")
    if add_to_shelf_form.is_valid() and add_to_shelf_form.cleaned_data["new_shelf"]:
        actions.append("shelf")
    if add_to_list_form.is_valid() and (
        add_to_list_form.cleaned_data["existing_list"] or add_to_list_form.cleaned_data["new_list"]):
        actions.append("list")
    if remove_from_list_form and remove_from_list_form.is_valid() and remove_from_list_form.cleaned_data["remove"]:
        actions.append("remove")
    if not actions:
        form_utils.append_error(global_dummy_form, _(u"You must select an action."))
        referentially_valid = False
    elif len(actions) > 1:
        form_utils.append_error(global_dummy_form, _(u"You can't do more that one thing at the same time."))
        referentially_valid = False
    else:
        action = actions[0]
    # The following is actually already tested in `dispatch` but maybe this
    # changes, so I test it here, too.
    if not any(selection_box_form.is_valid() and selection_box_form.cleaned_data["selected"]
               for selection_box_form in selection_box_forms):
        form_utils.append_error(global_dummy_form, _(u"You must select at least one sample."))
        referentially_valid = False
    return referentially_valid, action


@login_required
@require_http_methods(["POST"])
def dispatch(request):
    export_form = form_utils.ExportForm(request.POST)
    add_to_shelf_form = form_utils.AddToShelfForm(request.POST)
    add_to_list_form = form_utils.AddToListForm(request.user, request.POST)
    remove_from_list_form = form_utils.RemoveFromListForm(request.POST, prefix="remove") \
        if "remove-listname" in request.POST else None
    global_dummy_form = forms.Form(request.POST)
    ids = set()
    for key, value in request.POST.iteritems():
        id_, dash, name = key.partition("-")
        if name == "selected" and value == "on":
            ids.add(id_)
    selection_box_forms = [form_utils.SelectionBoxForm(request.POST, prefix=id_) for id_ in ids]
    if not selection_box_forms:
        return render_to_response("nothing_selected.html", {"title": _(u"Nothing selected")},
                                  context_instance=RequestContext(request))
    all_valid = export_form.is_valid() and add_to_shelf_form.is_valid() and add_to_list_form.is_valid()
    if remove_from_list_form:
        all_valid = remove_from_list_form.is_valid() and all_valid
    all_valid = all([form.is_valid() for form in selection_box_forms]) and all_valid
    referentially_valid, action = is_referentially_valid(export_form, add_to_shelf_form, add_to_list_form, remove_from_list_form,
                                                         selection_box_forms, global_dummy_form)
    if all_valid and referentially_valid:
        if action == "export":
            query_dict = {"format": export_form.cleaned_data["format"]}
            query_dict.update((id_ + "-selected", "on") for id_ in ids)
            query_string = urlencode(query_dict)
            return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse(export) + "?" + query_string)
        elif action == "shelf":
            # FixMe: This must be changed from using citation keys to using
            # IDs.  However, first
            # https://sourceforge.net/tracker/?func=detail&aid=2857792&group_id=26091&atid=385991
            # needs to be fixed.
            citation_keys = [reference.citation_key for reference in refdb.get_connection(request.user).
                             get_references(" OR ".join(":ID:=" + id_ for id_ in ids))]
            refdb.get_connection(request.user).add_note_links(
                ":NCK:=django-refdb-shelf-" + add_to_shelf_form.cleaned_data["new_shelf"],
                u" ".join(":CK:=" + citation_key for citation_key in citation_keys))
        elif action == "list":
            add_references_to_list(ids, add_to_list_form, request.user)
        elif action == "remove":
            refdb.get_connection(request.user).dump_references(ids, remove_from_list_form.cleaned_data["listname"])
    return render_to_response("dispatch.html", {"title": _(u"Action dispatch"), "export": export_form,
                                                "add_to_shelf": add_to_shelf_form, "add_to_list": add_to_list_form,
                                                "global_dummy": global_dummy_form, "selection_boxes": selection_box_forms,
                                                "remove_from_list": remove_from_list_form},
                              context_instance=RequestContext(request))
