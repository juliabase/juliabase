#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
from chantal.samples import models
from django.template import RequestContext
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.decorators import login_required
from django.forms import Form
from django import forms
from django.forms.util import ValidationError
from . import utils

class SampleForm(Form):
    _ = ugettext_lazy
    name = forms.CharField(label=_(u"Name"), max_length=30, widget=forms.TextInput(attrs={"readonly": "readonly",
                                                                        "style": "text-align: center"}))
    number_of_pieces = forms.IntegerField(label=_(u"Pieces"), initial="1",
                                          widget=forms.TextInput(attrs={"size": "3", "style": "text-align: center"}))
    def clean_number_of_pieces(self):
        if self.cleaned_data["number_of_pieces"] <= 0:
            raise ValidationError(_(u"Must be at least 1."))
        return self.cleaned_data["number_of_pieces"]

class NewNameForm(Form):
    _ = ugettext_lazy
    new_name = forms.CharField(label=_(u"Old sample name"), max_length=30)

def has_permission_for_process(user, process):
    return user.has_perm("samples.change_" + process.__class__.__name__.lower())

def is_all_valid(sample_forms, new_name_form_lists):
    valid = all([sample_form.is_valid() for sample_form in sample_forms])
    for forms in new_name_form_lists:
        valid = valid and all([new_name_form.is_valid() for new_name_form in forms])
    return valid

def change_structure(sample_forms, new_name_form_lists):
    structure_changed = False
    for sample_index in range(len(sample_forms)):
        sample_form, new_name_forms = sample_forms[sample_index], new_name_form_lists[sample_index]
        if sample_form.is_valid():
            number_of_pieces = sample_form.cleaned_data["number_of_pieces"]
            if number_of_pieces < len(new_name_forms):
                del new_name_forms[number_of_pieces:]
                structure_changed = True
            elif number_of_pieces > len(new_name_forms):
                for new_name_index in range(len(new_name_forms), number_of_pieces):
                    new_name_forms.append(NewNameForm(prefix="%d_%d"%(sample_index, new_name_index)))
                structure_changed = True
    return structure_changed

def save_to_database(sample_forms, new_name_form_lists, operator, sample_names):
    for sample_form, new_name_forms, old_name in zip(sample_forms, new_name_form_lists, sample_names):
        # I don't take the old name from `sample_form` because it may be
        # forged.
        sample = models.Sample.objects.get(name=old_name)
        if sample_form.cleaned_data["number_of_pieces"] > 1:
            sample_split = models.SampleSplit(timestamp=datetime.datetime.now(), operator=operator, parent=sample)
            sample_split.save()
            sample.processes.add(sample_split)
            for new_name_form in new_name_forms:
                child_sample = sample.duplicate()
                child_sample.name = new_name_form.cleaned_data["new_name"]
                child_sample.split_origin = sample_split
                child_sample.save()
        else:
            models.SampleAlias(name=old_name, sample=sample).save()
            sample.name = new_name_forms[0].cleaned_data["new_name"]
            sample.save()

def is_referencially_valid(new_name_form_lists):
    referencially_valid = True
    new_names = set()
    for new_name_forms in new_name_form_lists:
        for new_name_form in new_name_forms:
            if new_name_form.is_valid():
                new_name = new_name_form.cleaned_data["new_name"]
                if new_name in new_names:
                    utils.append_error(new_name_form, "__all__", _(u"This sample name has been used already on this page."))
                    referentially_valid = False
                new_names.add(new_name)
                if utils.does_sample_exist(new_name):
                    utils.append_error(new_name_form, "__all__", _(u"This sample name exists already."))
                    referentially_valid = False
    return referencially_valid

def forms_from_post_data(post_data):
    post_data, number_of_samples, list_of_number_of_new_names = utils.normalize_prefixes(post_data)
    sample_forms = [SampleForm(post_data, prefix=str(i)) for i in range(number_of_samples)]
    new_name_form_lists = [[NewNameForm(post_data, prefix="%d_%d" % (sample_index, new_name_index))
                            for new_name_index in range(list_of_number_of_new_names[sample_index])]
                           for sample_index in range(number_of_samples)]
    return sample_forms, new_name_form_lists

def forms_from_database(samples, deposition_number):
    sample_forms = [SampleForm(initial={"name": sample.name}, prefix=str(i)) for i, sample in enumerate(samples.all())]
    new_name_form_lists = [[NewNameForm(initial={"new_name": deposition_number}, prefix="%d_0"%i)]
                           for i in range(samples.count())]
    return sample_forms, new_name_form_lists

@login_required
def split_and_rename(request, process_id):
    process = get_object_or_404(models.Process, pk=process_id)
    process = process.find_actual_process()
    if not isinstance(process, (models.SixChamberDeposition,)):
        raise Http404
    if not has_permission_for_process(request.user, process):
        return HttpResponseRedirect("permission_error")
    process_name = unicode(process)
    if request.POST:
        sample_names = [sample.name for sample in process.samples.all()]
        sample_forms, new_name_form_lists = forms_from_post_data(request.POST)
        all_valid = is_all_valid(sample_forms, new_name_form_lists)
        structure_changed = change_structure(sample_forms, new_name_form_lists)
        referencially_valid = is_referencially_valid(new_name_form_lists)
        if all_valid and referencially_valid and not structure_changed:
            save_to_database(sample_forms, new_name_form_lists, process.operator, sample_names)
            request.session["success_report"] = _(u"Samples were successfully split and/or renamed.")
            return HttpResponseRedirect("../../")
    else:
        sample_forms, new_name_form_lists = forms_from_database(process.samples, process.deposition_number)
    return render_to_response("split_and_rename.html",
                              {"title": _(u"Bulk sample rename for %s") % process_name,
                               "samples": zip(sample_forms, new_name_form_lists)},
                              context_instance=RequestContext(request))
