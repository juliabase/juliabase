#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""View for doing various this with selected samples from “My Samples”.  For
example, copying them to the “My Samples” list of another user, or simply
removing them from the list.
"""

from __future__ import absolute_import

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.http import Http404
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
import chantal_common.utils
from chantal_common.utils import append_error, get_really_full_name
from samples import models, permissions
from samples.views import utils, form_utils, feed_utils


class MySamplesForm(forms.Form):
    _ = ugettext_lazy
    samples = form_utils.MultipleSamplesField(label=_(u"My Samples"))

    def __init__(self, user_details, *args, **kwargs):
        super(MySamplesForm, self).__init__(*args, **kwargs)
        self.fields["samples"].set_samples(user_details.my_samples.all())


class ActionForm(forms.Form):
    u"""Form for all the things you can do with the selected samples.
    """
    _ = ugettext_lazy
    new_currently_responsible_person = form_utils.UserField(label=_(u"New currently responsible person"), required=False)
    new_topic = form_utils.TopicField(label=_(u"New Topic"), required=False)
    new_current_location = forms.CharField(label=_(u"New current location"), required=False, max_length=50)
    copy_to_user = form_utils.UserField(label=_(u"Copy to user"), required=False)
    clearance = forms.ChoiceField(label=_("Clearance"), required=False)
    comment = forms.CharField(label=_(u"Comment for recipient"), widget=forms.Textarea, required=False)
    remove_from_my_samples = forms.BooleanField(label=_(u"Remove from “My Samples”"), required=False)

    def __init__(self, user, *args, **kwargs):
        u"""Form constructor.

        :Parameters:
          - `user`: the user whose “My Samples” list should be generated

        :type user: ``django.contrib.auth.models.User``
        """
        super(ActionForm, self).__init__(*args, **kwargs)
        self.fields["new_currently_responsible_person"].set_users_without(user)
        self.fields["copy_to_user"].set_users_without(user)
        self.fields["new_topic"].set_topics(user)
        self.fields["clearance"].choices = [("", u"---------"), ("0", _(u"sample only")),
                                            ("1", _(u"all processes up to now"))]
        self.fields["clearance"].choices.extend((str(i), name) for i, name in enumerate(models.clearance_sets, 2))
        self.clearance_choices = {"": None, "0": (), "1": "all"}
        self.clearance_choices.update((i, models.clearance_sets[name]) for i, name in self.fields["clearance"].choices[3:])

    def clean_comment(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        comment = self.cleaned_data["comment"]
        chantal_common.utils.check_markdown(comment)
        return comment

    def clean_clearance(self):
        return self.clearance_choices[self.cleaned_data["clearance"]]

    def clean(self):
        cleaned_data = self.cleaned_data
        if cleaned_data["copy_to_user"]:
            if not cleaned_data["comment"]:
                append_error(self, _(u"If you copy samples over to another person, you must enter a short comment."),
                             "comment")
        if cleaned_data["clearance"] is not None and not cleaned_data.get("copy_to_user"):
                append_error(self, _(u"If you set a clearance, you must copy samples to another user."), "copy_to_user")
                del cleaned_data["clearance"]
        if (cleaned_data["new_currently_responsible_person"] or cleaned_data["new_topic"] or
            cleaned_data["new_current_location"]) and not cleaned_data["comment"]:
            raise ValidationError(_(u"If you edit samples, you must enter a short comment."))
        return cleaned_data


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
    if my_samples_form.is_valid() and action_form.is_valid():
        if not current_user.is_staff:
            action_data = action_form.cleaned_data
            if action_data["new_currently_responsible_person"] or action_data["new_topic"] or \
                        action_data["new_current_location"]:
                try:
                    for sample in my_samples_form.cleaned_data["samples"]:
                        permissions.assert_can_edit_sample(current_user, sample)
                except permissions.PermissionError:
                    append_error(action_form,
                                 _(u"You must be the currently responsible person for samples you'd like to change."))
                    referentially_valid = False
        if action_form.cleaned_data["clearance"] is None:
            try:
                for sample in my_samples_form.cleaned_data["samples"]:
                    permissions.assert_can_fully_view_sample(action_form.cleaned_data["copy_to_user"], sample)
                    print permissions.has_permission_to_fully_view_sample(action_form.cleaned_data["copy_to_user"], sample)
            except permissions.PermissionError:
                append_error(action_form, _(u"If you copy samples over to another person who cannot fully view one of the "
                                            u"samples, you must select a clearance option."), "clearance")
                referentially_valid = False
    return referentially_valid


def enforce_clearance(clearance_processes, destination_user, sample, clearance=None, cutoff_timestamp=None):
    u"""Unblocks specified processes of a sample for a given user.

    :Parameters:
      - `clearance_processes`: all process classes that the destination user
        should be able to see; ``"all"`` means all processes
      - `destination_user`: the user for whom the sample should be unblocked
      - `sample`: the sample to be unblocked
      - `clearance`: The current clearance to which further unblocked processes
        should be added.  This is only used in the internal recursion of this
        routine in order to traverse through sample splits upwards.
      - `cutoff_timestamp`: The timestamp after which no processes in the
        sample should be unblocked.  This is only used in the internal
        recursion of this routine in order to traverse through sample splits
        upwards.  It is a similar algorithm as the one used in
        `samples.views.sample.ProcessContext`.

    :type clearance_processes: tuple of `models.Process`, or str
    :type destination_user: ``django.contrib.auth.models.User``
    :type sample: `models.Sample`
    :type clearance: `models.Clearance`
    :type cutoff_timestamp: ``datetime.datetime``
    """
    if not clearance:
        clearance, __ = models.Clearance.objects.get_or_create(user=destination_user, sample=sample)
    processes = sample.processes.all() if not cutoff_timestamp else sample.processes.filter(timestamp__lte=cutoff_timestamp)
    for process in processes:
        if clearance_processes == "all" or isinstance(process.find_actual_instance(), clearance_processes):
            clearance.processes.add(process)
    split_origin = sample.split_origin
    if split_origin:
        enforce_clearance(clearance_processes, destination_user, split_origin.parent, clearance, split_origin.timestamp)


def save_to_database(user, my_samples_form, action_form):
    u"""Execute the things that should be done with the selected “My Samples”.
    I do also the feed generation here.

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
    samples = my_samples_form.cleaned_data["samples"]
    samples_with_new_responsible_person = []
    samples_with_new_topic = {}
    for sample in samples:
        old_topic, old_responsible_person = sample.topic, sample.currently_responsible_person
        if action_data["new_currently_responsible_person"] and \
                action_data["new_currently_responsible_person"] != sample.currently_responsible_person:
            sample.currently_responsible_person = action_data["new_currently_responsible_person"]
            samples_with_new_responsible_person.append(sample)
        if action_data["new_topic"] and action_data["new_topic"] != sample.topic:
            if sample.topic not in samples_with_new_topic:
                samples_with_new_topic[sample.topic] = [sample]
            else:
                samples_with_new_topic[sample.topic].append(sample)
            sample.topic = action_data["new_topic"]
        if action_data["new_current_location"]:
            sample.current_location = action_data["new_current_location"]
        sample.save()
        if sample.topic and sample.topic != old_topic:
            for watcher in sample.topic.auto_adders.all():
                watcher.my_samples.add(sample)
        if sample.currently_responsible_person != old_responsible_person:
            utils.get_profile(sample.currently_responsible_person).my_samples.add(sample)
        if action_data["copy_to_user"]:
            recipient_my_samples.add(sample)
            if action_data["clearance"] is not None:
                enforce_clearance(action_data["clearance"], action_data["copy_to_user"], sample)
        if action_data["remove_from_my_samples"]:
            current_user_my_samples.remove(sample)
    feed_reporter = feed_utils.Reporter(user)
    edit_description = {"important": True, "description": action_data["comment"]}
    if samples_with_new_responsible_person:
        feed_reporter.report_new_responsible_person_samples(samples_with_new_responsible_person, edit_description)
    for old_topic, samples in samples_with_new_topic.iteritems():
        feed_reporter.report_changed_sample_topic(samples, old_topic, edit_description)
    if action_data["new_currently_responsible_person"] or action_data["new_current_location"] or action_data["new_topic"]:
        feed_reporter.report_edited_samples(samples, edit_description)
    # Now a separate(!) message for copied samples
    if action_data["copy_to_user"]:
        feed_utils.Reporter(user).report_copied_my_samples(samples, action_data["copy_to_user"], action_data["comment"])


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
    user_details = utils.get_profile(user)
    if not request.user.is_staff and request.user != user:
        raise permissions.PermissionError(request.user, _(u"You can't access the “My Samples” section of another user."))
    if request.method == "POST":
        my_samples_form = MySamplesForm(user_details, request.POST)
        action_form = ActionForm(user, request.POST)
        referentially_valid = is_referentially_valid(request.user, my_samples_form, action_form)
        if my_samples_form.is_valid() and action_form.is_valid() and referentially_valid:
            save_to_database(user, my_samples_form, action_form)
            return utils.successful_response(request, _(u"Successfully processed “My Samples”."))
    else:
        my_samples_form = MySamplesForm(user_details)
        action_form = ActionForm(user)
    return render_to_response("samples/edit_my_samples.html",
                              {"title": _(u"Edit “My Samples” of %s") % get_really_full_name(user),
                               "my_samples": my_samples_form, "action": action_form},
                              context_instance=RequestContext(request))
