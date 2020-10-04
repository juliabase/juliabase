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


"""Models for feed entries.

It is important to note that in some case, you may wonder why certain fields
are included into the model.  For example, if I report a new sample in the
feed, it seems to be superfluous to include the topic it has been added since
it is already stored in the new sample itself.  However, the topic may change
afterwards which would render old feed entries incorrect.  Therefore, the feed
entries are self-contained.
"""

import hashlib
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
import django.contrib.auth.models
import django.urls
from samples.models import Sample, Process, Result, SampleSplit, SampleSeries, StatusMessage, Task
from jb_common.models import Topic, PolymorphicModel
from jb_common.utils.base import get_really_full_name


class FeedEntry(PolymorphicModel):
    """Abstract base model for newsfeed entries.  This is also not really abstract
    as it has a table in the database, however, it is never instantiated
    itself.  Instead, see
    :py:meth:`samples.models.PolymorphicModel.actual_instance` which is
    inherited by this class.
    """
    originator = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("originator"))
    users = models.ManyToManyField(django.contrib.auth.models.User, verbose_name=_("users"), related_name="feed_entries",
                                   blank=True)
    timestamp = models.DateTimeField(_("timestamp"), auto_now_add=True)
    important = models.BooleanField(_("is important"), default=True)
    sha1_hash = models.CharField(_("SHA1 hex digest"), max_length=40, blank=True, editable=False)
    """You'll never calculate the SHA-1 hash yourself.  It is done in
    `save`.
    """

    class Meta:
        verbose_name = _("feed entry")
        verbose_name_plural = _("feed entries")
        ordering = ["-timestamp"]

    def __str__(self):
        return _("feed entry #{number}").format(number=self.id)

    def save(self, *args, **kwargs):
        """Before saving the feed entry, I calculate an unsalted SHA-1 from
        the timestamp, the username of the originator, the object's ID, and the
        link (if given).  It is used for the GUID of this entry.

        Note that I have to call the parent's ``save()`` method twice and I
        pass the parameter only to the first call.

        :return:
          ``None``
        """
        super().save(*args, **kwargs)
        entry_hash = hashlib.sha1()
        entry_hash.update(repr(self.timestamp).encode())
        entry_hash.update(repr(self.originator).encode())
        entry_hash.update(repr(self.id).encode())
        self.sha1_hash = entry_hash.hexdigest()
        super().save()

    def get_metadata(self):
        """Return the title of this feed entry, as a plain string (no HTML),
        and the categorisation (see the Atom feed specification, :RFC:`4646`,
        section 4.2.2).  It also returns a link if approriate (without domain
        but with the leading ``/``).

        :return:
          a dictionary with the keys ``"title"``, ``"category term"``,
          ``"link"``, and ``"category label"``.  ``"link"`` is optional.

        :rtype: dict mapping str to str
        """
        raise NotImplementedError

    def get_additional_template_context(self, user):
        """Return a dictionary with additional context that should be available in the
        template.  It is similar to
        :py:meth:`institute.models.FiveChamberDeposition.get_additional_template_context`.
        However, in contrast to this other method, the feed version is
        implemented in the abstract base class, so it is defined in all feed
        models.  The rationale for this is that it is used in almost every feed
        model anyway.  If not overridden, this method returns an empty
        dictionary.

        :param user: the user fetching the feed

        :type user: django.contrib.auth.models.User

        :return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        return {}


class FeedNewSamples(FeedEntry):
    """Model for feed entries about new samples having been added to the
    database.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_("samples"))
    topic = models.ForeignKey(Topic, models.CASCADE, verbose_name=_("topic"), related_name="new_samples_news")
    purpose = models.CharField(_("purpose"), max_length=80, blank=True)
    auto_adders = models.ManyToManyField(django.contrib.auth.models.User, verbose_name=_("auto adders"), blank=True)

    class Meta(PolymorphicModel.Meta):
        # FixMe: The labels are gramatically unfortunate.  “feed entry for new
        # samples” is better.
        verbose_name = _("new samples feed entry")
        verbose_name_plural = _("new samples feed entries")

    def get_metadata(self):
        result = {}
        result["title"] = ungettext("New sample in “{topic}”", "New samples in “{topic}”", self.samples.count()).format(
            topic=self.topic)
        result["category term"] = "new samples"
        result["category label"] = "new samples"
        return result

    def get_additional_template_context(self, user):
        return {"auto_added": self.auto_adders.filter(pk=user.pk).exists()}


class FeedMovedSamples(FeedEntry):
    """Model for feed entries about samples moved to a new topic.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_("samples"))
    topic = models.ForeignKey(Topic, models.CASCADE, verbose_name=_("topic"), related_name="moved_samples_news")
    old_topic = models.ForeignKey(Topic, models.CASCADE, verbose_name=_("old topic"), null=True, blank=True)
    auto_adders = models.ManyToManyField(django.contrib.auth.models.User, verbose_name=_("auto adders"), blank=True)
    description = models.TextField(_("description"))

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("moved samples feed entry")
        verbose_name_plural = _("moved samples feed entries")

    def get_metadata(self):
        result = {}
        result["title"] = ungettext("New sample moved to “{topic}”", "New samples moved to “{topic}”",
                                    self.samples.count()).format(topic=self.topic)
        result["category term"] = "moved samples"
        result["category label"] = "moved samples"
        return result

    def get_additional_template_context(self, user):
        return {"auto_added": self.auto_adders.filter(pk=user.pk).exists()}


class FeedNewPhysicalProcess(FeedEntry):
    """Model for feed entries about new physical processes.
    """
    process = models.OneToOneField(Process, models.CASCADE, verbose_name=_("process"))

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("new physical process feed entry")
        verbose_name_plural = _("new physical process feed entries")

    def get_metadata(self):
        result = {}
        process = self.process.actual_instance
        result["title"] = _("New {process}").format(process=process)
        result["category term"] = "new physical process"
        result["category label"] = "new physical process"
        result["link"] = process.get_absolute_url()
        return result

    def get_additional_template_context(self, user):
        return {"process": self.process.actual_instance}


class FeedEditedPhysicalProcess(FeedEntry):
    """Model for feed entries about edited physical processes.
    """
    process = models.ForeignKey(Process, models.CASCADE, verbose_name=_("process"))
    description = models.TextField(_("description"))

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("edited physical process feed entry")
        verbose_name_plural = _("edited physical process feed entries")

    def get_metadata(self):
        metadata = {}
        process = self.process.actual_instance
        metadata["title"] = _("Edited {process}").format(process=process)
        metadata["category term"] = "new physical process"
        metadata["category label"] = "new physical process"
        metadata["link"] = process.get_absolute_url()
        return metadata

    def get_additional_template_context(self, user):
        return {"process": self.process.actual_instance}


class FeedDeletedProcess(FeedEntry):
    """Model for feed entries for a deleted process, including result processes.
    """
    process_name = models.TextField(_("process name"))

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("deleted process feed entry")
        verbose_name_plural = _("deleted process feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("Process {name} was deleted").format(name=self.process_name)
        metadata["category term"] = "deleted process"
        metadata["category label"] = "deleted process"
        return metadata


class FeedResult(FeedEntry):
    """Model for feed entries about new or edited result processes.  Note that
    this model doesn't care whether the result is connected with samples or
    sample series or both.  This is distinguished in the HTML template.
    """
        # Translators: experimental result
    result = models.ForeignKey(Result, models.CASCADE, verbose_name=_("result"))
    description = models.TextField(_("description"), blank=True)
    is_new = models.BooleanField(_("result is new"), default=False)

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("result feed entry")
        verbose_name_plural = _("result feed entries")

    def get_metadata(self):
        metadata = {}
        if self.is_new:
            metadata["title"] = _("New: {result_title}").format(result_title=self.result.title)
            metadata["category term"] = "new result"
            metadata["category label"] = "new result"
        else:
            metadata["title"] = _("Edited: {result_title}").format(result_title=self.result.title)
            metadata["category term"] = "edited result"
            metadata["category label"] = "edited result"
        metadata["link"] = self.result.get_absolute_url()
        return metadata

    def get_additional_template_context(self, user):
        if self.result.image_type != "none":
            image_locations = self.result.get_image_locations()
            return {"thumbnail_url": image_locations["thumbnail_url"], "image_url": image_locations["image_url"]}
        else:
            return {"thumbnail_url": None, "image_url": None}


class FeedCopiedMySamples(FeedEntry):
    """Model for feed entries about samples copied from one user to the “My
    Samples” list of another user.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_("samples"))
    comments = models.TextField(_("comments"))

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("copied My Samples feed entry")
        verbose_name_plural = _("copied My Samples feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("{name} copied samples to you").format(name=get_really_full_name(self.originator))
        metadata["category term"] = "copied samples"
        metadata["category label"] = "copied My Samples"
        return metadata


class FeedEditedSamples(FeedEntry):
    """Model for feed entries for edited samples.  This includes changed currently
    responsible persons.  The respective view generates three entries for that,
    however, see :py:func:`samples.views.sample.edit`.

    FixMe: This should also include sample deaths.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_("samples"))
    description = models.TextField(_("description"))
    responsible_person_changed = models.BooleanField(_("has responsible person changed"), default=False)

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("edited samples feed entry")
        verbose_name_plural = _("edited samples feed entries")

    def get_metadata(self):
        metadata = {}
        if self.samples.count() == 1:
            metadata["title"] = _("Sample {sample} was edited").format(sample=self.samples.get())
        else:
            metadata["title"] = _("Samples were edited")
        metadata["category term"] = "edited samples"
        metadata["category label"] = "edited samples"
        return metadata


class FeedDeletedSample(FeedEntry):
    """Model for feed entries for a deleted sample.  Note that in contrast to
    edited samples, this is only one per feed entry.
    """
    sample_name = models.CharField(_("sample name"), max_length=30)

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("deleted sample feed entry")
        verbose_name_plural = _("deleted sample feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("Sample {name} was deleted").format(name=self.sample_name)
        metadata["category term"] = "deleted sample"
        metadata["category label"] = "deleted sample"
        return metadata


class FeedSampleSplit(FeedEntry):
    """Model for feed entries for sample splits.
    """
    sample_split = models.ForeignKey(SampleSplit, models.CASCADE, verbose_name=_("sample split"))
    sample_completely_split = models.BooleanField(_("sample was completely split"), default=False)

    class Meta(PolymorphicModel.Meta):
            # Translators: Feed entry for a split of a sample
        verbose_name = _("sample split feed entry")
            # Translators: Feed entries for splits of samples
        verbose_name_plural = _("sample split feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("Sample “{parent_sample}” was split").format(parent_sample=self.sample_split.parent)
        metadata["category term"] = "split sample"
        metadata["category label"] = "split sample"
        return metadata


class FeedEditedSampleSeries(FeedEntry):
    """Model for feed entries for edited sample series.  This includes changed
    currently responsible persons.  The respective view generates two entries
    for that, however, see :py:func:`samples.views.sample_series.edit`.
    """
    sample_series = models.ForeignKey(SampleSeries, models.CASCADE, verbose_name=_("sample series"))
    description = models.TextField(_("description"))
    responsible_person_changed = models.BooleanField(_("has responsible person changed"), default=False)

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("edited sample series feed entry")
        verbose_name_plural = _("edited sample series feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("Sample series {name} was edited").format(name=self.sample_series)
        metadata["category term"] = "edited sample series"
        metadata["category label"] = "edited sample series"
        metadata["link"] = self.sample_series.get_absolute_url()
        return metadata


class FeedNewSampleSeries(FeedEntry):
    """Model for feed entries for new sample series.
    """
    sample_series = models.ForeignKey(SampleSeries, models.CASCADE, verbose_name=_("sample series"))
    topic = models.ForeignKey(Topic, models.CASCADE, verbose_name=_("topic"))
    subscribers = models.ManyToManyField(django.contrib.auth.models.User, verbose_name=_("subscribers"), blank=True)

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("new sample series feed entry")
        verbose_name_plural = _("new sample series feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("New sample series “{sample_series}” in topic “{topic}”").format(
            sample_series=self.sample_series, topic=self.topic)
        metadata["category term"] = "new sample series"
        metadata["category label"] = "new sample series"
        metadata["link"] = self.sample_series.get_absolute_url()
        return metadata

    def get_additional_template_context(self, user):
        return {"subscribed": self.subscribers.filter(pk=user.pk).exists()}


class FeedMovedSampleSeries(FeedEntry):
    """Model for feed entries for sample series moved to a new topic.
    """
    sample_series = models.ForeignKey(SampleSeries, models.CASCADE, verbose_name=_("sample series"))
    topic = models.ForeignKey(Topic, models.CASCADE, verbose_name=_("topic"))
    old_topic = models.ForeignKey(Topic, models.CASCADE, verbose_name=_("old topic"), null=True, blank=True,
                                  related_name="news_ex_sample_series")
    description = models.TextField(_("description"))
    subscribers = models.ManyToManyField(django.contrib.auth.models.User, verbose_name=_("subscribers"), blank=True)

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("moved sample series feed entry")
        verbose_name_plural = _("moved sample series feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("Sample series {sample_series} was moved to topic “{topic}”").format(
            sample_series=self.sample_series, topic=self.topic)
        metadata["category term"] = "moved sample series"
        metadata["category label"] = "moved sample series"
        metadata["link"] = self.sample_series.get_absolute_url()
        return metadata

    def get_additional_template_context(self, user):
        return {"subscribed": self.subscribers.filter(pk=user.pk).exists()}


class FeedChangedTopic(FeedEntry):
    """Model for feed entries for sample series moved to a new topic.
    """

    class Action(models.TextChoices):
        ADDED = "added", _("added")
        REMOVED = "removed", _("removed")

    topic = models.ForeignKey(Topic, models.CASCADE, verbose_name=_("topic"))
        # Translators: Action is either addition or removal
    action = models.CharField(_("action"), max_length=7, choices=Action.choices)

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("changed topic feed entry")
        verbose_name_plural = _("changed topic feed entries")

    def get_metadata(self):
        metadata = {}
        if self.action == "added":
            metadata["title"] = _("Now in topic “{name}”").format(name=self.topic)
        else:
            metadata["title"] = _("Not anymore in topic “{name}”").format(name=self.topic)
        metadata["category term"] = "changed topic membership"
        metadata["category label"] = "changed topic membership"
        return metadata


class FeedStatusMessage(FeedEntry):
    """Model for feed entries for new status messages from physical processes.
    """
    process_class = models.ForeignKey(ContentType, models.CASCADE, verbose_name=_("process class"))
    status = models.ForeignKey(StatusMessage, models.CASCADE, verbose_name=_("status message"), related_name="feed_entries")

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("status message feed entry")
        verbose_name_plural = _("status message feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("New status message for {process_class}").format(
            process_class=self.process_class.model_class()._meta.verbose_name)
        metadata["category term"] = metadata["category label"] = "new status message"
        metadata["link"] = django.urls.reverse("samples:show_status")
        return metadata


class FeedWithdrawnStatusMessage(FeedEntry):
    """Model for feed entries for withdrawn status messages from physical
    processes.
    """
    process_class = models.ForeignKey(ContentType, models.CASCADE, verbose_name=_("process class"))
    status = models.ForeignKey(StatusMessage, models.CASCADE, verbose_name=_("status message"),
                               related_name="feed_entries_for_withdrawal")

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("withdrawn status message feed entry")
        verbose_name_plural = _("withdrawn status message feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("Withdrawn status message for {process_class}").format(
            process_class=self.process_class.model_class()._meta.verbose_name)
        metadata["category term"] = metadata["category label"] = "withdrawn status message"
        metadata["link"] = django.urls.reverse("samples:show_status")
        return metadata


class FeedNewTask(FeedEntry):
    """Model for feed entries for new tasks for physical processes.
    """
    task = models.ForeignKey(Task, models.CASCADE, verbose_name=_("task"), related_name="feed_entries_for_new_tasks")

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("new task feed entry")
        verbose_name_plural = _("new task feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("New task for {process_class}").format(
            process_class=self.task.process_class.model_class()._meta.verbose_name)
        metadata["category term"] = metadata["category label"] = "new task"
        metadata["link"] = self.task.get_absolute_url()
        return metadata


class FeedEditedTask(FeedEntry):
    """Model for feed entries for new tasks for physical processes.
    """
    task = models.ForeignKey(Task, models.CASCADE, verbose_name=_("task"), related_name="feed_entries_for_edited_tasks")
    description = models.TextField(_("description"))

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("edited task feed entry")
        verbose_name_plural = _("edited task feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("Edited task for {process_class}").format(
            process_class=self.task.process_class.model_class()._meta.verbose_name)
        metadata["category term"] = metadata["category label"] = "edited task"
        metadata["link"] = self.task.get_absolute_url()
        return metadata


class FeedRemovedTask(FeedEntry):
    """Model for feed entries for removing tasks.
    """
    old_id = models.PositiveIntegerField(_("number"), unique=True)
    process_class = models.ForeignKey(ContentType, models.CASCADE, verbose_name=_("process class"))
    samples = models.ManyToManyField(Sample, verbose_name=_("samples"))

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("removed task feed entry")
        verbose_name_plural = _("removed task feed entries")

    def get_metadata(self):
        metadata = {}
        metadata["title"] = _("Removed a task for {process_class}").format(
            process_class=self.process_class.model_class()._meta.verbose_name)
        metadata["category term"] = metadata["category label"] = "removed task"
        metadata["link"] = django.urls.reverse("samples:show_task_lists")
        return metadata


_ = ugettext
