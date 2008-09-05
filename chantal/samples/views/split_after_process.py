#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from . import utils

class OriginalDataForm(Form):
    _ = ugettext_lazy
    name = forms.CharField(label=_(u"Old sample name"), max_length=30,
                           widget=forms.TextInput(attrs={"readonly": "readonly", "style": "text-align: center"}))
    number_of_pieces = forms.IntegerField(label=_(u"Pieces"), initial="1",
                                          widget=forms.TextInput(attrs={"size": "3", "style": "text-align: center"}))
    def clean_number_of_pieces(self):
        if self.cleaned_data["number_of_pieces"] <= 0:
            raise ValidationError(_(u"Must be at least 1."))
        return self.cleaned_data["number_of_pieces"]

class NewDataForm(Form):
    _ = ugettext_lazy
    new_name = forms.CharField(label=_(u"New sample name"), max_length=30)
    new_responsible_person = utils.OperatorChoiceField(label=_(u"New responsible person"), queryset=None)
    def __init__(self, data=None, **keyw):
        super(NewDataForm, self).__init__(data, **keyw)
        self.fields["new_name"].widget = forms.TextInput(attrs={"size": "15"})
        self.fields["new_responsible_person"].queryset = django.contrib.auth.models.User.objects.all()

class GlobalNewDataForm(Form):
    _ = ugettext_lazy
    new_responsible_person = utils.OperatorChoiceField(
        label=_(u"New responsible person"), required=False, queryset=None,
        help_text=_(u"(for all samples; overrides individual settings above)"), empty_label=_(u"(no global change)"))
    new_location = forms.CharField(label=_(u"New current location"), max_length=50, required=False,
                                   help_text=_(u"(for all samples; leave empty for no change)"))
    def __init__(self, data=None, **keyw):
        process_instance = keyw.pop("process_instance")
        super(GlobalNewDataForm, self).__init__(data, **keyw)
        self.fields["new_responsible_person"].queryset = django.contrib.auth.models.User.objects.all()
        self.fields["new_location"].initial = \
            models.default_location_of_processed_samples.get(process_instance.__class__, u"")
        self.fields["new_location"].widget = forms.TextInput(attrs={"size": "40"})

def has_permission_for_process(user, process):
    return user.has_perm("samples.change_" + process.__class__.__name__.lower())

def is_all_valid(original_data_forms, new_data_form_lists, global_new_data_form):
    valid = all([original_data_form.is_valid() for original_data_form in original_data_forms])
    for forms in new_data_form_lists:
        valid = valid and all([new_data_form.is_valid() for new_data_form in forms])
    valid = valid and global_new_data_form.is_valid()
    return valid

def change_structure(original_data_forms, new_data_form_lists, process_number):
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
                    new_data_forms.append(NewDataForm(initial={"new_name": process_number,
                                                               "new_responsible_person": default_new_responsible_person},
                                                      prefix="%d_%d"%(sample_index, new_name_index)))
                structure_changed = True
    return structure_changed

def save_to_database(original_data_forms, new_data_form_lists, global_new_data_form, operator, sample_names):
    global_new_location = global_new_data_form.cleaned_data["new_location"]
    global_new_responsible_person = global_new_data_form.cleaned_data["new_responsible_person"]
    for original_data_form, new_data_forms, old_name in zip(
        original_data_forms, new_data_form_lists, sample_names):
        # I don't take the old name from `original_data_form` because it may be
        # forged.
        sample = models.Sample.objects.get(name=old_name)
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
            if not old_name.startswith("*"):
                models.SampleAlias(name=old_name, sample=sample).save()
            sample.name = new_data_forms[0].cleaned_data["new_name"]
            if global_new_location:
                sample.current_location = global_new_location
            sample.currently_responsible_person = global_new_responsible_person if global_new_responsible_person \
                else new_data_forms[0].cleaned_data["new_responsible_person"]
            sample.save()
            # Cheap heuristics to avoid re-adding samples that have been already removed from the operator's MySamples
            if sample.currently_responsible_person != operator:
                sample.currently_responsible_person.get_profile().my_samples.add(sample)

def is_referentially_valid(new_data_form_lists, process_name):
    referentially_valid = True
    new_names = set()
    more_than_one_piece = sum(len(new_data_forms) for new_data_forms in new_data_form_lists) > 1
    for new_data_forms in new_data_form_lists:
        for new_data_form in new_data_forms:
            if new_data_form.is_valid():
                new_name = new_data_form.cleaned_data["new_name"]
                if more_than_one_piece and new_name == process_name:
                    utils.append_error(new_data_form, "__all__", _(u"Since there is more than one piece, the new name "
                                                                   u"must not be exactly the deposition's name."))
                    referentially_valid = False
                if new_name in new_names:
                    utils.append_error(new_data_form, "__all__", _(u"This sample name has been used already on this page."))
                    referentially_valid = False
                new_names.add(new_name)
                if utils.does_sample_exist(new_name):
                    utils.append_error(new_data_form, "__all__", _(u"This sample name exists already."))
                    referentially_valid = False
    return referentially_valid

def forms_from_post_data(post_data, process):
    post_data, number_of_samples, list_of_number_of_new_names = utils.normalize_prefixes(post_data)
    original_data_forms = [OriginalDataForm(post_data, prefix=str(i)) for i in range(number_of_samples)]
    new_data_form_lists = [[NewDataForm(post_data, prefix="%d_%d" % (sample_index, new_name_index))
                            for new_name_index in range(list_of_number_of_new_names[sample_index])]
                           for sample_index in range(number_of_samples)]
    global_new_data_form = GlobalNewDataForm(post_data, process_instance=process)
    return original_data_forms, new_data_form_lists, global_new_data_form

def forms_from_database(process):
    samples = process.samples
    original_data_forms = [OriginalDataForm(initial={"name": sample.name}, prefix=str(i))
                             for i, sample in enumerate(samples.all())]
    new_data_form_lists = [[NewDataForm(
                initial={"new_name": process.number, "new_responsible_person": sample.currently_responsible_person.pk},
                prefix="%d_0"%i)] for i, sample in enumerate(samples.all())]
    global_new_data_form = GlobalNewDataForm(process_instance=process)
    return original_data_forms, new_data_form_lists, global_new_data_form

@login_required
def split_and_rename_after_process(request, process_id):
    process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id))
    process = process.find_actual_instance()
    if not isinstance(process, models.Deposition):
        raise Http404
    if not has_permission_for_process(request.user, process):
        return utils.HttpResponseSeeOther("permission_error")
    process_name = unicode(process)
    if request.POST:
        sample_names = [sample.name for sample in process.samples.all()]
        original_data_forms, new_data_form_lists, global_new_data_form = forms_from_post_data(request.POST, process)
        all_valid = is_all_valid(original_data_forms, new_data_form_lists, global_new_data_form)
        structure_changed = change_structure(original_data_forms, new_data_form_lists, process.number)
        referentially_valid = is_referentially_valid(new_data_form_lists, process.number)
        if all_valid and referentially_valid and not structure_changed:
            save_to_database(original_data_forms, new_data_form_lists, global_new_data_form, process.operator, sample_names)
            request.session["success_report"] = _(u"Samples were successfully split and/or renamed.")
            return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse("samples.views.main.main_menu"))
    else:
        original_data_forms, new_data_form_lists, global_new_data_form = forms_from_database(process)
    return render_to_response("split_after_process.html",
                              {"title": _(u"Bulk sample rename for %s") % process_name,
                               "samples": zip(original_data_forms, new_data_form_lists),
                               "new_sample_data": global_new_data_form},
                              context_instance=RequestContext(request))
