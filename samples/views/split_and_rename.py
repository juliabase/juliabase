#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Here are the views for an ordinary sample split.
"""

from __future__ import absolute_import

import datetime
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import Http404
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms.util import ValidationError
from samples import models, permissions
import django.core.urlresolvers
from chantal_common.utils import append_error
from samples.views import utils, feed_utils


class NewNameForm(forms.Form):
    u"""Form for data of one new sample piece.
    """
    _ = ugettext_lazy
    new_name = forms.CharField(label=_(u"New sample name"), max_length=30)
    new_purpose = forms.CharField(label=_(u"New sample purpose"), max_length=80, required=False)
    delete = forms.BooleanField(label=_(u"Delete"), required=False)

    def __init__(self, parent_name, *args, **kwargs):
        super(NewNameForm, self).__init__(*args, **kwargs)
        self.parent_name = parent_name

    def clean_new_name(self):
        new_name = self.cleaned_data["new_name"]
        sample_name_format = utils.sample_name_format(new_name)
        if not sample_name_format:
            raise ValidationError(_(u"The sample name has an invalid format."))
        elif sample_name_format == "old":
            if not new_name.startswith(self.parent_name):
                raise ValidationError(_(u"The new sample name must start with the parent sample's name."))
        if utils.does_sample_exist(new_name):
            raise ValidationError(_(u"Name does already exist in database."))
        return new_name


class GlobalDataForm(forms.Form):
    u"""Form for general data for a split as a whole, and for the “finished”
    checkbox.
    """
    _ = ugettext_lazy
    finished = forms.BooleanField(label=_(u"All pieces completely entered"), required=False)
    sample_completely_split = forms.BooleanField(label=_(u"Sample was completely split"), initial=True, required=False)
    sample_series = forms.ModelChoiceField(label=_(u"Sample series"), queryset=None, required=False)

    def __init__(self, parent, user_details, data=None, **kwargs):
        super(GlobalDataForm, self).__init__(data, **kwargs)
        now = datetime.datetime.now() + datetime.timedelta(seconds=5)
        three_months_ago = now - datetime.timedelta(days=90)
        self.fields["sample_series"].queryset = permissions.get_editable_sample_series(user_details.user)


def forms_from_post_data(post_data, parent, user_details):
    u"""Interpret the POST data sent by the user through his browser and create
    forms from it.  This function also performs the so-called “structural
    changes”, namely adding and deleting pieces.

    Note this this routine doesn't append the dummy form at the end which can
    be used by the user to add a new piece.  On the contrary, it ignores it in
    the POST data if the user didn't make use of it.

    :Parameters:
      - `post_data`: the value of ``request.POST``
      - `parent`: the parent sample which is split
      - `user_details`: the user details of the current user

    :type post_data: ``QueryDict``
    :type parent: `models.Sample`
    :type user_details: `models.UserDetails`

    :Return:
      The list of the pieces forms, the global data form, and whether the
      structure was changed by the user

    :rtype: list of `NewNameForm`, `GlobalDataForm`, bool
    """
    new_name_forms = []
    structure_changed = False
    index = 0
    last_deleted = False
    while True:
        if "%d-new_name" % index not in post_data:
            break
        if "%d-delete" % index in post_data:
            structure_changed = True
            last_deleted = True
        else:
            new_name_forms.append(NewNameForm(parent.name, post_data, prefix=str(index)))
            last_deleted = False
        index += 1
    if not last_deleted and post_data.get("%d-new_name" % (index-1), parent.name) == parent.name:
        del new_name_forms[-1]
    else:
        structure_changed = True
    global_data_form = GlobalDataForm(parent, user_details, post_data)
    return new_name_forms, global_data_form, structure_changed


def forms_from_database(parent, user_details):
    u"""Generate pristine forms for the given parent.  In particular, this
    returns an empty list of ``new_name_forms``.

    :Parameters:
      - `parent`: the sample to be split
      - `user_details`: the details of the current user

    :type parent: `models.Sample`
    :type user_details: `sample.UserDetails`

    :Return:
      the initial ``new_name_forms``, the initial ``global_data_form``

    :rtype: list of `NewNameForm`, list of `GlobalDataForm`
    """
    new_name_forms = []
    global_data_form = GlobalDataForm(parent, user_details)
    return new_name_forms, global_data_form


def is_all_valid(new_name_forms, global_data_form):
    u"""Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `new_name_forms`: all “new name forms”, but not the dummy one for new
        pieces (the one in darker grey).
      - `global_data_form`: the global data form

    :type new_name_forms: list of `NewNameForm`
    :type global_data_form: `GlobalDataForm`

    :Return:
      whether all forms are valid

    :rtype: bool
    """
    all_valid = all([new_name_form.is_valid() for new_name_form in new_name_forms])
    all_valid = global_data_form.is_valid() and all_valid  # Ordering important: .is_valid() must be called
    return all_valid


def is_referentially_valid(new_name_forms, global_data_form, number_of_old_pieces):
    u"""Test whether all forms are consistent with each other and with the
    database.  For example, no piece name must occur twice, and the piece names
    must not exist within the database.

    :Parameters:
      - `new_name_forms`: all “new name forms”, but not the dummy one for new
        pieces (the one in darker grey).
      - `global_data_form`: the global data form
      - `number_of_old_pieces`: The number of pieces the split has already had,
        if it is a re-split.  It's 0 if we are creating a new split.

    :type new_name_forms: list of `NewNameForm`
    :type global_data_form: `GlobalDataForm`
    :type number_of_old_pieces: int

    :Return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = global_data_form.cleaned_data["finished"]
    if not new_name_forms:
        append_error(global_data_form, _(u"You must split into at least one piece."))
        referentially_valid = False
    if global_data_form.is_valid() and global_data_form.cleaned_data["sample_completely_split"] and \
            number_of_old_pieces + len(new_name_forms) < 2:
        append_error(global_data_form, _(u"You must split into at least two pieces if the split is complete."))
        referentially_valid = False
    new_names = set()
    for new_name_form in new_name_forms:
        if new_name_form.is_valid():
            new_name = new_name_form.cleaned_data["new_name"]
            if new_name in new_names or utils.does_sample_exist(new_name):
                append_error(new_name_form, _(u"Name is already given."))
                referentially_valid = False
            new_names.add(new_name)
    return referentially_valid


def save_to_database(new_name_forms, global_data_form, parent, sample_split, user):
    u"""Save all form data to the database.  If `sample_split` is not ``None``,
    modify it instead of appending a new one.  Warning: For this, the old split
    process must be the last process at all for the parental sample!  This must
    be checked before this routine is called.

    :Parameters:
      - `new_name_forms`: all “new name forms”, but not the dummy one for new
        pieces (the one in darker grey).
      - `global_data_form`: the global data form
      - `parent`: the sample to be split
      - `sample_split`: the already existing sample split process that is to be
        modified.  If this is ``None``, create a new one.
      - `user`: the current user

    :type new_name_forms: list of `NewNameForm`
    :type global_data_form: `GlobalDataForm`
    :type parent: `models.Sample`
    :type sample_split: `models.SampleSplit`
    :type user: ``django.contrib.auth.models.User``

    :Return:
      the sample split instance, new pieces as a dictionary mapping the new
      names to the sample IDs

    :rtype: `models.SampleSplit`, dict mapping unicode to int
    """
    now = datetime.datetime.now()
    if not sample_split:
        sample_split = models.SampleSplit(timestamp=now, operator=user, parent=parent)
        sample_split.save()
        parent.processes.add(sample_split)
    else:
        sample_split.timestamp = now
        sample_split.operator = user
        sample_split.save()
    sample_series = global_data_form.cleaned_data["sample_series"]
    new_pieces = {}
    for new_name_form in new_name_forms:
        new_name = new_name_form.cleaned_data["new_name"]
        child = models.Sample(name=new_name,
                              current_location=parent.current_location,
                              currently_responsible_person=user,
                              purpose=new_name_form.cleaned_data["new_purpose"], tags=parent.tags,
                              split_origin=sample_split,
                              topic=parent.topic)
        child.save()
        new_pieces[new_name] = child.pk
        for watcher in parent.watchers.all():
            watcher.my_samples.add(child)
        if sample_series:
            sample_series.samples.add(child)
    if global_data_form.cleaned_data["sample_completely_split"]:
        parent.watchers.clear()
        death = models.SampleDeath(timestamp=now+datetime.timedelta(seconds=5), operator=user, reason="split")
        death.save()
        parent.processes.add(death)
    return sample_split, new_pieces


@login_required
def split_and_rename(request, parent_name=None, old_split_id=None):
    u"""Both splitting of a sample and re-split of an already existing split
    are handled here.  *Either* ``parent_name`` *or* ``old_split`` are unequal
    to ``None``.

    :Parameters:
      - `request`: the current HTTP Request object
      - `parent_name`: if given, the name of the sample to be split
      - `old_split_id`: if given the process ID of the split to be modified

    :type request: ``HttpRequest``
    :type parent_name: unicode or ``NoneType``
    :type old_split_id: int or ``NoneType``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    assert (parent_name or old_split_id) and not (parent_name and old_split_id)
    if parent_name:
        old_split = None
        parent = utils.lookup_sample(parent_name, request.user)
    else:
        old_split = get_object_or_404(models.SampleSplit, pk=utils.convert_id_to_int(old_split_id))
        parent = old_split.parent
        permissions.assert_can_edit_sample(request.user, parent)
        if parent.last_process_if_split() != old_split:
            raise Http404(_(u"This split is not the last one in the sample's process list."))
    user_details = utils.get_profile(request.user)
    number_of_old_pieces = old_split.pieces.count() if old_split else 0
    if request.method == "POST":
        new_name_forms, global_data_form, structure_changed = forms_from_post_data(request.POST, parent, user_details)
        all_valid = is_all_valid(new_name_forms, global_data_form)
        referentially_valid = is_referentially_valid(new_name_forms, global_data_form, number_of_old_pieces)
        if all_valid and referentially_valid and not structure_changed:
            sample_split, new_pieces = save_to_database(new_name_forms, global_data_form, parent, old_split, request.user)
            feed_utils.Reporter(request.user).report_sample_split(
                sample_split, global_data_form.cleaned_data["sample_completely_split"])
            return utils.successful_response(
                request, _(u"Sample “%s” was successfully split.") % parent,
                "show_sample_by_name", {"sample_name": parent.name}, remote_client_response=new_pieces)
    else:
        new_name_forms, global_data_form = forms_from_database(parent, user_details)
    new_name_forms.append(NewNameForm(parent.name, initial={"new_name": parent.name, "new_purpose": parent.purpose},
                                      prefix=str(len(new_name_forms))))
    return render_to_response("samples/split_and_rename.html",
                              {"title": _(u"Split sample “%s”") % parent,
                               "new_names": zip(range(number_of_old_pieces+1,
                                                      number_of_old_pieces+1+len(new_name_forms)),
                                                new_name_forms),
                               "global_data": global_data_form,
                               "old_split": old_split},
                              context_instance=RequestContext(request))


@login_required
def latest_split(request, sample_name):
    u"""Get the database ID of the latest split of a sample, if it is also the
    very latest process for that sample.  In all other cases, return ``None``
    (or an error HTML page if the sample didn't exist).

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample = utils.lookup_sample(sample_name, request.user)
    split = sample.last_process_if_split()
    return utils.respond_to_remote_client(split.pk if split else None)
