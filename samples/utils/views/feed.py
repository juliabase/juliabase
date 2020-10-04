# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Code for generating feed entries.  They are called by views shortly after
the database was changed in one way or another.
"""

from django.contrib.contenttypes.models import ContentType
import jb_common.models
from samples import models, permissions


__all__ = ("Reporter",)


class Reporter:
    """This class contains all feed-generating routines as methods.  Their
    names start with ``report_...``.  The main reason for putting them into a
    class is that this class assures that no user gets two feed entries.
    Therefore, if you want to report a certain database change to the users,
    create an instance of ``Reporter`` and call all methods that are related to
    the database change.  Call the most meaningful method first, and the most
    general last.  For example, when changing the data of a sample, the
    respective view calls the following methods in this order::

        report_new_responsible_person_samples
        report_changed_sample_topic
        report_edited_samples

    Of course, the first two are only called if the respective data change
    really happend.  Thus, the new responsible person is signalled first, then
    all people about a possible topic change, and if this didn't happen, all
    so-far un-signalled users get a general message about changed sample data.

    If you want to signal something to all possibly interested users, no matter
    on which feed entries they already have received, just create a new
    instance of ``Reporter``.

    Mostly, you can call the method directly without binding the instance of
    ``Reporter`` to a name, as in::

        feed_utils.Reporter(request.user).report_result_process(
                result, edit_description=None)

    :ivar interested_users: all users that get informed with the next generated
      feed entry by a call to `__connect_with_users`

    :ivar already_informed_users: All users who have already received a feed
      entry from this instance of ``Reporter``.  They won't get a second
      entry.

    :ivar originator: the user responsible for the databse change reported by
      the feed entry of this instance of ``Reporter``.

    :type interested_users: set of django.contrib.auth.models.User
    :type already_informed_users: set of django.contrib.auth.models.User
    :type originator: django.contrib.auth.models.User
    """

    def __init__(self, originator):
        """Class constructor.

        :param originator: the user who did the database change to be reported;
            almost always, this is the currently logged-in user

        :type originator: django.contrib.auth.models.User
        """
        self.interested_users = set()
        self.already_informed_users = set()
        self.originator = originator

    def __connect_with_users(self, entry, sending_model=None):
        """Take an already generated feed entry and set its recipients to all
        users that are probably interested in this news (and allowed to see
        it).  This method ensures that neither the originator, nor users who
        have already received another feed entry get the current ``entry``.

        If the entry would be connected with no interested users, it is
        deleted.

        :param entry: the feed entry that should be connected with users that
            should receive it
        :param sending_model: the model which is the origin of the news

        :type entry: `samples.models.FeedEntry`
        :type sending_model: class, descendant of ``models.Model``
        """
        self.interested_users -= self.already_informed_users
        if sending_model:
            self.interested_users &= {user_details.user for user_details in
                                      ContentType.objects.get_for_model(sending_model).subscribed_users.all()}
        self.already_informed_users.update(self.interested_users)
        self.interested_users.discard(self.originator)
        if self.interested_users:
            entry.users.set(self.interested_users)
        else:
            entry.delete()
        self.interested_users = set()

    def __add_interested_users(self, samples, important=True):
        """Add users interested in news about the given samples.  These are
        all users that have one of ``samples`` on their “My Samples” list,
        *and* the level of importance is enough.  They are added to the set of
        users connected with the next generated feed entry by `__connect_with_users`.

        :param samples: the samples involved in the database change
        :param important: whether the news is marked as being important;
            defaults to ``True``

        :type samples: list of `samples.models.Sample`
        :type important: bool
        """
        for sample in samples:
            for user in sample.watchers.all():
                if (important or not user.samples_user_details.only_important_news) and \
                        permissions.has_permission_to_fully_view_sample(user, sample):
                    self.interested_users.add(user)

    def __add_watchers(self, process_or_sample_series, important=True):
        """Add users interested in news about the given process or sample
        series.  They are added to the set of users connected with the next
        generated feed entry by `__connect_with_users`.  The odd unification of
        processes and sample series stems from the fact that both share the
        attribute ``samples`` as a many-to-many relationship.  Thus, I use
        duck-typing here.

        :param process_or_sample_series: the process or sample_series involved
            in the database change
        :param important: whether the news is marked as being important;
            defaults to ``True``

        :type process_or_sample_series: `samples.models.Process` or
          `samples.models.SampleSeries`
        :type important: bool
        """
        self.__add_interested_users(process_or_sample_series.samples.all(), important)

    def __add_topic_members(self, topic):
        """Add all members of the given topic to the set of users connected
        with the next generated feed entry by `__connect_with_users`.  However,
        only those members are added who wish to receive also non-important
        news.

        :param topic: the topic whose members should be informed with the next
            feed entry

        :type topic: `jb_common.models.Topic`
        """
        self.interested_users.update(user for user in topic.members.iterator()
                                     if not user.samples_user_details.only_important_news)

    def __get_subscribers(self, sample_series):
        """
        :param sample_series: the sample series whose subscribers should be
            determined

        :type sample_series: `samples.models.SampleSeries`

        :return:
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
        """Generate one feed entry for new samples.  If more than one sample
        is in the given list, they are assumed to have been generated at the
        same time, so they should share the same topic and purpose.

        If the sample or samples are not in a topic, no feed entry is generated
        (because nobody listens).

        :param samples: the samples that were added

        :type samples: list of `samples.models.Sample`
        """
        topic = samples[0].topic
        if topic:
            common_purpose = samples[0].purpose
            entry = models.FeedNewSamples.objects.create(originator=self.originator, topic=topic, purpose=common_purpose)
            entry.samples.set(samples)
            entry.auto_adders.set(user_details.user for user_details in topic.auto_adders.all())
            self.__add_topic_members(topic)
            self.__connect_with_users(entry, jb_common.models.Topic)

    def report_physical_process(self, process, edit_description=None):
        """Generate a feed entry for a physical process (deposition,
        measurement, etching etc) which was recently edited or created.  If the
        process is still unfinished, nothing is done.

        :param process: the process which was added/edited recently
        :param edit_description: The dictionary containing data about what was
            edited in the process.  Its keys correspond to the fields of
            `~samples.utils.views.EditDescriptionForm`.  ``None`` if the
            process was newly created.

        :type process: `samples.models.Process`
        :type edit_description: dict mapping str to ``object``
        """
        if process.finished:
            important = edit_description["important"] if edit_description else True
            if edit_description:
                entry = models.FeedEditedPhysicalProcess.objects.create(
                    originator=self.originator, process=process,
                    description=edit_description["description"], important=important)
            else:
                entry = models.FeedNewPhysicalProcess.objects.create(originator=self.originator, process=process)
            self.__add_watchers(process, important)
            self.__connect_with_users(entry, process.__class__)


    def report_deleted_process(self, process):
        """Generate a feed entry about a deletion of a process.

        :param process: the process that was deleted

        :type process: `samples.models.Process`
        """
        entry = models.FeedDeletedProcess.objects.create(originator=self.originator, process_name=str(process))
        self.__add_watchers(process)
        if isinstance(process, models.Result):
            for sample_series in process.sample_series.all():
                self.__add_watchers(sample_series)
        self.__connect_with_users(entry, process.__class__)


    def report_result_process(self, result, edit_description=None):
        """Generate a feed entry for a result process which was recently
        edited or created.

        :param result: the result process which was added/edited recently
        :param edit_description: The dictionary containing data about what was
            edited in the result.  Its keys correspond to the fields of
            `~samples.utils.views.EditDescriptionForm`.  ``None`` if the
            process was newly created.

        :type result: `samples.models.Result`
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
        """Generate a feed entry for sample that one user has copied to
        another user's “My Samples” list.

        :param samples: the samples that were copied to another user
        :param recipient: the other user who got the samples
        :param comments: a message from the sender to the recipient

        :type samples: list of `samples.models.Sample`
        :type recipient: django.contrib.auth.models.User
        :type comments: str
        """
        entry = models.FeedCopiedMySamples.objects.create(originator=self.originator, comments=comments)
        entry.samples.set(samples)
        self.interested_users.add(recipient)
        self.__connect_with_users(entry, models.Sample)

    def report_new_responsible_person_samples(self, samples, edit_description):
        """Generate a feed entry for samples that changed their currently
        responsible person.  This feed entry is only sent to that new
        responsible person.  Note that it is possible that further things were
        changed in the sample(s) at the same time (topic, purpose …).  They
        should be mentioned in the description by the formerly responsible
        person.

        :param samples: the samples that got a new responsible person
        :param edit_description: Dictionary containing data about what was
            edited in the samples (besides the change of the responsible
            person).  Its keys correspond to the fields of
            `~samples.utils.views.EditDescriptionForm`.

        :type samples: list of `samples.models.Sample`
        :type edit_description: dict mapping str to ``object``
        """
        entry = models.FeedEditedSamples.objects.create(
            originator=self.originator, description=edit_description["description"],
            important=edit_description["important"], responsible_person_changed=True)
        entry.samples.set(samples)
        self.interested_users.add(samples[0].currently_responsible_person)
        self.__connect_with_users(entry, models.Sample)

    def report_changed_sample_topic(self, samples, old_topic, edit_description):
        """Generate a feed entry about a topic change for sample(s).  All
        members of the former topic (if any) and the new topic are informed.
        Note that it is possible that further things were changed in the
        sample(s) at the same time (reponsible person, purpose …).  They should
        be mentioned in the description by the one who changed it.

        :param samples: the samples that went into a new topic
        :param old_topic: the old topic of the samples; may be ``None`` if
            they weren't in any topic before
        :param edit_description: The dictionary containing data about what was
            edited in the samples (besides the change of the topic).  Its keys
            correspond to the fields of
            `~samples.utils.views.EditDescriptionForm`.

        :type samples: list of `samples.models.Sample`
        :type old_topic: `jb_common.models.Topic`
        :type edit_description: dict mapping str to ``object``
        """
        important = edit_description["important"]
        topic = samples[0].topic
        entry = models.FeedMovedSamples.objects.create(
            originator=self.originator, description=edit_description["description"],
            important=important, topic=topic, old_topic=old_topic)
        entry.samples.set(samples)
        entry.auto_adders.set(user_details.user for user_details in topic.auto_adders.all())
        if old_topic:
            self.__add_topic_members(old_topic)
        self.__add_topic_members(topic)
        self.__connect_with_users(entry, jb_common.models.Topic)

    def report_edited_samples(self, samples, edit_description):
        """Generate a feed entry about a general edit of sample(s).  All users
        who are allowed to see the sample and who have the sample on their “My
        Samples” list are informed.

        :param samples: the samples that were edited
        :param edit_description: The dictionary containing data about what was
            edited in the samples.  Its keys correspond to the fields of
            `~samples.utils.views.EditDescriptionForm`.

        :type samples: list of `samples.models.Sample`
        :type edit_description: dict mapping str to ``object``
        """
        important = edit_description["important"]
        entry = models.FeedEditedSamples.objects.create(
            originator=self.originator, description=edit_description["description"], important=important)
        entry.samples.set(samples)
        self.__add_interested_users(samples, important)
        self.__connect_with_users(entry, models.Sample)

    def report_deleted_sample(self, sample):
        """Generate a feed entry about a deletion of a sample.  All users who are
        allowed to see the sample and who have the sample on their “My Samples”
        list are informed.

        :param sample: the sample that was deleted

        :type sample: `samples.models.Sample`
        """
        entry = models.FeedDeletedSample.objects.create(originator=self.originator, sample_name=sample.name)
        self.__add_interested_users([sample])
        self.__connect_with_users(entry, models.Sample)

    def report_sample_split(self, sample_split, sample_completely_split):
        """Generate a feed entry for a sample split.

        :param sample_split: sample split that is to be reported
        :param sample_completely_split: whether the sample was completely split,
            i.e. no piece of the parent sample is left

        :type sample_split: `samples.models.SampleSplit`
        :type sample_completely_split: bool
        """
        entry = models.FeedSampleSplit.objects.create(originator=self.originator, sample_split=sample_split,
                                                      sample_completely_split=sample_completely_split)
        # I can't use the parent sample for this because if it was completely
        # split, it is already removed from “My Samples”.
        self.__add_interested_users([sample_split.pieces.all()[0]])
        self.__connect_with_users(entry, models.Sample)

    def report_edited_sample_series(self, sample_series, edit_description):
        """Generate a feed entry about an edited of sample series.  All users
        who have watches samples in this series are informed, including the
        currently responsible person (in case that it is not the originator).

        :param sample_series: the sample series that was edited
        :param edit_description: The dictionary containing data about what was
            edited in the sample series.  Its keys correspond to the fields of
            `~samples.utils.views.EditDescriptionForm`.

        :type sample_series: list of `samples.models.SampleSeries`
        :type edit_description: dict mapping str to ``object``
        """
        important = edit_description["important"]
        entry = models.FeedEditedSampleSeries.objects.create(
            originator=self.originator, sample_series=sample_series, description=edit_description["description"],
            important=important)
        self.__add_watchers(sample_series, important)
        self.__connect_with_users(entry, models.SampleSeries)

    def report_new_responsible_person_sample_series(self, sample_series, edit_description):
        """Generate a feed entry for a sample series that changed their
        currently responsible person.  This feed entry is only sent to that new
        responsible person.  Note that it is possible that further things were
        changed in the sample series at the same time (topic, samples …).
        They should be mentioned in the description by the formerly responsible
        person.

        :param sample_series: the sample series that got a new responsible
            person
        :param edit_description: Dictionary containing data about what was
            edited in the sample series (besides the change of the responsible
            person).  Its keys correspond to the fields of
            `~samples.utils.views.EditDescriptionForm`.

        :type sample_series: list of `samples.models.SampleSeries`
        :type edit_description: dict mapping str to ``object``
        """
        entry = models.FeedEditedSampleSeries.objects.create(
            originator=self.originator, description=edit_description["description"],
            important=edit_description["important"], responsible_person_changed=True, sample_series=sample_series)
        self.interested_users.add(sample_series.currently_responsible_person)
        self.__connect_with_users(entry, models.SampleSeries)

    def report_changed_sample_series_topic(self, sample_series, old_topic, edit_description):
        """Generate a feed entry about a topic change for a sample series.
        All members of the former topic and the new topic are informed.
        Note that it is possible that further things were changed in the sample
        series at the same time (reponsible person, samples …).  They should be
        mentioned in the description by the one who changed it.

        :param sample_series: the sample series that went into a new topic
        :param old_topic: the old topic of the samples; may be ``None`` if
            they weren't in any topic before
        :param edit_description: The dictionary containing data about what was
            edited in the sample series (besides the change of the topic).
            Its keys correspond to the fields of
            `~samples.utils.views.EditDescriptionForm`.

        :type sample_series: list of `samples.models.SampleSeries`
        :type old_topic: `jb_common.models.Topic`
        :type edit_description: dict mapping str to ``object``
        """
        important = edit_description["important"]
        topic = sample_series.topic
        entry = models.FeedMovedSampleSeries.objects.create(
            originator=self.originator, description=edit_description["description"],
            important=important, sample_series=sample_series, old_topic=old_topic, topic=sample_series.topic)
        entry.subscribers.set(self.__get_subscribers(sample_series))
        self.__add_topic_members(old_topic)
        self.__add_topic_members(topic)
        self.__connect_with_users(entry, models.SampleSeries)

    def report_new_sample_series(self, sample_series):
        """Generate one feed entry for a new sample series.

        :param sample_series: the sample series that was added

        :type sample_series: `samples.models.SampleSeries`
        """
        topic = sample_series.topic
        entry = models.FeedNewSampleSeries.objects.create(
            originator=self.originator, sample_series=sample_series, topic=topic)
        entry.subscribers.set(self.__get_subscribers(sample_series))
        self.__add_topic_members(topic)
        self.__connect_with_users(entry, models.SampleSeries)

    def report_changed_topic_membership(self, users, topic, action):
        """Generate one feed entry for changed topic memberships, i.e. added
        or removed users in a topic.

        :param users: the affected users
        :param topic: the topic whose memberships have changed
        :param action: what was done; ``"added"`` for added users, ``"removed"``
            for removed users

        :type users: iterable of django.contrib.auth.models.User
        :type topic: `jb_common.models.Topic`
        :type action: str
        """
        entry = models.FeedChangedTopic.objects.create(originator=self.originator, topic=topic, action=action)
        self.interested_users = set(users)
        self.__connect_with_users(entry, jb_common.models.Topic)

    def report_status_message(self, process_class, status_message):
        """Generate one feed entry for new status messages for physical
        processes.

        :param process_class: the content type of the physical process whose
            status has changed
        :param status_message: the status message for the physical process

        :type process_class: django.contrib.contenttypes.models.ContentType
        :type status_message: `samples.models.StatusMessage`
        """
        entry = models.FeedStatusMessage.objects.create(originator=self.originator, process_class=process_class,
                                                        status=status_message)
        self.interested_users = {user_details.user for user_details in process_class.subscribed_users.all()}
        self.__connect_with_users(entry)

    def report_withdrawn_status_message(self, process_class, status_message):
        """Generate one feed entry for a withdrawn status message for physical
        processes.

        :param process_class: the content type of the physical process one of
            whose statuses was withdrawn
        :param status_message: the status message for the physical process

        :type process_class: django.contrib.contenttypes.models.ContentType
        :type status_message: `samples.models.StatusMessage`
        """
        entry = models.FeedWithdrawnStatusMessage.objects.create(
            originator=self.originator, process_class=process_class, status=status_message)
        self.interested_users = {user_details.user for user_details in process_class.subscribed_users.all()}
        self.__connect_with_users(entry)

    def report_task(self, task, edit_description=None):
        """Generate one feed entry for a new task or an edited task.

        :param task: the task that was created or edited
        :param edit_description: The dictionary containing data about what was
            edited in the task.  Its keys correspond to the fields of
            `~samples.utils.views.EditDescriptionForm`. ``None`` if the task
            was newly created.

        :type task: `models.Task`
        :type edit_description: dict mapping str to ``object`` or ``None``
        """
        process_class = task.process_class
        self.interested_users = set(permissions.get_all_adders(task.process_class.model_class()))
        if edit_description is None:
            entry = models.FeedNewTask.objects.create(originator=self.originator, task=task)
        else:
            self.interested_users.add(task.customer)
            important = edit_description["important"]
            entry = models.FeedEditedTask.objects.create(originator=self.originator, task=task,
                                                         description=edit_description["description"], important=important)
        self.__connect_with_users(entry)

    def report_removed_task(self, task):
        """Generate one feed for a removed task.  It is called immediately
        before the task is actually deleted.

        :param task: the to-be-deleted task

        :type task: `models.Task`
        """
        self.interested_users = set(permissions.get_all_adders(task.process_class.model_class()))
        self.interested_users.add(task.customer)
        entry = models.FeedRemovedTask.objects.create(old_id=task.id, originator=self.originator,
                                                      process_class=task.process_class)
        entry.samples.set(task.samples.all())
        self.__connect_with_users(entry)
