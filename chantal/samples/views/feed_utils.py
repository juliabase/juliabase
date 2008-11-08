#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Helper routines for generating single feed entries.  They are called by
views shortly after the database was changed in one way or another.
"""

from chantal.samples import models
from chantal.samples.views import utils
from chantal.samples import permissions

class Reporter(object):
    def __init__(self, originator):
        self.interested_users = set()
        self.already_informed_users = set()
        self.originator = originator
    def inform_users(self, entry):
        self.interested_users -= self.already_informed_users
        self.already_informed_users.update(self.interested_users)
        self.interested_users.discard(utils.get_profile(self.originator))
        entry.users = self.interested_users
        self.interested_users = set()
    def add_interested_users(self, samples, important=True):
        for sample in samples:
            for user in sample.watchers.all():
                if (important or not user.only_important_news) and \
                        permissions.has_permission_to_view_sample(user.user, sample):
                    self.interested_users.add(user)
    def add_watchers(self, process_or_sample_series, important=True):
        self.add_interested_users(process_or_sample_series.samples.all(), important)
    def add_group_members(self, group):
        self.interested_users.update(utils.get_profile(user) for user in group.user_set.all())
    def generate_feed_new_samples(self, samples):
        u"""Generate one feed entry for new samples.

        :Parameters:
          - `samples`: the samples that were added

        :type samples: list of `models.Sample`
        """
        group = samples[0].group
        common_purpose = samples[0].purpose
        if group:
            entry = models.FeedNewSamples.objects.create(originator=self.originator, group=group, purpose=common_purpose)
            entry.samples = samples
            entry.auto_adders = group.auto_adders.all()
            self.add_group_members(group)
            self.inform_users(entry)
    def generate_feed_for_physical_process(self, process, edit_description_form=None):
        u"""Generate a feed entry for a physical process (deposition, measurement,
        etching etc) which was recently edited or created.

        :Parameters:
          - `process`: the process which was added/edited recently
          - `edit_description_form`: the form containing data about what was edited
            in the process.  ``None`` if the process was newly created.

        :type process: `models.Process`
        :type edit_description_form: `form_utils.EditDescriptionForm`
        """
        if edit_description_form:
            entry = models.FeedEditedPhysicalProcess.objects.create(
                originator=self.originator, process=process,
                description=edit_description_form.cleaned_data["description"],
                important=edit_description_form.cleaned_data["important"])
            self.add_watchers(process, entry.important)
            self.inform_users(entry)
        else:
            entry = models.FeedNewPhysicalProcess.objects.create(originator=user, process=process)
            self.add_watchers(process)
            self.inform_users(entry)
    def generate_feed_for_result_process(self, result, edit_description_form=None):
        u"""Generate a feed entry for a physical process (deposition, measurement,
        etching etc) which was recently edited or created.

        :Parameters:
          - `result`: the result process which was added/edited recently
          - `edit_description_form`: the form containing data about what was edited
            in the result.  ``None`` if the process was newly created.

        :type result: `models.Result`
        :type edit_description_form: `form_utils.EditDescriptionForm`
        """
        if edit_description_form:
            entry = models.FeedResult.objects.create(
                originator=self.originator, result=result, is_new=False,
                description=edit_description_form.cleaned_data["description"],
                important=edit_description_form.cleaned_data["important"])
        else:
            entry = models.FeedResult.objects.create(originator=self.originator, result=result, is_new=True)
        self.add_watchers(result, entry.important)
        for sample_series in result.sample_series.all():
            self.add_watchers(sample_series)
        self.inform_users(entry)
    def generate_feed_for_copied_my_samples(self, samples, recipient, comments):
        entry = models.FeedCopiedMySamples.objects.create(originator=self.originator, comments=comments)
        entry.samples = samples
        self.interested_users.add(utils.get_profile(recipient))
        self.inform_users(entry)
    def generate_feed_for_new_responsible_person_samples(self, samples, old_responsible_person, edit_description_form):
        entry = models.FeedEditedSamples.objects.create(
            originator=self.originator, description=edit_description_form.cleaned_data["description"],
            important=edit_description_form.cleaned_data["important"], responsible_person_changed=True)
        entry.samples = samples
        self.interested_users.add(utils.get_profile(samples[0].currently_responsible_person))
        self.inform_users(entry)
    def generate_feed_changed_sample_group(self, samples, old_group, edit_description_form):
        important = edit_description_form.cleaned_data["important"]
        group = samples[0].group
        entry = models.FeedMovedSamples.objects.create(
            originator=self.originator, description=edit_description_form.cleaned_data["description"],
            important=important, group=group, old_group=old_group)
        entry.samples = samples
        entry.auto_adders = group.auto_adders.all()
        if old_group:
            self.add_group_members(old_group)
        self.add_group_members(group)
        self.inform_users(entry)
    def generate_feed_for_edited_samples(self, samples, edit_description_form):
        important = edit_description_form.cleaned_data["important"]
        entry = models.FeedEditedSamples.objects.create(
            originator=self.originator, description=edit_description_form.cleaned_data["description"], important=important)
        entry.samples = samples
        self.add_interested_users(samples, important)
        self.inform_users(entry)
