#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponseRedirect
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms.util import ValidationError
from chantal.samples import models
from . import utils

class NewNameForm(forms.Form):
    _ = ugettext_lazy
    new_name = forms.CharField(label=_(u"New sample name"), max_length=30)
    delete = forms.BooleanField(label=_(u"Delete"), required=False)
    def clean_new_name(self):
        if utils.does_sample_exist(self.cleaned_data["new_name"]):
            raise ValidationError(_(u"Name does already exist in database."))
        return self.cleaned_data["new_name"]

class GlobalDataForm(forms.Form):
    _ = ugettext_lazy

def forms_from_post_data(post_data, sample_name):
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
            new_name_forms.append(NewNameForm(post_data, prefix=str(index)))
            last_deleted = False
        index += 1
    print index
    if not last_deleted and post_data.get("%d-new_name" % (index-1), sample_name) == sample_name:
        del new_name_forms[-1]
    else:
        structure_changed = True
    return new_name_forms, structure_changed

def is_referentially_valid(new_name_forms, global_data_form):
    referentially_valid = True
    if not new_name_forms:
        utils.append_error(global_data_form, "__all__", _(u"You must split into at least one piece."))
        referentially_valid = False
    new_names = set()
    for new_name_form in new_name_forms:
        if new_name_form.is_valid():
            new_name = new_name_form.cleaned_data["new_name"]
            print new_name, new_names
            if new_name in new_names or utils.does_sample_exist(new_name):
                utils.append_error(new_name_form, "__all__", _(u"Name is already given."))
                referentially_valid = False
            new_names.add(new_name)
    return referentially_valid
        
@login_required
def split_and_rename(request, sample_name):
    lookup_result = utils.lookup_sample(sample_name, request)
    if lookup_result:
        return lookup_result
    if request.method == "POST":
        global_data_form = GlobalDataForm(request.POST)
        print global_data_form.is_valid()
        new_name_forms, structure_changed = forms_from_post_data(request.POST, sample_name)
        all_valid = all([new_name_form.is_valid() for new_name_form in new_name_forms])
        referentially_valid = is_referentially_valid(new_name_forms, global_data_form)
        if all_valid and referentially_valid and not structure_changed:
#            save_to_database(new_name_forms)
            return HttpResponseRedirect("../")
    else:
        new_name_forms = []
    new_name_forms.append(NewNameForm(initial={"new_name": sample_name}, prefix=str(len(new_name_forms))))
    return render_to_response("split_and_rename.html", {"title": _(u"Split sample “%s”") % sample_name,
                                                        "new_names": new_name_forms, "global_data": global_data_form},
                              context_instance=RequestContext(request))

