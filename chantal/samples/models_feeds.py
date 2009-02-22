#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Models for feed entries.

It is important to note that in some case, you may wonder why certain fields
are included into the model.  For example, if I report a new sample in the
feed, it seems to be superfluous to include the group it has been added since
it is already stored in the new sample itself.  However, the group may change
afterwards which would render old feed entries incorrect.  Therefor, the feed
entries are self-contained.
"""

from __future__ import absolute_import

import hashlib
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.contrib import admin
from django.db import models
import django.core.urlresolvers
from samples.models_common import Sample, UserDetails, Process, Result, SampleSplit, SampleSeries


class FeedEntry(models.Model):
    u"""Abstract base model for newsfeed entries.  This is also not really
    abstract as it has a table in the database, however, it is never
    instantiated itself.  Instead, see `find_actual_instance` which is also
    injected into this class.
    """
    originator = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"originator"))
    timestamp = models.DateTimeField(_(u"timestamp"), auto_now_add=True)
    important = models.BooleanField(_(u"is important"), default=True, null=True, blank=True)
    sha1_hash = models.CharField(_(u"SHA1 hex digest"), max_length=40, blank=True, editable=False)
    u"""You'll never calculate the SHA-1 hash yourself.  It is done in
    `save`."""

    class Meta:
        verbose_name = _(u"feed entry")
        verbose_name_plural = _(u"feed entries")
        ordering = ["-timestamp"]

    def __unicode__(self):
        _ = ugettext
        return _(u"feed entry #%d") % self.pk

    def save(self, *args, **kwargs):
        u"""Before saving the feed entry, I calculate an unsalted SHA-1 from
        the timestamp, the username of the originator, the object's ID, and the
        link (if given).  It is used for the GUID of this entry.

        Note that I have to call the parent's ``save()`` method twice and I
        pass the parameter only to the first call.

        :Return:
          ``None``
        """
        super(FeedEntry, self).save(*args, **kwargs)
        entry_hash = hashlib.sha1()
        entry_hash.update(repr(self.timestamp))
        entry_hash.update(repr(self.originator))
        entry_hash.update(repr(self.pk))
        self.sha1_hash = entry_hash.hexdigest()
        super(FeedEntry, self).save()

    def get_metadata(self):
        u"""Return the title of this feed entry, as a plain string (no HTML),
        and the categorisation (see the Atom feed specification, :RFC:`4646`,
        section 4.2.2).  It also returns a link if approriate (without domain
        but with the leading ``/``).

        :Return:
          a dictionary with the keys ``"title"``, ``"category term"``,
          ``"link"``, and ``"category label"``.  ``"link"`` is optional.

        :rtype: dict mapping str to unicode
        """
        raise NotImplementedError

    def get_additional_template_context(self, user_details):
        u"""Return a dictionary with additional context that should be
        available in the template.  It is similar to
        `models_depositions.SixChamberDeposition.get_additional_template_context`.
        However, in contrast to this other method, the feed version is
        implemented in the abstract base class, so it is defined in all feed
        models.  The rationale for this is that it is used in almost every feed
        model anyway.  If not overridden, this method returns an empty
        dictionary.

        :Parameters:
          - `user_details`: the details of the user fetching the feed

        :type user_details: `UserDetails`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        return {}


class FeedNewSamples(FeedEntry):
    u"""Model for feed entries about new samples having been added to the
    database.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"), blank=True)
    group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"group"), related_name="new_samples_news")
    purpose = models.CharField(_(u"purpose"), max_length=80, blank=True)
    auto_adders = models.ManyToManyField(UserDetails, verbose_name=_(u"auto adders"), blank=True)

    class Meta:
        verbose_name = _(u"new samples feed entry")
        verbose_name_plural = _(u"new samples feed entries")

    def get_metadata(self):
        _ = ugettext
        result = {}
        result["title"] = ungettext(u"New sample in “%s”", u"New samples in “%s”", self.samples.count()) % self.group
        result["category term"] = "new samples"
        result["category label"] = "new samples"
        return result

    def get_additional_template_context(self, user_details):
        return {"auto_added": self.auto_adders.filter(pk=user_details.pk).count() != 0}

admin.site.register(FeedNewSamples)


class FeedMovedSamples(FeedEntry):
    u"""Model for feed entries about samples moved to a new group.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"), blank=True)
    group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"group"), related_name="moved_samples_news")
    old_group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"old group"), null=True, blank=True)
    auto_adders = models.ManyToManyField(UserDetails, verbose_name=_(u"auto adders"), blank=True)
    description = models.TextField(_(u"description"))

    class Meta:
        verbose_name = _(u"moved samples feed entry")
        verbose_name_plural = _(u"moved samples feed entries")

    def get_metadata(self):
        _ = ugettext
        result = {}
        result["title"] = ungettext(u"New sample moved to “%s”", u"New samples moved to “%s”",
                                    self.samples.count()) % self.group
        result["category term"] = "moved samples"
        result["category label"] = "moved samples"
        return result

    def get_additional_template_context(self, user_details):
        return {"auto_added": self.auto_adders.filter(pk=user_details.pk).count() != 0}

admin.site.register(FeedMovedSamples)


class FeedNewPhysicalProcess(FeedEntry):
    u"""Model for feed entries about new physical processes.
    """
    process = models.OneToOneField(Process, verbose_name=_(u"process"))

    class Meta:
        verbose_name = _(u"new physical process feed entry")
        verbose_name_plural = _(u"new physical process feed entries")

    def get_metadata(self):
        _ = ugettext
        result = {}
        process = self.process.find_actual_instance()
        result["title"] = _(u"New %s") % process
        result["category term"] = "new physical process"
        result["category label"] = "new physical process"
        result["link"] = process.get_absolute_url()
        return result

    def get_additional_template_context(self, user_details):
        return {"process": self.process.find_actual_instance()}

admin.site.register(FeedNewPhysicalProcess)


class FeedEditedPhysicalProcess(FeedEntry):
    u"""Model for feed entries about edited physical processes.
    """
    process = models.ForeignKey(Process, verbose_name=_(u"process"))
    description = models.TextField(_(u"description"))

    class Meta:
        verbose_name = _(u"edited physical process feed entry")
        verbose_name_plural = _(u"edited physical process feed entries")

    def get_metadata(self):
        _ = ugettext
        metadata = {}
        process = self.process.find_actual_instance()
        metadata["title"] = _(u"Edited %s") % process
        metadata["category term"] = "new physical process"
        metadata["category label"] = "new physical process"
        metadata["link"] = process.get_absolute_url()
        return metadata

    def get_additional_template_context(self, user_details):
        return {"process": self.process.find_actual_instance()}

admin.site.register(FeedEditedPhysicalProcess)


class FeedResult(FeedEntry):
    u"""Model for feed entries about new or edited result processes.  Note that
    this model doesn't care whether the result is connected with samples or
    sample series or both.  This is distinguished in the HTML template.
    """
    result = models.ForeignKey(Result, verbose_name=_(u"result"))
    description = models.TextField(_(u"description"), blank=True)
    is_new = models.BooleanField(_(u"result is new"), null=True, blank=True)

    class Meta:
        verbose_name = _(u"result feed entry")
        verbose_name_plural = _(u"result feed entries")

    def get_metadata(self):
        _ = ugettext
        metadata = {}
        if self.is_new:
            metadata["title"] = _(u"New: %s") % self.result.title
            metadata["category term"] = "new result"
            metadata["category label"] = "new result"
        else:
            metadata["title"] = _(u"Edited: %s") % self.result.title
            metadata["category term"] = "edited result"
            metadata["category label"] = "edited result"
        metadata["link"] = self.result.get_absolute_url()
        return metadata

    def get_additional_template_context(self, user_details):
        return self.result.get_image()

admin.site.register(FeedResult)


class FeedCopiedMySamples(FeedEntry):
    u"""Model for feed entries about samples copied from one user to the “My
    Samples” list of another user.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"))
    comments = models.TextField(_(u"comments"))

    class Meta:
        verbose_name = _(u"copied My Samples feed entry")
        verbose_name_plural = _(u"copied My Samples feed entries")

    def get_metadata(self):
        _ = ugettext
        metadata = {}
        metadata["title"] = _(u"%s copied samples to you") % self.originator
        metadata["category term"] = "copied samples"
        metadata["category label"] = "copied My Samples"
        return metadata

admin.site.register(FeedCopiedMySamples)


class FeedEditedSamples(FeedEntry):
    u"""Model for feed entries for edited samples.  This includes changed
    currently responsible persons.  The respective view generates three entries
    for that, however, see `chantal.samples.views.sample.edit`.

    FixMe: This should also include sample deaths.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"))
    description = models.TextField(_(u"description"))
    responsible_person_changed = models.BooleanField(_(u"has responsible person changed"), default=False,
                                                     null=True, blank=True)

    class Meta:
        verbose_name = _(u"edited samples feed entry")
        verbose_name_plural = _(u"edited samples feed entries")

    def get_metadata(self):
        _ = ugettext
        metadata = {}
        if self.samples.count() == 1:
            metadata["title"] = _(u"Sample %s was edited") % self.samples.all()[0]
        else:
            metadata["title"] = _(u"Samples were edited")
        metadata["category term"] = "edited samples"
        metadata["category label"] = "edited samples"
        return metadata

admin.site.register(FeedEditedSamples)


class FeedSampleSplit(FeedEntry):
    u"""Model for feed entries for sample splits.
    """
    sample_split = models.ForeignKey(SampleSplit, verbose_name=_(u"sample split"))
    sample_completely_split = models.BooleanField(_(u"sample was completely split"), default=False, null=True, blank=True)

    class Meta:
        verbose_name = _(u"sample split feed entry")
        verbose_name_plural = _(u"sample split feed entries")

    def get_metadata(self):
        _ = ugettext
        metadata = {}
        metadata["title"] = _(u"Sample “%s” was split") % self.sample_split.parent
        metadata["category term"] = "split sample"
        metadata["category label"] = "split sample"
        return metadata

admin.site.register(FeedSampleSplit)


class FeedEditedSampleSeries(FeedEntry):
    u"""Model for feed entries for edited sample series.  This includes changed
    currently responsible persons.  The respective view generates two entries
    for that, however, see `chantal.samples.views.sample_series.edit`.
    """
    sample_series = models.ForeignKey(SampleSeries, verbose_name=_(u"sample series"))
    description = models.TextField(_(u"description"))
    responsible_person_changed = models.BooleanField(_(u"has responsible person changed"), default=False,
                                                     null=True, blank=True)

    class Meta:
        verbose_name = _(u"edited sample series feed entry")
        verbose_name_plural = _(u"edited sample series feed entries")

    def get_metadata(self):
        _ = ugettext
        metadata = {}
        metadata["title"] = _(u"Sample series %s was edited") % self.sample_series
        metadata["category term"] = "edited sample series"
        metadata["category label"] = "edited sample series"
        metadata["link"] = self.sample_series.get_absolute_url()
        return metadata

admin.site.register(FeedEditedSampleSeries)


class FeedNewSampleSeries(FeedEntry):
    u"""Model for feed entries for new sample series.
    """
    sample_series = models.ForeignKey(SampleSeries, verbose_name=_(u"sample series"))
    group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"group"))
    subscribers = models.ManyToManyField(UserDetails, verbose_name=_(u"subscribers"), blank=True)

    class Meta:
        verbose_name = _(u"new sample series feed entry")
        verbose_name_plural = _(u"new sample series feed entries")

    def get_metadata(self):
        _ = ugettext
        metadata = {}
        metadata["title"] = _(u"New sample series “%(sample_series)s” in group “%(group)s”") % \
            {"sample_series": self.sample_series, "group": self.group}
        metadata["category term"] = "new sample series"
        metadata["category label"] = "new sample series"
        metadata["link"] = self.sample_series.get_absolute_url()
        return metadata

    def get_additional_template_context(self, user_details):
        return {"subscribed": self.subscribers.filter(pk=user_details.pk).count() != 0}

admin.site.register(FeedNewSampleSeries)


class FeedMovedSampleSeries(FeedEntry):
    u"""Model for feed entries for sample series moved to a new group.
    """
    sample_series = models.ForeignKey(SampleSeries, verbose_name=_(u"sample series"))
    group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"group"))
    old_group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"old group"), null=True, blank=True,
                                  related_name="news_ex_sample_series")
    description = models.TextField(_(u"description"))
    subscribers = models.ManyToManyField(UserDetails, verbose_name=_(u"subscribers"), blank=True)

    class Meta:
        verbose_name = _(u"moved sample series feed entry")
        verbose_name_plural = _(u"moved sample series feed entries")

    def get_metadata(self):
        _ = ugettext
        metadata = {}
        metadata["title"] = _(u"Sample series %(sample_series)s was moved to group “%(group)s”") % \
            {"sample_series": self.sample_series, "group": self.group}
        metadata["category term"] = "moved sample series"
        metadata["category label"] = "moved sample series"
        metadata["link"] = self.sample_series.get_absolute_url()
        return metadata

    def get_additional_template_context(self, user_details):
        return {"subscribed": self.subscribers.filter(pk=user_details.pk).count() != 0}

admin.site.register(FeedMovedSampleSeries)


changed_group_action_choices = (
    ("added", _(u"added")),
    ("removed", _(u"removed")),
    )

class FeedChangedGroup(FeedEntry):
    u"""Model for feed entries for sample series moved to a new group.
    """
    group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"group"))
    action = models.CharField(_("action"), max_length=7, choices=changed_group_action_choices)

    class Meta:
        verbose_name = _(u"changed group feed entry")
        verbose_name_plural = _(u"changed group feed entries")

    def get_metadata(self):
        _ = ugettext
        metadata = {}
        if self.action == "added":
            metadata["title"] = _(u"Now in group “%s”") % self.group
        else:
            metadata["title"] = _(u"Not anymore in group “%s”") % self.group
        metadata["category term"] = "changed group membership"
        metadata["category label"] = "changed group membership"
        return metadata

admin.site.register(FeedChangedGroup)
