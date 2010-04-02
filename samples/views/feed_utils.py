#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Code for generating feed entries.  They are called by views shortly after
the database was changed in one way or another.
"""

from __future__ import absolute_import

from samples import models
from samples.views import utils
from samples import permissions


class Reporter(object):
    u"""This class contains all feed-generating routines as methods.  Their
    names start with ``report_...``.  The main reason for putting them into a
    class is that this class assures that no user gets two feed entries.
    Therefore, if you want to report a certain database change to the users,
    create an instance of ``Reporter`` and call all methods that are related to
    the database change.  Call the most meaningful method first, and the most
    general last.  For example, when changing the data of a sample, the
    respective view calls the following methods in this order::

        report_new_responsible_person_samples
        report_changed_sample_group
        report_edited_samples

    Of course, the first two are only called if the respective data change
    really happend.  Thus, the new responsible person is signalled first, then
    all people about a possible group change, and if this didn't happen, all
    so-far un-signalled users get a general message about changed sample data.

    If you want to signal something to all possibly interested users, no matter
    on which feed entries they already have received, just create a new
    instance of ``Reporter``.

    Mostly, you can call the method directly without binding the instance of
    ``Reporter`` to a name, as in::

        feed_utils.Reporter(request.user).report_result_process(
                result, edit_description=None)

    Note that some internal data structures here seem to contain users but in
    fact they contains user *details*.

    :ivar interested_users: all users that get informed with the next generated
      feed entry by a call to `__connect_with_users`

    :ivar already_informed_users: All users who have already received a feed
      entry from this instance of ``Reporter``.  They won't get a second
      entry.

    :ivar originator: the user responsible for the databse change reported by
      the feed entry of this instance of ``Reporter``.

    :type interested_users: set of `models.UserDetails`
    :type already_informed_users: set of `models.UserDetails`
    :type originator: ``django.contrib.auth.models.User``
    """

    def __init__(self, originator):
        u"""Class constructor.

        :Parameters:
          - `originator`: the user who did the database change to be reported;
            almost always, this is the currently logged-in user

        :type originator: ``django.contrib.auth.models.User``
        """
        self.interested_users = set()
        self.already_informed_users = set()
        self.originator = originator

    def __connect_with_users(self, entry):
        u"""Take an already generated feed entry and set its recipients to all
        users that are probably interested in this news (and allowed to see
        it).  This method ensures that neither the originator, nor users who
        have already received another feed entry get the current ``entry``.

        If the entry would be connected with no interested users, it is
        deleted.

        :Parameters:
          - `entry`: the feed entry that should be connected with users that
            should receive it

        :type entry: `models.FeedEntry`
        """
        self.interested_users -= self.already_informed_users
        self.already_informed_users.update(self.interested_users)
        self.interested_users.discard(utils.get_profile(self.originator))
        if self.interested_users:
            entry.users = self.interested_users
        else:
            entry.delete()
        self.interested_users = set()

    def __add_interested_users(self, samples, important=True):
        u"""Add users interested in news about the given samples.  These are
        all users that have one of ``samples`` on their “My Samples” list,
        *and* the level of importance is enough.  They are added to the set of
        users connected with the next generated feed entry by `__connect_with_users`.

        :Parameters:
          - `samples`: the samples involved in the database change
          - `important`: whether the news is marked as being important;
            defaults to ``True``

        :type samples: list of `models.Sample`
        :type important: bool
        """
        for sample in samples:
            for user in sample.watchers.all():
                if (important or not user.only_important_news) and \
                        permissions.has_permission_to_view_sample(user.user, sample):
                    self.interested_users.add(user)

    def __add_watchers(self, process_or_sample_series, important=True):
        u"""Add users interested in news about the given process or sample
        series.  They are added to the set of users connected with the next
        generated feed entry by `__connect_with_users`.  The odd unification of
        processes and sample series stems from the fact that both share the
        attribute ``samples`` as a many-to-many relationship.  Thus, I use
        duck-typing here.

        :Parameters:
          - `process_or_sample_series`: the process or sample_series involved
            in the database change
          - `important`: whether the news is marked as being important;
            defaults to ``True``

        :type process_or_sample_series: `models.Process` or
          `models.SampleSeries`
        :type important: bool
        """
        self.__add_interested_users(process_or_sample_series.samples.all(), important)

    def __add_group_members(self, group):
        u"""Add all members of the given group to the set of users connected
        with the next generated feed entry by `__connect_with_users`.

        :Parameters:
          - `group`: the group whose members should be informed with the next
            feed entry

        :type group: ``django.contrib.auth.models.Group``
        """
        self.interested_users.update(utils.get_profile(user) for user in group.user_set.all())

    def __get_subscribers(self, sample_series):
        u"""
        :Parameters:
          - `sample_series`: the sample series whose subscribers should be
            determined

        :type sample_series: `models.SampleSeries`

        :Return:
          all user who watch a sample in this sample series, and therefore, the
          sample series itself, too

        :rtype: list of `models.UserDetails`
        """
        # This is a hack but I think it's okay.  I save
        # ``self.interested_users``, fill it with the subscribers, and restore
        # the old value for ``self.interested_users`` again.
        interested_users = self.interested_users
        self.__add_watchers(sample_series)
        subscribers = self.interested_users
        self.interested_users = interested_users
        return subscribers

    def report_new_samples(self, samples):
        u"""Generate one feed entry for new samples.  If more than one sample
        is in the given list, they are assumed to have been generated at the
        same time, so they should share the same group and purpose.

        If the sample or samples are not in a group, no feed entry is generated
        (because nobody listens).

        :Parameters:
          - `samples`: the samples that were added

        :type samples: list of `models.Sample`
        """
        group = samples[0].group
        if group:
            common_purpose = samples[0].purpose
            entry = models.FeedNewSamples.objects.create(originator=self.originator, group=group, purpose=common_purpose)
            entry.samples = samples
            entry.auto_adders = group.auto_adders.all()
            self.__add_group_members(group)
            self.__connect_with_users(entry)

    def report_physical_process(self, process, edit_description=None):
        u"""Generate a feed entry for a physical process (deposition, measurement,
        etching etc) which was recently edited or created.

        :Parameters:
          - `process`: the process which was added/edited recently
          - `edit_description`: The dictionary containing data about what was
            edited in the process.  Its keys correspond to the fields of
            `form_utils.EditDescriptionForm`.  ``None`` if the process was
            newly created.

        :type process: `models.Process`
        :type edit_description: dict mapping str to ``object``
        """
        important = edit_description["important"] if edit_description else True
        if edit_description:
            entry = models.FeedEditedPhysicalProcess.objects.create(
                originator=self.originator, process=process,
                description=edit_description["description"], important=important)
        else:
            entry = models.FeedNewPhysicalProcess.objects.create(originator=self.originator, process=process)
        self.__add_watchers(process, important)
        self.__connect_with_users(entry)

    def report_result_process(self, result, edit_description=None):
        u"""Generate a feed entry for a result process which was recently
        edited or created.

        :Parameters:
          - `result`: the result process which was added/edited recently
          - `edit_description`: The dictionary containing data about what was
            edited in the result.  Its keys correspond to the fields of
            `form_utils.EditDescriptionForm`.  ``None`` if the process was
            newly created.

        :type result: `models.Result`
        :type edit_description: dict mapping str to ``object``
        """
        if edit_description:
            entry = models.FeedResult.objects.create(
                originator=self.originator, result=result, is_new=False,
                description=edit_description["description"],
                important=edit_description["important"])
        else:
            entry = models.FeedResult.objects.create(originator=self.originator, result=result, is_new=True)
        self.__add_watchers(result, entry.important)
        for sample_series in result.sample_series.all():
            self.__add_watchers(sample_series)
        self.__connect_with_users(entry)

    def report_copied_my_samples(self, samples, recipient, comments):
        u"""Generate a feed entry for sample that one user has copied to
        another user's “My Samples” list.

        :Parameters:
          - `samples`: the samples that were copied to another user
          - `recipient`: the other user who got the samples
          - `comments`: a message from the sender to the recipient

        :type samples: list of `models.Sample`
        :type recipient: ``django.contrib.auth.models.User``
        :type comments: unicode
        """
        entry = models.FeedCopiedMySamples.objects.create(originator=self.originator, comments=comments)
        entry.samples = samples
        self.interested_users.add(utils.get_profile(recipient))
        self.__connect_with_users(entry)

    def report_new_responsible_person_samples(self, samples, edit_description):
        u"""Generate a feed entry for samples that changed their currently
        responsible person.  This feed entry is only sent to that new
        responsible person.  Note that it is possible that further things were
        changed in the sample(s) at the same time (group, purpose …).  They
        should be mentioned in the description by the formerly responsible
        person.

        :Parameters:
          - `samples`: the samples that got a new responsible person
          - `edit_description`: Dictionary containing data about what was
            edited in the samples (besides the change of the responsible
            person).  Its keys correspond to the fields of
            `form_utils.EditDescriptionForm`.

        :type samples: list of `models.Sample`
        :type edit_description: dict mapping str to ``object``
        """
        entry = models.FeedEditedSamples.objects.create(
            originator=self.originator, description=edit_description["description"],
            important=edit_description["important"], responsible_person_changed=True)
        entry.samples = samples
        self.interested_users.add(utils.get_profile(samples[0].currently_responsible_person))
        self.__connect_with_users(entry)

    def report_changed_sample_group(self, samples, old_group, edit_description):
        u"""Generate a feed entry about a group change for sample(s).  All
        members of the former group (if any) and the new group are informed.
        Note that it is possible that further things were changed in the
        sample(s) at the same time (reponsible person, purpose …).  They should
        be mentioned in the description by the one who changed it.

        :Parameters:
          - `samples`: the samples that went into a new group
          - `old_group`: the old group of the samples; may be ``None`` if they
            weren't in any group before
          - `edit_description`: The dictionary containing data about what was
            edited in the samples (besides the change of the group).  Its keys
            correspond to the fields of `form_utils.EditDescriptionForm`.

        :type samples: list of `models.Sample`
        :type old_group: ``django.contrib.auth.models.Group``
        :type edit_description: dict mapping str to ``object``
        """
        important = edit_description["important"]
        group = samples[0].group
        entry = models.FeedMovedSamples.objects.create(
            originator=self.originator, description=edit_description["description"],
            important=important, group=group, old_group=old_group)
        entry.samples = samples
        entry.auto_adders = group.auto_adders.all()
        if old_group:
            self.__add_group_members(old_group)
        self.__add_group_members(group)
        self.__connect_with_users(entry)

    def report_edited_samples(self, samples, edit_description):
        u"""Generate a feed entry about a general edit of sample(s).  All users
        who are allowed to see the sample and who have the sample on their “My
        Samples” list are informed.

        :Parameters:
          - `samples`: the samples that was edited
          - `edit_description`: The dictionary containing data about what was
            edited in the samples.  Its keys correspond to the fields of
            `form_utils.EditDescriptionForm`.

        :type samples: list of `models.Sample`
        :type edit_description: dict mapping str to ``object``
        """
        important = edit_description["important"]
        entry = models.FeedEditedSamples.objects.create(
            originator=self.originator, description=edit_description["description"], important=important)
        entry.samples = samples
        self.__add_interested_users(samples, important)
        self.__connect_with_users(entry)

    def report_sample_split(self, sample_split, sample_completely_split):
        u"""Generate a feed entry for a sample split.

        :Parameters:
          - `sample_split`: sample split that is to be reported
          - `sample_completely_split`: whether the sample was completely split,
            i.e. no piece of the parent sample is left

        :type sample_split: `models.SampleSplit`
        :type sample_completely_split: bool
        """
        entry = models.FeedSampleSplit.objects.create(originator=self.originator, sample_split=sample_split,
                                                      sample_completely_split=sample_completely_split)
        # I can't use the parent sample for this because if it was completely
        # split, it is already removed from “My Samples”.
        self.__add_interested_users([sample_split.pieces.all()[0]])
        self.__connect_with_users(entry)

    def report_edited_sample_series(self, sample_series, edit_description):
        u"""Generate a feed entry about an edited of sample series.  All users
        who have watches samples in this series are informed, including the
        currently responsible person (in case that it is not the originator).

        :Parameters:
          - `sample_series`: the sample series that was edited
          - `edit_description`: The dictionary containing data about what was
            edited in the sample series.  Its keys correspond to the fields of
            `form_utils.EditDescriptionForm`.

        :type sample_series: list of `models.SampleSeries`
        :type edit_description: dict mapping str to ``object``
        """
        important = edit_description["important"]
        entry = models.FeedEditedSampleSeries.objects.create(
            originator=self.originator, sample_series=sample_series, description=edit_description["description"],
            important=important)
        self.__add_watchers(sample_series, important)
        self.__connect_with_users(entry)

    def report_new_responsible_person_sample_series(self, sample_series, edit_description):
        u"""Generate a feed entry for a sample series that changed their
        currently responsible person.  This feed entry is only sent to that new
        responsible person.  Note that it is possible that further things were
        changed in the sample series at the same time (group, samples …).  They
        should be mentioned in the description by the formerly responsible
        person.

        :Parameters:
          - `sample_series`: the sample series that got a new responsible
            person
          - `edit_description`: Dictionary containing data about what was
            edited in the sample series (besides the change of the responsible
            person).  Its keys correspond to the fields of
            `form_utils.EditDescriptionForm`.

        :type sample_series: list of `models.SampleSeries`
        :type edit_description: dict mapping str to ``object``
        """
        entry = models.FeedEditedSampleSeries.objects.create(
            originator=self.originator, description=edit_description["description"],
            important=edit_description["important"], responsible_person_changed=True, sample_series=sample_series)
        self.interested_users.add(utils.get_profile(sample_series.currently_responsible_person))
        self.__connect_with_users(entry)

    def report_changed_sample_series_group(self, sample_series, old_group, edit_description):
        u"""Generate a feed entry about a group change for a sample series.
        All members of the former group and the new group are informed.  Note
        that it is possible that further things were changed in the sample
        series at the same time (reponsible person, samples …).  They should be
        mentioned in the description by the one who changed it.

        :Parameters:
          - `sample_series`: the sample series that went into a new group
          - `old_group`: the old group of the samples; may be ``None`` if they
            weren't in any group before
          - `edit_description`: The dictionary containing data about what was
            edited in the sample series (besides the change of the group).  Its
            keys correspond to the fields of `form_utils.EditDescriptionForm`.

        :type sample_series: list of `models.SampleSeries`
        :type old_group: ``django.contrib.auth.models.Group``
        :type edit_description: dict mapping str to ``object``
        """
        important = edit_description["important"]
        group = sample_series.group
        entry = models.FeedMovedSampleSeries.objects.create(
            originator=self.originator, description=edit_description["description"],
            important=important, sample_series=sample_series, old_group=old_group, group=sample_series.group)
        entry.subscribers = self.__get_subscribers(sample_series)
        self.__add_group_members(old_group)
        self.__add_group_members(group)
        self.__connect_with_users(entry)

    def report_new_sample_series(self, sample_series):
        u"""Generate one feed entry for a new sample series.

        :Parameters:
          - `sample_series`: the sample series that was added

        :type sample_series: `models.SampleSeries`
        """
        group = sample_series.group
        entry = \
            models.FeedNewSampleSeries.objects.create(originator=self.originator, sample_series=sample_series, group=group)
        entry.subscribers = self.__get_subscribers(sample_series)
        self.__add_group_members(group)
        self.__connect_with_users(entry)

    def report_changed_group_membership(self, users, group, action):
        u"""Generate one feed entry for changed group memberships, i.e. added
        or removed users in a group.

        :Parameters:
          - `users`: the affected users
          - `group`: the group whose memberships have changed
          - `action`: what was done; ``"added"`` for added users, ``"removed"``
            for removed users

        :type users: ``django.contrib.auth.models.User``
        :type group: ``django.contrib.auth.models.Group``
        :type action: str
        """
        entry = models.FeedChangedGroup.objects.create(originator=self.originator, group=group, action=action)
        self.interested_users = set(utils.get_profile(user) for user in users)
        self.__connect_with_users(entry)