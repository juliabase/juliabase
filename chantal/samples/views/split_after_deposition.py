#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Here are the views for a split immediately after a deposition.  In contrast
to the actual split view, you see all samples of the deposition at once, and
you can rename and/or split them.
"""

import datetime
from chantal.samples import models
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
from chantal.samples.views import utils

class OriginalDataForm(Form):
    u"""Form holding the old sample and the number of pieces it is about to be
    split into.
    """
    _ = ugettext_lazy
    sample = forms.CharField(label=_(u"Old sample name"), max_length=30,
                             widget=forms.TextInput(attrs={"readonly": "readonly", "style": "text-align: center"}))
    number_of_pieces = forms.IntegerField(label=_(u"Pieces"), initial="1",
                                          widget=forms.TextInput(attrs={"size": "3", "style": "text-align: center"}))
    def __init__(self, remote_client, *args, **kwargs):
        super(OriginalDataForm, self).__init__(*args, **kwargs)
        self.remote_client = remote_client
    def clean_sample(self):
        if not self.remote_client:
            sample = utils.get_sample(self.cleaned_data["sample"])
            if sample is None:
                raise ValidationError(_(u"No sample with this name found."))
            if isinstance(sample, list):
                raise ValidationError(_(u"Alias is not unique."))
        else:
            try:
                sample = models.Sample.get(id=int(self.cleaned_data["sample"]))
            except models.Sample.DoesNotExist:
                raise ValidationError(_(u"No sample with this ID found."))
            except ValueError:
                raise ValidationError(_(u"Invalid ID format."))
        return sample
    def clean_number_of_pieces(self):
        if self.cleaned_data["number_of_pieces"] <= 0:
            raise ValidationError(_(u"Must be at least 1."))
        return self.cleaned_data["number_of_pieces"]

class NewDataForm(Form):
    u"""Form holding the newly given name of a sample and the new person
    responsible for it.
    """
    _ = ugettext_lazy
    new_name = forms.CharField(label=_(u"New sample name"), max_length=30)
    new_responsible_person = utils.OperatorChoiceField(label=_(u"New responsible person"), queryset=None)
    def __init__(self, data=None, **keyw):
        super(NewDataForm, self).__init__(data, **keyw)
        self.fields["new_name"].widget = forms.TextInput(attrs={"size": "15"})
        self.fields["new_responsible_person"].queryset = django.contrib.auth.models.User.objects.all()

class GlobalNewDataForm(Form):
    u"""Form for holding new data which applies to all samples and overrides
    local settings.
    """
    _ = ugettext_lazy
    new_responsible_person = utils.OperatorChoiceField(
        label=_(u"New responsible person"), required=False, queryset=None,
        help_text=_(u"(for all samples; overrides individual settings above)"), empty_label=_(u"(no global change)"))
    new_location = forms.CharField(label=_(u"New current location"), max_length=50, required=False,
                                   help_text=_(u"(for all samples; leave empty for no change)"))
    def __init__(self, data=None, **keyw):
        u"""Form constructor.  I have to initialise the field here, both heir
        value and their layout.
        """
        deposition_instance = keyw.pop("deposition_instance")
        super(GlobalNewDataForm, self).__init__(data, **keyw)
        self.fields["new_responsible_person"].queryset = django.contrib.auth.models.User.objects.all()
        self.fields["new_location"].initial = \
            models.default_location_of_deposited_samples.get(deposition_instance.__class__, u"")
        self.fields["new_location"].widget = forms.TextInput(attrs={"size": "40"})

def is_all_valid(original_data_forms, new_data_form_lists, global_new_data_form):
    u"""Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `original_data_forms`: all old samples and pieces numbers
      - `new_data_form_lists`: new names for all pieces
      - `global_new_data_form`: the global, overriding settings

    :type original_data_forms: list of `OriginalDataForm`
    :type new_data_form_lists: list of list of `NewDataForm`
    :type global_new_data_form: `GlobalNewDataForm`

    :Return:
      whether all forms are valid according to their ``is_valid()`` method

    :rtype: bool
    """
    valid = all([original_data_form.is_valid() for original_data_form in original_data_forms])
    for forms in new_data_form_lists:
        valid = valid and all([new_data_form.is_valid() for new_data_form in forms])
    valid = valid and global_new_data_form.is_valid()
    return valid

def change_structure(original_data_forms, new_data_form_lists, deposition_number):
    u"""Add or delete new data form according to the new number of pieces
    entered by the user.  While changes in form fields are performs by the form
    objects themselves, they can't change the *structure* of the view.  This is
    performed here.
    
    :Parameters:
      - `original_data_forms`: all old samples and pieces numbers
      - `new_data_form_lists`: new names for all pieces
      - `deposition_number`: the deposition number

    :type original_data_forms: list of `OriginalDataForm`
    :type new_data_form_lists: list of list of `NewDataForm`
    :type deposition_number: unicode

    :Return:
      whether the structure was changed, i.e. whether the number of pieces of
      one sample has been changed by the user

    :rtype: bool
    """
    structure_changed = False
    for sample_index in range(len(original_data_forms)):
        original_data_form, new_data_forms = original_data_forms[sample_index], new_data_form_lists[sample_index]
        if original_data_form.is_valid():
            number_of_pieces = original_data_form.cleaned_data["number_of_pieces"]
            if number_of_pieces < len(new_data_forms):
                del new_data_forms[number_of_pieces:]
                structure_changed = True
            elif number_of_pieces > len(new_data_forms):
                for new_name_index in range(len(new_data_forms), number_of_pieces):
                    default_new_responsible_person = None
                    if new_data_forms[-1].is_valid():
                        default_new_responsible_person = new_data_forms[-1].cleaned_data["new_responsible_person"].pk
                    new_data_forms.append(NewDataForm(initial={"new_name": deposition_number,
                                                               "new_responsible_person": default_new_responsible_person},
                                                      prefix="%d_%d"%(sample_index, new_name_index)))
                structure_changed = True
    return structure_changed

def save_to_database(original_data_forms, new_data_form_lists, global_new_data_form, operator):
    u"""Performs all splits – if any – and renames the samples according to
    what was input by the user.

    :Parameters:
      - `original_data_forms`: all old samples and pieces numbers
      - `new_data_form_lists`: new names for all pieces
      - `global_new_data_form`: the global, overriding settings
      - `operator`: the user who performed the split

    :type original_data_forms: list of `OriginalDataForm`
    :type new_data_form_lists: list of list of `NewDataForm`
    :type global_new_data_form: `GlobalNewDataForm`
    :type operator: ``django.contrib.auth.models.User``
    """
    global_new_location = global_new_data_form.cleaned_data["new_location"]
    global_new_responsible_person = global_new_data_form.cleaned_data["new_responsible_person"]
    for original_data_form, new_data_forms in zip(original_data_forms, new_data_form_lists):
        sample = original_data_form.cleaned_data["sample"]
        if original_data_form.cleaned_data["number_of_pieces"] > 1:
            sample_split = models.SampleSplit(timestamp=datetime.datetime.now(), operator=operator, parent=sample)
            sample_split.save()
            sample.processes.add(sample_split)
            for new_data_form in new_data_forms:
                child_sample = sample.duplicate()
                child_sample.name = new_data_form.cleaned_data["new_name"]
                child_sample.split_origin = sample_split
                if global_new_location:
                    child_sample.current_location = global_new_location
                child_sample.currently_responsible_person = global_new_responsible_person if global_new_responsible_person \
                    else new_data_form.cleaned_data["new_responsible_person"]
                child_sample.save()
                child_sample.currently_responsible_person.get_profile().my_samples.add(child_sample)
        else:
            if not sample.name.startswith("*"):
                models.SampleAlias(name=sample.name, sample=sample).save()
            sample.name = new_data_forms[0].cleaned_data["new_name"]
            if global_new_location:
                sample.current_location = global_new_location
            sample.currently_responsible_person = global_new_responsible_person if global_new_responsible_person \
                else new_data_forms[0].cleaned_data["new_responsible_person"]
            sample.save()
            # Cheap heuristics to avoid re-adding samples that have been already removed from the operator's MySamples
            if sample.currently_responsible_person != operator:
                sample.currently_responsible_person.get_profile().my_samples.add(sample)

def is_referentially_valid(original_data_forms, new_data_form_lists, deposition):
    u"""Test whether all forms are consistent with each other and with the
    database.  For example, no sample name must occur twice, and the sample
    names must not exist within the database already.

    :Parameters:
      - `original_data_forms`: all old samples and pieces numbers
      - `new_data_form_lists`: new names for all pieces
      - `deposition`: the deposition after which the split takes place

    :type original_data_forms: list of `OriginalDataForm`
    :type new_data_form_lists: list of `NewDataForm`
    :type deposition: `models.Deposition`

    :Return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    samples = deposition.samples.all()
    for original_data_form in original_data_forms:
        if original_data_form.is_valid() and original_data_form.cleaned_data["sample"] not in samples:
            utils.append_error(original_data_form, _(u"Sample name %s doesn't belong to this deposition."))
            referentially_valid = False
    new_names = set()
    more_than_one_piece = sum(len(new_data_forms) for new_data_forms in new_data_form_lists) > 1
    for new_data_forms in new_data_form_lists:
        for new_data_form in new_data_forms:
            if new_data_form.is_valid():
                new_name = new_data_form.cleaned_data["new_name"]
                if more_than_one_piece and new_name == deposition.number:
                    utils.append_error(new_data_form, _(u"Since there is more than one piece, the new name "
                                                        u"must not be exactly the deposition's name."))
                    referentially_valid = False
                if new_name in new_names:
                    utils.append_error(new_data_form, _(u"This sample name has been used already on this page."))
                    referentially_valid = False
                new_names.add(new_name)
                if utils.does_sample_exist(new_name):
                    utils.append_error(new_data_form, _(u"This sample name exists already."))
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

    :rtype: list of `OriginalDataForm`, list of lists of `NewDataForm`,
      `GlobalNewDataForm`
    """
    for item in sorted(post_data.iteritems()):
        print "%s: %s" % item
    post_data, number_of_samples, list_of_number_of_new_names = utils.normalize_prefixes(post_data)
    original_data_forms = [OriginalDataForm(remote_client, post_data, prefix=str(i)) for i in range(number_of_samples)]
    new_data_form_lists = [[NewDataForm(post_data, prefix="%d_%d" % (sample_index, new_name_index))
                            for new_name_index in range(list_of_number_of_new_names[sample_index])]
                           for sample_index in range(number_of_samples)]
    global_new_data_form = GlobalNewDataForm(post_data, deposition_instance=deposition)
    return original_data_forms, new_data_form_lists, global_new_data_form

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

    :rtype: list of `OriginalDataForm`, list of lists of `NewDataForm`,
      `GlobalNewDataForm`
    """
    samples = deposition.samples
    original_data_forms = [OriginalDataForm(remote_client, initial={"sample": sample.name}, prefix=str(i))
                             for i, sample in enumerate(samples.all())]
    new_data_form_lists = [[NewDataForm(
                initial={"new_name": deposition.number, "new_responsible_person": sample.currently_responsible_person.pk},
                prefix="%d_0"%i)] for i, sample in enumerate(samples.all())]
    global_new_data_form = GlobalNewDataForm(deposition_instance=deposition)
    return original_data_forms, new_data_form_lists, global_new_data_form

@login_required
def split_and_rename_after_deposition(request, deposition_id):
    u"""View for renaming and/or splitting samples immediately after they have
    been deposited in the same run.

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_id`: the ID of the deposition after which samples should be
        split and/or renamed

    :type request: ``HttpRequest``
    :type deposition_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    deposition = get_object_or_404(models.Deposition, pk=utils.convert_id_to_int(deposition_id))
    remote_client = utils.is_remote_client(request)
    if not request.user.has_perm("samples.change_" + deposition.__class__.__name__.lower()):
        return utils.HttpResponseSeeOther("permission_error")
    if request.POST:
        original_data_forms, new_data_form_lists, global_new_data_form = \
            forms_from_post_data(request.POST, deposition, remote_client)
        all_valid = is_all_valid(original_data_forms, new_data_form_lists, global_new_data_form)
        structure_changed = change_structure(original_data_forms, new_data_form_lists, deposition.number)
        referentially_valid = is_referentially_valid(original_data_forms, new_data_form_lists, deposition)
        if all_valid and referentially_valid and not structure_changed:
            save_to_database(original_data_forms, new_data_form_lists, global_new_data_form, deposition.operator)
            if not remote_client:
                request.session["success_report"] = _(u"Samples were successfully split and/or renamed.")
                return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse("samples.views.main.main_menu"))
            else:
                return utils.respond_to_remote_client(True)
    else:
        original_data_forms, new_data_form_lists, global_new_data_form = forms_from_database(deposition, remote_client)
    return render_to_response("split_after_deposition.html",
                              {"title": _(u"Bulk sample rename for %s") % deposition,
                               "samples": zip(original_data_forms, new_data_form_lists),
                               "new_sample_data": global_new_data_form},
                              context_instance=RequestContext(request))
