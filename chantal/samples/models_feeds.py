#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Models for feed entries.
"""

import hashlib
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.contrib import admin
from django.db import models
import django.core.urlresolvers
from chantal.samples.models_common import Sample, UserDetails, Process, Result, SampleSplit

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
    def __unicode__(self):
        _ = ugettext
        return _(u"feed entry #%d") % self.pk
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
    class Meta:
        verbose_name = _(u"feed entry")
        verbose_name_plural = _(u"feed entries")
        ordering = ["-timestamp"]

class FeedNewSamples(FeedEntry):
    u"""Model for feed entries about new samples having been added to the
    database.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"), blank=True)
    group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"group"), related_name="new_samples_news")
    purpose = models.CharField(_(u"purpose"), max_length=80, blank=True)
    auto_adders = models.ManyToManyField(UserDetails, verbose_name=_(u"auto adders"), blank=True)
    def get_metadata(self):
        _ = ugettext
        result = {}
        result["title"] = ungettext(u"New sample in “%s”", u"New samples in “%s”", self.samples.count()) % self.group
        result["category term"] = "new samples"
        result["category label"] = _(u"new samples")
        return result
    def get_additional_template_context(self, user_details):
        return {"auto_added": self.auto_adders.filter(pk=user_details.pk).count() != 0}
    class Meta:
        verbose_name = _(u"new samples feed entry")
        verbose_name_plural = _(u"new samples feed entries")
admin.site.register(FeedNewSamples)

class FeedMovedSamples(FeedEntry):
    u"""Model for feed entries about samples moved to a new group.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"), blank=True)
    group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"group"), related_name="moved_samples_news")
    old_group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"old group"))
    auto_adders = models.ManyToManyField(UserDetails, verbose_name=_(u"auto adders"), blank=True)
    description = models.TextField(_(u"description"))
    def get_metadata(self):
        _ = ugettext
        result = {}
        result["title"] = ungettext(u"New sample moved to “%s”", u"New samples moved to “%s”",
                                    self.samples.count()) % self.group
        result["category term"] = "moved samples"
        result["category label"] = _(u"moved samples")
        return result
    def get_additional_template_context(self, user_details):
        return {"auto_added": self.auto_adders.filter(pk=user_details.pk).count() != 0}
    class Meta:
        verbose_name = _(u"moved samples feed entry")
        verbose_name_plural = _(u"moved samples feed entries")
admin.site.register(FeedMovedSamples)

class FeedNewPhysicalProcess(FeedEntry):
    u"""Model for feed entries about new physical processes.
    """
    process = models.OneToOneField(Process, verbose_name=_(u"process"))
    def get_metadata(self):
        _ = ugettext
        result = {}
        process = self.process.find_actual_instance()
        result["title"] = _(u"New %s") % process
        result["category term"] = "new physical process"
        result["category label"] = _(u"new physical process")
        result["link"] = process.get_absolute_url()
        return result
    def get_additional_template_context(self, user_details):
        return {"process": self.process.find_actual_instance()}
    class Meta:
        verbose_name = _(u"new physical process feed entry")
        verbose_name_plural = _(u"new physical process feed entries")
admin.site.register(FeedNewPhysicalProcess)

class FeedEditedPhysicalProcess(FeedEntry):
    u"""Model for feed entries about edited physical processes.
    """
    process = models.ForeignKey(Process, verbose_name=_(u"process"))
    description = models.TextField(_(u"description"))
    def get_metadata(self):
        _ = ugettext
        result = {}
        process = self.process.find_actual_instance()
        result["title"] = _(u"Edited %s") % process
        result["category term"] = "new physical process"
        result["category label"] = _(u"new physical process")
        result["link"] = process.get_absolute_url()
        return result
    def get_additional_template_context(self, user_details):
        return {"process": self.process.find_actual_instance()}
    class Meta:
        verbose_name = _(u"edited physical process feed entry")
        verbose_name_plural = _(u"edited physical process feed entries")
admin.site.register(FeedEditedPhysicalProcess)

class FeedResult(FeedEntry):
    u"""Model for feed entries about new or edited result processes.
    """
    result = models.ForeignKey(Result, verbose_name=_(u"result"))
    description = models.TextField(_(u"description"), blank=True)
    is_new = models.BooleanField(_(u"result is new"), null=True, blank=True)
    def get_metadata(self):
        _ = ugettext
        metadata = {}
        if self.is_new:
            metadata["title"] = _(u"New: %s") % self.result.title
            metadata["category term"] = "new result"
            metadata["category label"] = _(u"new result")
        else:
            metadata["title"] = _(u"Edited: %s") % self.result.title
            metadata["category term"] = "edited result"
            metadata["category label"] = _(u"edited result")
        metadata["link"] = self.result.get_absolute_url()
        return metadata
    def get_additional_template_context(self, user_details):
        return self.result.get_image()
    class Meta:
        verbose_name = _(u"result feed entry")
        verbose_name_plural = _(u"result feed entries")
admin.site.register(FeedResult)

class FeedCopiedMySamples(FeedEntry):
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"))
    comments = models.TextField(_(u"comments"))
    def get_metadata(self):
        _ = ugettext
        metadata = {}
        metadata["title"] = _(u"%s copied samples to you") % self.originator
        metadata["category term"] = "copied samples"
        metadata["category label"] = _(u"copied My Samples")
        return metadata
    class Meta:
        verbose_name = _(u"copied My Samples feed entry")
        verbose_name_plural = _(u"copied My Samples feed entries")
admin.site.register(FeedCopiedMySamples)

class FeedEditedSamples(FeedEntry):
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"))
    description = models.TextField(_(u"description"))
    old_group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"old group"), null=True, blank=True)
    responsible_person_changed = models.BooleanField(_(u"has responsible person changed"), default=False,
                                                     null=True, blank=True)
    def get_metadata(self):
        _ = ugettext
        metadata = {}
        if self.samples.count() == 1:
            metadata["title"] = _(u"Sample %s was edited") % self.samples.all()[0]
        else:
            metadata["title"] = _(u"Samples were edited")
        metadata["category term"] = "edited samples"
        metadata["category label"] = _(u"edited samples")
        return metadata
    class Meta:
        verbose_name = _(u"edited samples feed entry")
        verbose_name_plural = _(u"edit samples feed entries")
admin.site.register(FeedEditedSamples)

class FeedSampleSplit(FeedEntry):
    sample_split = models.ForeignKey(SampleSplit, verbose_name=_(u"sample split"))
    def get_metadata(self):
        _ = ugettext
        metadata = {}
        metadata["title"] = _(u"Sample “%s” was split") % self.sample_split.parent
        metadata["category term"] = "split sample"
        metadata["category label"] = _(u"split sample")
        return metadata
    class Meta:
        verbose_name = _(u"sample split feed entry")
        verbose_name_plural = _(u"sample split feed entries")
admin.site.register(FeedSampleSplit)
