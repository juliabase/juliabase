#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal.samples import models
from chantal.samples.views import utils

class _MySeries(object):
    def __init__(self, series):
        self.name, self.timestamp = series.name, series.timestamp
        self.samples = []
    def get_choices(self):
        self.samples.sort(key=lambda sample: sample.name)
        return (self.name, [(sample.pk, unicode(sample)) for sample in self.samples])
    def __cmp__(self, other):
        return self.timestamp > other.timestamp

class MySamplesForm(forms.Form):
    _ = ugettext_lazy
    samples = forms.MultipleChoiceField(label=_(u"My Samples"))
    def __init__(self, user, *args, **keyw):
        super(MySamplesForm, self).__init__(*args, **keyw)
        user_details = utils.get_profile(user)
        my_series = {}
        seriesless_samples = []
        for sample in user_details.my_samples.all():
            containing_series = sample.series.all()
            if not containing_series:
                seriesless_samples.append(sample)
            else:
                for series in containing_series:
                    if series.name not in my_series:
                        my_series[series.name] = _MySeries(series)
                    my_series[series.name].samples.append(sample)
        my_series = sorted(my_series.values(), key=lambda series: series.timestamp, reverse=True)
        my_series = [series.get_choices() for series in sorted(my_series, reverse=True)]
        self.fields["samples"].choices = my_series + [(sample.pk, unicode(sample)) for sample in seriesless_samples]
    def clean_samples(self):
        return models.Sample.objects.in_bulk([int(pk) for pk in set(self.cleaned_data["samples"])]).values()

class ActionForm(forms.Form):
    _ = ugettext_lazy
    new_currently_responsible_person = utils.OperatorChoiceField(
        label=_(u"New currently responsible person"), required=False, queryset=None)
    new_group = utils.ModelChoiceField(label=_(u"New Group"), queryset=django.contrib.auth.models.Group.objects,
                                       required=False)
    new_current_location = forms.CharField(label=_(u"New current location"), required=False, max_length=50)
    copy_to_user = utils.OperatorChoiceField(label=_(u"Copy to user"), required=False, queryset=None)
    comment = forms.CharField(label=_(u"Comment for recipient"), widget=forms.Textarea, required=False)
    remove_from_my_samples = forms.BooleanField(label=_(u"Remove from “My Samples”"), required=False)
    def __init__(self, user, *args, **keyw):
        super(ActionForm, self).__init__(*args, **keyw)
        self.fields["new_currently_responsible_person"].queryset = self.fields["copy_to_user"].queryset = \
            django.contrib.auth.models.User.objects.exclude(pk=user.pk)

def is_referentially_valid(current_user, user, my_samples_form, action_form):
    referentially_valid = True
    if not current_user.is_staff and my_samples_form.is_valid() and action_form.is_valid():
        action_data = action_form.cleaned_data
        if action_data["new_currently_responsible_person"] or action_data["new_group"] or \
                    action_data["new_current_location"]:
            for sample in my_samples_form.cleaned_data["samples"]:
                if sample.currently_responsible_person != current_user:
                    utils.append_error(action_form,
                                       _(u"You must be the currently responsible person for samples you'd like to change."))
                    referentially_valid = False
                    break
    if action_form.is_valid():
        action_data = action_form.cleaned_data
        if (action_data["new_currently_responsible_person"] or action_data["copy_to_user"]) and not action_data["comment"]:
            utils.append_error(
                action_form, _(u"If you move the sample over to another person, you must enter a short comment."), "comment")
            referentially_valid = False
    return referentially_valid

@login_required
def edit(request, username):
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    if not request.user.is_staff and request.user != user:
        return utils.HttpResponseSeeOther("permission_error")
    comment_preview = None
    if request.method == "POST":
        my_samples_form = MySamplesForm(user, request.POST)
        action_form = ActionForm(user, request.POST)
        if action_form.is_valid():
            comment_preview = action_form.cleaned_data["comment"]
        referentially_valid = is_referentially_valid(request.user, user, my_samples_form, action_form)
        if my_samples_form.is_valid() and action_form.is_valid() and referentially_valid:
            action_data = action_form.cleaned_data
            if action_data["copy_to_user"]:
                recipient_my_samples = utils.get_profile(action_data["copy_to_user"]).my_samples
            if action_data["remove_from_my_samples"]:
                current_user_my_samples = utils.get_profile(user).my_samples
            for sample in my_samples_form.cleaned_data["samples"]:
                if action_data["new_currently_responsible_person"]:
                    sample.currently_responsible_person = action_data["new_currently_responsible_person"]
                if action_data["new_group"]:
                    sample.group = action_data["new_group"]
                if action_data["new_current_location"]:
                    sample.current_location = action_data["new_current_location"]
                sample.save()
                if action_data["copy_to_user"]:
                    recipient_my_samples.add(sample)
                if action_data["remove_from_my_samples"]:
                    current_user_my_samples.remove(sample)
            return utils.successful_response(request, _(u"Successfully processed “My Samples”."))
    else:
        my_samples_form = MySamplesForm(user)
        action_form = ActionForm(user)
    return render_to_response("edit_my_samples.html",
                              {"title": _(u"Edit “My Samples” of %s") % models.get_really_full_name(user),
                               "my_samples": my_samples_form, "action": action_form, "comment_preview": comment_preview},
                              context_instance=RequestContext(request))
