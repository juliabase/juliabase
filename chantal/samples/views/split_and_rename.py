#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import Http404, HttpResponseRedirect
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms.util import ValidationError
from django.db.models import Q
from chantal.samples import models
from . import utils

class NewNameForm(forms.Form):
    _ = ugettext_lazy
    new_name = forms.CharField(label=_(u"New sample name"), max_length=30)
    new_purpose = forms.CharField(label=_(u"New sample purpose"), max_length=80)
    delete = forms.BooleanField(label=_(u"Delete"), required=False)
    def clean_new_name(self):
        if utils.does_sample_exist(self.cleaned_data["new_name"]):
            raise ValidationError(_(u"Name does already exist in database."))
        if self.cleaned_data["new_name"].startswith("*"):
            raise ValidationError(_(u"You must not give a provisional name, i.e., it must not start with “*”."))
        return self.cleaned_data["new_name"]

class GlobalDataForm(forms.Form):
    _ = ugettext_lazy
    finished = forms.BooleanField(label=_(u"All pieces completely entered"), required=False)
    sample_completely_split = forms.BooleanField(label=_(u"Sample was completely split"), initial=True, required=False)
    sample_series = forms.ModelChoiceField(label=_(u"Sample series"), queryset=None, required=False)
    def __init__(self, parent, user_details, data=None, **keyw):
        super(GlobalDataForm, self).__init__(data, **keyw)
        now = datetime.datetime.now() + datetime.timedelta(seconds=5)
        three_months_ago = now - datetime.timedelta(days=90)
        self.fields["sample_series"].queryset = \
            models.SampleSeries.objects.filter(currently_responsible_person=user_details.user)

def forms_from_post_data(post_data, parent, user_details):
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
    if not last_deleted and post_data.get("%d-new_name" % (index-1), parent.name) == parent.name:
        del new_name_forms[-1]
    else:
        structure_changed = True
    global_data_form = GlobalDataForm(parent, user_details, post_data)
    return new_name_forms, global_data_form, structure_changed

def forms_from_database(parent, user_details):
    new_name_forms = []
    global_data_form = GlobalDataForm(parent, user_details)
    return new_name_forms, global_data_form

def is_all_valid(new_name_forms, global_data_form):
    all_valid = all([new_name_form.is_valid() for new_name_form in new_name_forms])
    all_valid = global_data_form.is_valid() and all_valid  # Ordering important: .is_valid() must be called
    return all_valid

def is_referentially_valid(new_name_forms, global_data_form):
    referentially_valid = global_data_form.cleaned_data["finished"]
    if not new_name_forms:
        utils.append_error(global_data_form, "__all__", _(u"You must split into at least one piece."))
        referentially_valid = False
    new_names = set()
    for new_name_form in new_name_forms:
        if new_name_form.is_valid():
            new_name = new_name_form.cleaned_data["new_name"]
            if new_name in new_names or utils.does_sample_exist(new_name):
                utils.append_error(new_name_form, "__all__", _(u"Name is already given."))
                referentially_valid = False
            new_names.add(new_name)
    return referentially_valid

def save_to_database(new_name_forms, global_data_form, parent, sample_split, user):
    now = datetime.datetime.now()
    if not sample_split:
        sample_split = models.SampleSplit(timestamp=now, operator=user, parent=parent)
        sample_split.save()
        parent.processes.add(sample_split)
    else:
        sample_split.timestamp = now
        sample_split.operator = user
        sample_split.save()
    if global_data_form.cleaned_data["sample_completely_split"]:
        for watcher in parent.watchers.all():
            watcher.my_samples.remove(parent)
        death = models.SampleDeath(timestamp=now+datetime.timedelta(seconds=5), operator=user, reason="split")
        death.save()
        parent.processes.add(death)
    sample_series = global_data_form.cleaned_data["sample_series"]
    for new_name_form in new_name_forms:
        child = models.Sample(name=new_name_form.cleaned_data["new_name"],
                              current_location=parent.current_location,
                              currently_responsible_person=user,
                              purpose=new_name_form.cleaned_data["new_purpose"], tags=parent.tags,
                              split_origin=sample_split,
                              group=parent.group)
        child.save()
        for watcher in parent.watchers.all():
            watcher.my_samples.add(child)
        if sample_series:
            sample_series.samples.add(child)
        
@login_required
def split_and_rename(request, parent_name=None, old_split_id=None):
    assert (parent_name or old_split_id) and not (parent_name and old_split_id)
    if parent_name:
        parent, redirect = utils.lookup_sample(parent_name, request)
        if redirect:
            return redirect
        old_split = None
    else:
        old_split = get_object_or_404(models.SampleSplit, pk=old_split_id)
        parent = old_split.parent
        if parent.processes.filter(timestamp__gt=old_split.timestamp).count():
            raise Http404(_(u"This split is not the last one in the sample's process list."))
        if not utils.has_permission_for_sample(request.user, parent):
            return HttpResponseRedirect("permission_error")
    user_details = request.user.get_profile()
    if request.method == "POST":
        new_name_forms, global_data_form, structure_changed = forms_from_post_data(request.POST, parent, user_details)
        all_valid = is_all_valid(new_name_forms, global_data_form)
        referentially_valid = is_referentially_valid(new_name_forms, global_data_form)
        if all_valid and referentially_valid and not structure_changed:
            save_to_database(new_name_forms, global_data_form, parent, old_split, request.user)
            return HttpResponseRedirect("../")
    else:
        new_name_forms, global_data_form = forms_from_database(parent, user_details)
    new_name_forms.append(NewNameForm(initial={"new_name": parent.name, "new_purpose": parent.purpose},
                                      prefix=str(len(new_name_forms))))
    number_of_old_pieces = old_split.pieces.count()
    return render_to_response("split_and_rename.html", {"title": _(u"Split sample “%s”") % parent.name,
                                                        "new_names": zip(range(number_of_old_pieces+1,
                                                                               number_of_old_pieces+1+len(new_name_forms)),
                                                                         new_name_forms),
                                                        "global_data": global_data_form,
                                                        "old_split": old_split},
                              context_instance=RequestContext(request))

