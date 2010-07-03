#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Here are the views for a split immediately after a deposition.  In contrast
to the actual split view, you see all samples of the deposition at once, and
you can rename and/or split them.
"""

from __future__ import absolute_import

import datetime
from samples import models, permissions
from django.template import RequestContext
from django.http import Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.decorators import login_required
import django.core.urlresolvers
import django.contrib.auth.models
from django.forms import Form
from django import forms
from django.forms.util import ValidationError
from chantal_common.utils import append_error, HttpResponseSeeOther
from samples.views import utils, form_utils, feed_utils


class OriginalDataForm(Form):
    u"""Form holding the old sample and the number of pieces it is about to be
    split into.
    """
    _ = ugettext_lazy
    sample = forms.CharField(label=_(u"Old sample name"), max_length=30,
                             widget=forms.TextInput(attrs={"readonly": "readonly", "style": "text-align: center"}))
    new_name = forms.CharField(label=_(u"New name"), max_length=30)
    number_of_pieces = forms.IntegerField(label=_(u"Pieces"), initial="1",
                                          widget=forms.TextInput(attrs={"size": "3", "style": "text-align: center"}))

    def __init__(self, remote_client, deposition_number, post_data=None, *args, **kwargs):
        if "initial" not in kwargs:
            kwargs["initial"] = {}
        if post_data is None:
            old_sample_name = kwargs["initial"]["sample"]
            kwargs["initial"]["new_name"] = old_sample_name if utils.sample_name_format(old_sample_name) == "new" \
                else deposition_number
        super(OriginalDataForm, self).__init__(post_data, *args, **kwargs)
        self.remote_client, self.deposition_number = remote_client, deposition_number

    def clean_new_name(self):
        new_name = self.cleaned_data["new_name"]
        new_name_format = utils.sample_name_format(new_name)
        if new_name_format == "old" and utils.does_sample_exist(new_name):
            raise ValidationError(_(u"This sample name exists already."))
        elif new_name_format == "provisional":
            raise ValidationError(_(u"You must get rid of the provisional sample name."))
        return new_name

    def clean_sample(self):
        if not self.remote_client:
            sample = utils.get_sample(self.cleaned_data["sample"])
            if sample is None:
                raise ValidationError(_(u"No sample with this name found."))
            if isinstance(sample, list):
                raise ValidationError(_(u"Alias is not unique."))
        else:
            try:
                sample = models.Sample.objects.get(pk=int(self.cleaned_data["sample"]))
            except models.Sample.DoesNotExist:
                raise ValidationError(_(u"No sample with this ID found."))
            except ValueError:
                raise ValidationError(_(u"Invalid ID format."))
        return sample

    def clean_number_of_pieces(self):
        if self.cleaned_data["number_of_pieces"] <= 0:
            raise ValidationError(_(u"Must be at least 1."))
        return self.cleaned_data["number_of_pieces"]

    def clean(self):
        if "new_name" in self.cleaned_data:
            sample = self.cleaned_data.get("sample")
            if sample:
                new_name = self.cleaned_data["new_name"]
                if utils.sample_name_format(new_name) == "new":
                    if new_name != sample.name:
                        append_error(self, _(u"If you choose a new-style name, it must not change."), "new_name")
                        del self.cleaned_data["new_name"]
                else:
                    if not new_name.startswith(self.deposition_number):
                        append_error(
                            self, _(u"If you choose a deposition-style name, it must begin with the deposition number."),
                            "new_name")
                        del self.cleaned_data["new_name"]
        return self.cleaned_data


class NewNameForm(Form):
    u"""Form holding the newly given name of a sample.
    """
    _ = ugettext_lazy
    new_name = forms.CharField(label=_(u"New sample name"), max_length=30)

    def __init__(self, readonly, data=None, **kwargs):
        super(NewNameForm, self).__init__(data, **kwargs)
        self.fields["new_name"].widget = forms.TextInput(attrs={"size": "15"})
        if readonly:
            self.fields["new_name"].widget.attrs["readonly"] = "readonly"


class GlobalNewDataForm(Form):
    u"""Form for holding new data which applies to all samples and overrides
    local settings.
    """
    _ = ugettext_lazy
    new_location = forms.CharField(label=_(u"New current location"), max_length=50, required=False,
                                   help_text=_(u"(for all samples; leave empty for no change)"))

    def __init__(self, data=None, **kwargs):
        u"""Form constructor.  I have to initialise the field here, both their
        value and their layout.
        """
        deposition_instance = kwargs.pop("deposition_instance")
        super(GlobalNewDataForm, self).__init__(data, **kwargs)
        self.fields["new_location"].initial = \
            models.default_location_of_deposited_samples.get(deposition_instance.__class__, u"")
        self.fields["new_location"].widget = forms.TextInput(attrs={"size": "40"})


def is_all_valid(original_data_forms, new_name_form_lists, global_new_data_form):
    u"""Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `original_data_forms`: all old samples and pieces numbers
      - `new_name_form_lists`: new names for all pieces
      - `global_new_data_form`: the global, overriding settings

    :type original_data_forms: list of `OriginalDataForm`
    :type new_name_form_lists: list of list of `NewNameForm`
    :type global_new_data_form: `GlobalNewDataForm`

    :Return:
      whether all forms are valid according to their ``is_valid()`` method

    :rtype: bool
    """
    valid = all([original_data_form.is_valid() for original_data_form in original_data_forms])
    for forms in new_name_form_lists:
        valid = valid and all([new_name_form.is_valid() for new_name_form in forms])
    valid = valid and global_new_data_form.is_valid()
    return valid


def change_structure(original_data_forms, new_name_form_lists):
    u"""Add or delete new data form according to the new number of pieces
    entered by the user.  While changes in form fields are performs by the form
    objects themselves, they can't change the *structure* of the view.  This is
    performed here.

    :Parameters:
      - `original_data_forms`: all old samples and pieces numbers
      - `new_name_form_lists`: new names for all pieces

    :type original_data_forms: list of `OriginalDataForm`
    :type new_name_form_lists: list of list of `NewNameForm`

    :Return:
      whether the structure was changed, i.e. whether the number of pieces of
      one sample has been changed by the user

    :rtype: bool
    """
    structure_changed = False
    for sample_index in range(len(original_data_forms)):
        original_data_form, new_name_forms = original_data_forms[sample_index], new_name_form_lists[sample_index]
        if original_data_form.is_valid():
            number_of_pieces = original_data_form.cleaned_data["number_of_pieces"]
            if number_of_pieces < len(new_name_forms):
                del new_name_forms[number_of_pieces:]
                structure_changed = True
            elif number_of_pieces > len(new_name_forms):
                for new_name_index in range(len(new_name_forms), number_of_pieces):
                    new_name_forms.append(NewNameForm(readonly=False,
                                                      initial={"new_name": original_data_form.cleaned_data["new_name"]},
                                                      prefix="%d_%d"%(sample_index, new_name_index)))
                structure_changed = True
    return structure_changed


def save_to_database(original_data_forms, new_name_form_lists, global_new_data_form, deposition):
    u"""Performs all splits – if any – and renames the samples according to
    what was input by the user.

    :Parameters:
      - `original_data_forms`: all old samples and pieces numbers
      - `new_name_form_lists`: new names for all pieces
      - `global_new_data_form`: the global, overriding settings
      - `deposition`: the deposition after which the splits took place

    :type original_data_forms: list of `OriginalDataForm`
    :type new_name_form_lists: list of list of `NewNameForm`
    :type global_new_data_form: `GlobalNewDataForm`
    :type deposition: `models.Deposition`

    :Return:
      all sample splits that were performed; note that they are always
      complete, i.e. a sample death objects is always created, too

    :rtype: list of `models.SampleSplit`
    """
    global_new_location = global_new_data_form.cleaned_data["new_location"]
    sample_splits = []
    for original_data_form, new_name_forms in zip(original_data_forms, new_name_form_lists):
        sample = original_data_form.cleaned_data["sample"]
        new_name = original_data_form.cleaned_data["new_name"]
        if new_name != sample.name:
            if not sample.name.startswith("*"):
                models.SampleAlias(name=sample.name, sample=sample).save()
            sample.name = new_name
            sample.save()
        if original_data_form.cleaned_data["number_of_pieces"] > 1:
            sample_split = models.SampleSplit(timestamp=deposition.timestamp + datetime.timedelta(seconds=5),
                                              operator=deposition.operator, parent=sample)
            sample_split.save()
            sample.processes.add(sample_split)
            sample_splits.append(sample_split)
            for new_name_form in new_name_forms:
                child_sample = sample.duplicate()
                child_sample.name = new_name_form.cleaned_data["new_name"]
                child_sample.split_origin = sample_split
                if global_new_location:
                    child_sample.current_location = global_new_location
                child_sample.save()
                for watcher in sample.watchers.all():
                    watcher.my_samples.add(child_sample)
            sample.watchers.clear()
            death = models.SampleDeath(timestamp=deposition.timestamp + datetime.timedelta(seconds=10),
                                       operator=deposition.operator, reason="split")
            death.save()
            sample.processes.add(death)
        else:
            if global_new_location:
                sample.current_location = global_new_location
            sample.save()
    return sample_splits


def is_referentially_valid(original_data_forms, new_name_form_lists, deposition):
    u"""Test whether all forms are consistent with each other and with the
    database.  For example, no sample name must occur twice, and the sample
    names must not exist within the database already.

    :Parameters:
      - `original_data_forms`: all old samples and pieces numbers
      - `new_name_form_lists`: new names for all pieces
      - `deposition`: the deposition after which the split takes place

    :type original_data_forms: list of `OriginalDataForm`
    :type new_name_form_lists: list of `NewNameForm`
    :type deposition: `models.Deposition`

    :Return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    samples = list(deposition.samples.all())
    more_than_one_piece = len(original_data_forms) > 1
    new_names = set()
    original_samples = set()
    for original_data_form in original_data_forms:
        if original_data_form.is_valid():
            original_sample = original_data_form.cleaned_data["sample"]
            if original_sample in original_samples:
                append_error(original_data_form, _(u"Sample %s occurs multiple times.") % original_sample, "sample")
                referentially_valid = False
            original_samples.add(original_sample)
            if original_sample not in samples:
                append_error(original_data_form, _(u"Sample %s doesn't belong to this deposition.") % original_sample,
                             "sample")
                referentially_valid = False
            new_name = original_data_form.cleaned_data["new_name"]
            if utils.sample_name_format(new_name) == "old":
                # "new" names exist in the database already anyway, so we have
                # to check for duplicates in the form only for deposition-style
                # names.
                if new_name in new_names:
                    append_error(original_data_form, _(u"This sample name has been used already on this page."), "new_name")
                    referentially_valid = False
                new_names.add(new_name)
            if more_than_one_piece and new_name == deposition.number:
                append_error(original_data_form, _(u"Since there is more than one piece, the new name "
                                                   u"must not be exactly the deposition's name."), "new_name")
                referentially_valid = False
    if all(original_data_form.is_valid() for original_data_form in original_data_forms):
        assert len(original_samples) <= len(samples)
        if len(original_samples) < len(samples):
            append_error(original_data_form, _(u"At least one sample of the original deposition is missing."))
            referentially_valid = False
    for new_name_forms, original_data_form in zip(new_name_form_lists, original_data_forms):
        if original_data_form.is_valid():
            for new_name_form in new_name_forms:
                if new_name_form.is_valid():
                    new_name = new_name_form.cleaned_data["new_name"]
                    if original_data_form.cleaned_data["number_of_pieces"] == 1:
                        if new_name != original_data_form.cleaned_data["new_name"]:
                            append_error(
                                new_name_form, _(u"If you don't split, you can't rename the single piece."), "new_name")
                            referentially_valid = False
                    else:
                        if new_name in new_names:
                            append_error(
                                new_name_form, _(u"This sample name has been used already on this page."), "new_name")
                            referentially_valid = False
                        new_names.add(new_name)
                        if utils.sample_name_format(new_name) != "new" and \
                                not new_name.startswith(original_data_form.cleaned_data["new_name"]):
                            append_error(new_name_form, _(u"If you choose a deposition-style name, it must begin "
                                                          u"with the parent's new name."), "new_name")
                            referentially_valid = False
                        if utils.does_sample_exist(new_name):
                            append_error(new_name_form, _(u"This sample name exists already."), "new_name")
                            referentially_valid = False
    return referentially_valid


def forms_from_post_data(post_data, deposition, remote_client):
    u"""Intepret the POST data and create bound forms for old and new names and
    the global data.  The top-level new-data list has the same number of
    elements as the original-data list because they correspond to each other.

    :Parameters:
      - `post_data`: the result from ``request.POST``
      - `deposition`: the deposition after which this split takes place
      - `remote_client`: whether the request was sent from the Chantal remote
        client

    :type post_data: ``QueryDict``
    :type deposition: `models.Deposition`
    :type remote_client: bool

    :Return:
      list of original data (i.e. old names) of every sample, list of lists of
      the new data (i.e. piece names), global new data

    :rtype: list of `OriginalDataForm`, list of lists of `NewNameForm`,
      `GlobalNewDataForm`
    """
    post_data, number_of_samples, list_of_number_of_new_names = form_utils.normalize_prefixes(post_data)
    original_data_forms = [OriginalDataForm(remote_client, deposition.number, post_data, prefix=str(i))
                           for i in range(number_of_samples)]
    new_name_form_lists = []
    for sample_index, original_data_form in enumerate(original_data_forms):
        number_of_pieces = original_data_form.cleaned_data["number_of_pieces"] if original_data_form.is_valid() else None
        new_name_forms = []
        for new_name_index in range(list_of_number_of_new_names[sample_index]):
            prefix = "%d_%d" % (sample_index, new_name_index)
            new_name_form = \
                NewNameForm(readonly=number_of_pieces==1, data=post_data, prefix=prefix)
            if number_of_pieces == 1 and new_name_form.is_valid() and original_data_form.is_valid() \
                    and new_name_form.cleaned_data["new_name"] != original_data_form.cleaned_data["new_name"]:
                piece_data = {}
                piece_data["new_name"] = original_data_form.cleaned_data["new_name"]
                new_name_form = NewNameForm(readonly=True, initial=piece_data, prefix=prefix)
            new_name_forms.append(new_name_form)
        new_name_form_lists.append(new_name_forms)
    global_new_data_form = GlobalNewDataForm(post_data, deposition_instance=deposition)
    return original_data_forms, new_name_form_lists, global_new_data_form


def forms_from_database(deposition, remote_client):
    u"""Take a deposition instance and construct forms from it for its old and
    new data.  The top-level new data list has the same number of elements as
    the old data list because they correspond to each other.

    :Parameters:
      - `deposition`: the deposition to be converted to forms.
      - `remote_client`: whether the request was sent from the Chantal remote
        client

    :type deposition: `models.Deposition`
    :type remote_client: bool

    :Return:
      list of original data (i.e. old names) of every sample, list of lists of
      the new data (i.e. piece names), global new data

    :rtype: list of `OriginalDataForm`, list of lists of `NewNameForm`,
      `GlobalNewDataForm`
    """
    samples = deposition.samples.all()
    original_data_forms = [OriginalDataForm(remote_client, deposition.number, initial={"sample": sample.name}, prefix=str(i))
                           for i, sample in enumerate(samples)]
    new_name_form_lists = [[NewNameForm(
                readonly=True,
                initial={"new_name": sample.name if utils.sample_name_format(sample.name) == "new" else deposition.number},
                prefix="%d_0"%i)] for i, sample in enumerate(samples)]
    global_new_data_form = GlobalNewDataForm(deposition_instance=deposition)
    return original_data_forms, new_name_form_lists, global_new_data_form


@login_required
def split_and_rename_after_deposition(request, deposition_number):
    u"""View for renaming and/or splitting samples immediately after they have
    been deposited in the same run.

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: the number of the deposition after which samples
        should be split and/or renamed

    :type request: ``HttpRequest``
    :type deposition_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    deposition = get_object_or_404(models.Deposition, number=deposition_number)
    permissions.assert_can_add_edit_physical_process(request.user, deposition.actual_instance)
    remote_client = utils.is_remote_client(request)
    if request.POST:
        original_data_forms, new_name_form_lists, global_new_data_form = \
            forms_from_post_data(request.POST, deposition, remote_client)
        all_valid = is_all_valid(original_data_forms, new_name_form_lists, global_new_data_form)
        structure_changed = change_structure(original_data_forms, new_name_form_lists)
        referentially_valid = is_referentially_valid(original_data_forms, new_name_form_lists, deposition)
        if all_valid and referentially_valid and not structure_changed:
            sample_splits = save_to_database(original_data_forms, new_name_form_lists, global_new_data_form, deposition)
            for sample_split in sample_splits:
                feed_utils.Reporter(request.user).report_sample_split(sample_split, sample_completely_split=True)
            return utils.successful_response(request, _(u"Samples were successfully split and/or renamed."),
                                             remote_client_response=True)
    else:
        original_data_forms, new_name_form_lists, global_new_data_form = forms_from_database(deposition, remote_client)
    return render_to_response("samples/split_after_deposition.html",
                              {"title": _(u"Bulk sample rename for %s") % deposition,
                               "samples": zip(original_data_forms, new_name_form_lists),
                               "new_sample_data": global_new_data_form},
                              context_instance=RequestContext(request))
