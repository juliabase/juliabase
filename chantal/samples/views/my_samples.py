#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""View for doing various this with selected samples from “My Samples”.  For
example, copying them to the “My Samples” list of another user, or simply
removing them from the list.
"""

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal.samples import models, permissions
from chantal.samples.views import utils

class _MySeries(object):
    u"""Helper class for building the HTML ``<OPTGROUP>`` structure used in
    `MySamplesForm`.
    """
    def __init__(self, series):
        self.name, self.timestamp = series.name, series.timestamp
        self.samples = []
    def get_choices(self):
        self.samples.sort(key=lambda sample: sample.name)
        return (self.name, [(sample.pk, unicode(sample)) for sample in self.samples])
    def __cmp__(self, other):
        return self.timestamp > other.timestamp

class MySamplesForm(forms.Form):
    u"""Form for the “My Samples” selection box.  The clever bit here is that I
    use the ``<OPTGROUP>`` feature of HTML in order to have a structured list.
    Some samples may occur twice in the list because of this; you may select
    both without a negative effect.
    """
    _ = ugettext_lazy
    samples = forms.MultipleChoiceField(label=_(u"My Samples"))
    def __init__(self, user, *args, **keyw):
        u"""Form constructor.

        :Parameters:
          - `user`: the user whose “My Samples” list should be generated

        :type user: ``django.contrib.auth.models.User``
        """
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
        self.fields["samples"].choices = [(sample.pk, unicode(sample)) for sample in seriesless_samples] + my_series
    def clean_samples(self):
        return models.Sample.objects.in_bulk([int(pk) for pk in set(self.cleaned_data["samples"])]).values()

class ActionForm(forms.Form):
    u"""Form for all the things you can do with the selected samples.
    """
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
        u"""Form constructor.

        :Parameters:
          - `user`: the user whose “My Samples” list should be generated

        :type user: ``django.contrib.auth.models.User``
        """
        super(ActionForm, self).__init__(*args, **keyw)
        self.fields["new_currently_responsible_person"].queryset = self.fields["copy_to_user"].queryset = \
            django.contrib.auth.models.User.objects.exclude(pk=user.pk)
    def clean_comment(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        comment = self.cleaned_data["comment"]
        utils.check_markdown(comment)
        return comment
    def clean(self):
        action_data = self.cleaned_data
        if (self.cleaned_data["new_currently_responsible_person"] or self.cleaned_data["copy_to_user"]) and \
                not self.cleaned_data["comment"]:
            raise ValidationError(_(u"If you move samples over to another person, you must enter a short comment."))
        return action_data

def is_referentially_valid(current_user, my_samples_form, action_form):
    u"""Test whether all forms are consistent with each other and with the
    database.  For example, you must not change data for samples for which
    you're not the currently responsible person.

    :Parameters:
      - `current_user`: the currently logged-in user
      - `my_samples_form`: the form with the selected “My Samples”
      - `action_form`: the form with the things to be done with the selected
        samples.

    :type current_user: ``django.contrib.auth.models.User``
    :type my_samples_form: `MySamplesForm`
    :type action_form: `ActionForm`

    :Return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if not current_user.is_staff and my_samples_form.is_valid() and action_form.is_valid():
        action_data = action_form.cleaned_data
        if action_data["new_currently_responsible_person"] or action_data["new_group"] or \
                    action_data["new_current_location"]:
            try:
                for sample in my_samples_form.cleaned_data["samples"]:
                    permissions.assert_can_edit_sample(current_user, sample)
            except permissions.PermissionError:
                utils.append_error(action_form,
                                   _(u"You must be the currently responsible person for samples you'd like to change."))
                referentially_valid = False
    return referentially_valid

def save_to_database(user, my_samples_form, action_form):
    u"""Execute the things that should be done with the selected “My Samples”.

    :Parameters:
      - `user`: the user whose “My Samples” should be edited
      - `my_samples_form`: the form with the selected “My Samples”
      - `action_form`: the form with the things to be done with the selected
        samples.

    :type user: ``django.contrib.auth.models.User``
    :type my_samples_form: `MySamplesForm`
    :type action_form: `ActionForm`
    """
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

@login_required
def edit(request, username):
    u"""View for doing various things with the samples listed under “My
    Samples”.  For example, copying them to the “My Samples” list of another
    user, or simply removing them from the list.

    Note that there are two different user variables in this view and its
    associated functions.  ``current_user`` is the same as ``request.user``.
    Thus, it is the currently logged-in user.  However, ``user`` is the user
    whose “My Samples” are to be processed.  Almost always both are the same,
    especially because you are not allowed to see or change the “My Samples” of
    another user.  However, staff users *are* allowed to change them, so then
    both are different.

    :Parameters:
      - `request`: the current HTTP Request object
      - `username`: the login name of the user whose “My Samples” should be
        changed

    :type request: ``HttpRequest``
    :type username: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    if not request.user.is_staff and request.user != user:
        raise permissions.PermissionError(request.user, _(u"You can't access the “My Samples” section of another user."))
    if request.method == "POST":
        my_samples_form = MySamplesForm(user, request.POST)
        action_form = ActionForm(user, request.POST)
        referentially_valid = is_referentially_valid(request.user, my_samples_form, action_form)
        if my_samples_form.is_valid() and action_form.is_valid() and referentially_valid:
            save_to_database(user, my_samples_form, action_form)
            return utils.successful_response(request, _(u"Successfully processed “My Samples”."))
    else:
        my_samples_form = MySamplesForm(user)
        action_form = ActionForm(user)
    return render_to_response("edit_my_samples.html",
                              {"title": _(u"Edit “My Samples” of %s") % models.get_really_full_name(user),
                               "my_samples": my_samples_form, "action": action_form},
                              context_instance=RequestContext(request))
