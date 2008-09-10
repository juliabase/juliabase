#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""This module is the connection to the database.  It contains the *models*,
i.e. Python classes which represent the tables in the relational database.
Every class which inherits from ``models.Model`` is a MySQL table at the same
time, unless it has ``abstract = True`` set in their ``Meta`` subclass.

If you add fields here, and you have a MySQL database running which contains
already valuable data, you have to add the fields manually with SQL commands to
the database, too.  (There is a project called `“Django Evolution”`_ that tries
to improve this situation.)

.. _“Django Evolution”: http://code.google.com/p/django-evolution/

However, if you add new *classes*, you can just run ``./manage.py syncdb`` and
the new tables are automatically created.

:type default_location_of_processed_samples: dict mapping `Process` to string.
:type result_process_classes: set of `Process`
"""

import hashlib
from django.db import models
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _
from django.utils.http import urlquote, urlquote_plus
import django.core.urlresolvers
from django.contrib import admin

def get_really_full_name(user):
    u"""Unfortunately, Django's ``get_full_name`` method for users returns the
    empty string if the user has no first and surname set.  However, it'd be
    sensible to use the login name as a fallback then.  This is realised here.

    :Parameters:
      - `user`: the user instance
    :type user: ``django.contrib.auth.models.User``

    :Return:
      The full, human-friendly name of the user

    :rtype: unicode
    """
    return user.get_full_name() or unicode(user)

default_location_of_processed_samples = {}
u"""Dictionary mapping process classes to strings which contain the default
location where samples can be found after this process has been performed.
This is used in `samples.views.split_after_process.GlobalNewDataForm.__init__`.
"""

result_process_classes = set()
u"""This set contains all process classes which may act as a *result*,
i.e. being used as a process for a `SampleSeries`.
"""

class ExternalOperator(models.Model):
    u"""Some samples and processes are not made in our institute but in external
    institutions.  This is realised by setting the `Process.external_operator`
    field, which in turn contains `ExternalOperator`.
    """
    name = models.CharField(_(u"name"), max_length=30)
    email = models.EmailField(_(u"email"))
    alternative_email = models.EmailField(_(u"alternative email"), null=True, blank=True)
    phone = models.CharField(_(u"phone"), max_length=30, blank=True)
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _(u"external operator")
        verbose_name_plural = _(u"external operators")
admin.site.register(ExternalOperator)

class Process(models.Model):
    u"""This is the parent class of all processes and measurements.  Actually,
    it is an *abstract* base class, i.e. there are no processes in the database
    that are *just* processes.  However, it is not marked as ``abstract=True``
    in the ``Meta`` subclass because I must be able to link to it with
    ``ForeignKey`` s.

    If you retrieve a `Process`, you may call (injected) method
    `find_actual_instance` to get the actual object, e.g. a
    `SixChamberDeposition`::

        process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id))
        process = process.find_actual_instance()

    FixMe: An open question is which `operator` should be filled in if
    `external_operator` is given.  (Note that `operator` is mandatory.)
    """
    timestamp = models.DateTimeField(_(u"timestamp"))
    operator = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"operator"))
    external_operator = models.ForeignKey(ExternalOperator, verbose_name=_("external operator"), null=True, blank=True)
    def __unicode__(self):
        return unicode(self.find_actual_instance())
    @models.permalink
    def get_absolute_url(self):
        u"""Returns the relative URL (ie, without the domain name) of the
        database object.  Django calls this method ``get_absolute_url`` to make
        clear that *only* the domain part is missing.  Apart from that, it
        includes the full URL path to where the object can be seen.

        Note that Django itself uses this method in its built-in syndication
        framework.  However currently, Chantal uses it only explicitly in
        re-directions and links in templates.

        :Return:
          Relative URL, however, starting with a “/”, to the page where one can
          view the object.

        :rtype: str
        """
        return ("samples.views.main.main_menu", (), {})
#        return ("samples.views.main.show_process", [str(self.id)])
    class Meta:
        ordering = ["timestamp"]
        verbose_name = _(u"process")
        verbose_name_plural = _(u"processes")

class Deposition(Process):
    u"""The base class for deposition processes.  Note that, like `Process`,
    this must never be instantiated.  Instead, derive the concrete deposition
    class from it.
    
    Every derived class, if it has sub-objects which resemble layers, must
    implement them as a class derived from `Layer`, with a ``ForeignKey`` field
    pointing to the deposition class with ``relative_name="layers"``.  In other
    words, ``instance.layers.all()`` must work if ``instance`` is an instance
    of your deposition class.
    """
    number = models.CharField(_(u"deposition number"), max_length=15, unique=True)
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.main.show_deposition", [urlquote(self.number, safe="")])
    def __unicode__(self):
        return _(u"deposition %s") % self.number
    class Meta:
        verbose_name = _(u"deposition")
        verbose_name_plural = _(u"depositions")

class SixChamberDeposition(Deposition):
    u"""6-chamber depositions.

    FixMe: Maybe the possibility to make comments should be avaiable to *all*
    processes?
    """
    carrier = models.CharField(_(u"carrier"), max_length=10, blank=True)
    comments = models.TextField(_(u"comments"), blank=True)
    def get_additional_template_context(self, process_context):
        u"""This method is called e.g. when the process list for a sample is
        being constructed.  It returns a dict with additional fields that are
        supposed to be given to the templates.

        ``"edit_url"`` and ``"duplicate_url"`` are somewhat special here
        because they are processed by the *outer* template (the one rendering
        the sample or sample series).  Other keys are just passed to the
        process template itself.  See also
        `samples.views.utils.ResultContext.digest_process` for further
        information.

        :Parameters:
          - `process_context`: the context of this process is for example the
            current sample, the requesting user, and maybe further info that is
            needed by the process to know what further things must be passed to
            the displaying templates (sample(-series) and process templates).

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        if process_context.user.has_perm("change_sixchamberdeposition"):
            return {"edit_url": django.core.urlresolvers.reverse("edit_6-chamber_deposition",
                                                                 kwargs={"deposition_number": self.number}),
                    "duplicate_url": "%s?copy_from=%s" % (django.core.urlresolvers.reverse("add_6-chamber_deposition"),
                                                          urlquote_plus(self.number))}
        else:
            return {}
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.six_chamber_deposition.show", [urlquote(self.number, safe="")])
    class Meta:
        verbose_name = _(u"6-chamber deposition")
        verbose_name_plural = _(u"6-chamber depositions")
        permissions = (("can_edit", "Can create and edit 6-chamber depositions"),)
default_location_of_processed_samples[SixChamberDeposition] = _(u"6-chamber deposition lab")
admin.site.register(SixChamberDeposition)

class HallMeasurement(Process):
    u"""This model is intended to store Hall measurements.  So far, all just
    fields here …
    """
    def __unicode__(self):
        try:
            _(u"hall measurement of %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            return _(u"hall measurement #%d") % self.id
    class Meta:
        verbose_name = _(u"Hall measurement")
        verbose_name_plural = _(u"Hall measurements")
admin.site.register(HallMeasurement)

class Layer(models.Model):
    u"""This is an abstract base model for deposition layers.  Now, this is the
    first *real* abstract model here.  It is abstract because it can never
    occur in a model relationship.  It just ensures that every layer has a
    number, because at least the MyLayers infrastructure relies on this.  (See
    for example `views.six_chamber_deposition.change_structure`, after ``if
    my_layer:``.)

    Every class derived from this model must point to their deposition with
    ``related_name="layers"``.  See also `Deposition`.
    """
    number = models.IntegerField(_(u"layer number"))
    class Meta:
        abstract = True
        ordering = ["number"]
        unique_together = ("deposition", "number")
        verbose_name = _(u"layer")
        verbose_name_plural = _(u"layers")

six_chamber_chamber_choices = (
    ("#1", "#1"),
    ("#2", "#2"),
    ("#3", "#3"),
    ("#4", "#4"),
    ("#5", "#5"),
    ("#6", "#6"),
    ("LL", "LL"),
    ("TL1", "TL1"),
    ("TL2", "TL2"))
u"""Contains all possible choices for `SixChamberLayer.chamber`.
"""

class SixChamberLayer(Layer):
    u"""One layer in a 6-chamber deposition.

    FixMe: Maybe `chamber` should become optional, too?
    """
    deposition = models.ForeignKey(SixChamberDeposition, related_name="layers", verbose_name=_(u"deposition"))
    chamber = models.CharField(_(u"chamber"), max_length=5, choices=six_chamber_chamber_choices)
    pressure = models.CharField(_(u"deposition pressure"), max_length=15, help_text=_(u"with unit"), blank=True)
    time = models.CharField(_(u"deposition time"), max_length=9, help_text=_(u"format HH:MM:SS"), blank=True)
    substrate_electrode_distance = \
        models.DecimalField(_(u"substrate–electrode distance"), null=True, blank=True, max_digits=4,
                            decimal_places=1, help_text=_(u"in mm"))
    comments = models.TextField(_(u"comments"), blank=True)
    transfer_in_chamber = models.CharField(_(u"transfer in the chamber"), max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField(_(u"pre-heat"), max_length=9, blank=True, help_text=_(u"format HH:MM:SS"))
    gas_pre_heat_gas = models.CharField(_(u"gas of gas pre-heat"), max_length=10, blank=True)
    gas_pre_heat_pressure = models.CharField(_(u"pressure of gas pre-heat"), max_length=15, blank=True,
                                             help_text=_(u"with unit"))
    gas_pre_heat_time = models.CharField(_(u"time of gas pre-heat"), max_length=15, blank=True,
                                         help_text=_(u"format HH:MM:SS"))
    heating_temperature = models.IntegerField(_(u"heating temperature"), help_text=_(u"in ℃"), null=True, blank=True)
    transfer_out_of_chamber = models.CharField(_(u"transfer out of the chamber"), max_length=10, default="Ar", blank=True)
    plasma_start_power = models.DecimalField(_(u"plasma start power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                             help_text=_(u"in W"))
    # FixMe:  Maybe NullBooleanField?
    plasma_start_with_carrier = models.BooleanField(_(u"plasma start with carrier"), default=False, null=True, blank=True)
    deposition_frequency = models.DecimalField(_(u"deposition frequency"), max_digits=5, decimal_places=2,
                                               null=True, blank=True, help_text=_(u"in MHz"))
    deposition_power = models.DecimalField(_(u"deposition power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text=_(u"in W"))
    base_pressure = models.FloatField(_(u"base pressure"), help_text=_(u"in Torr"), null=True, blank=True)
    def __unicode__(self):
        return _(u"layer %(number)d of %(deposition)s") % {"number": self.number, "deposition": self.deposition}
    class Meta(Layer.Meta):
        verbose_name = _(u"6-chamber layer")
        verbose_name_plural = _(u"6-chamber layers")
admin.site.register(SixChamberLayer)

six_chamber_gas_choices = (
    ("SiH4", "SiH4"),
    ("H2", "H2"),
    ("PH3+SiH4", _(u"PH3 in 2% SiH4")),
    ("TMB", _(u"TMB in 1% He")),
    ("B2H6", _(u"B2H6 in 5ppm H2")),
    ("CH4", "CH4"),
    ("CO2", "CO2"),
    ("GeH4", "GeH4"),
    ("Ar", "Ar"),
    ("Si2H6", "Si2H6"),
    ("PH3", _(u"PH3 in 10 ppm H2")))
u"""Contains all possible choices for `SixChamberChannel.gas`.
"""
    
class SixChamberChannel(models.Model):
    u"""One channel of a certain layer in a 6-chamber deposition.
    """
    number = models.IntegerField(_(u"channel"))
    layer = models.ForeignKey(SixChamberLayer, related_name="channels", verbose_name=_(u"layer"))
    gas = models.CharField(_(u"gas and dilution"), max_length=30, choices=six_chamber_gas_choices)
    flow_rate = models.DecimalField(_(u"flow rate"), max_digits=4, decimal_places=1, help_text=_(u"in sccm"))
    def __unicode__(self):
        return _(u"channel %(number)d of %(layer)s") % {"number": self.number, "layer": self.layer}
    class Meta:
        verbose_name = _(u"6-chamber channel")
        verbose_name_plural = _(u"6-chamber channels")
        unique_together = ("layer", "number")
        ordering = ["number"]
admin.site.register(SixChamberChannel)

class Sample(models.Model):
    u"""The model for samples.
    """
    name = models.CharField(_(u"name"), max_length=30, unique=True)
    current_location = models.CharField(_(u"current location"), max_length=50)
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, related_name="samples",
                                                     verbose_name=_(u"currently responsible person"))
    purpose = models.CharField(_(u"purpose"), max_length=80, blank=True)
    tags = models.CharField(_(u"tags"), max_length=255, blank=True, help_text=_(u"separated with commas, no whitespace"))
    split_origin = models.ForeignKey("SampleSplit", null=True, blank=True, related_name="pieces",
                                     verbose_name=_(u"split origin"))
    processes = models.ManyToManyField(Process, blank=True, related_name="samples", verbose_name=_(u"processes"))
    group = models.ForeignKey(django.contrib.auth.models.Group, null=True, blank=True, related_name="samples",
                              verbose_name=_(u"group"))
    def __unicode__(self):
        return self.name
    def duplicate(self):
        u"""This is used to create a new `Sample` instance with the same data as
        the current one.  Note that the `processes` field is not set because
        many-to-many fields can only be set after the object was saved.

        :Return:
          A new sample with the same data as the current.

        :rtype: `Sample`
        """
        return Sample(name=self.name, current_location=self.current_location,
                      currently_responsible_person=self.currently_responsible_person, tags=self.tags,
                      split_origin=self.split_origin, group=self.group)
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.sample.show", [urlquote(self.name, safe="")])
    class Meta:
        verbose_name = _(u"sample")
        verbose_name_plural = _(u"samples")
        ordering = ["name"]
        permissions = (("can_view_all_samples", "Can view all samples"),
                       ("can_add", "Can add samples and edit substrates"),)
admin.site.register(Sample)

class SampleAlias(models.Model):
    u"""Model for former names of samples.  If a sample gets renamed (for
    example, because it was deposited), its old name is moved here.  Note that
    aliases needn't be unique.  Two old names may be the same.  However, they
    must not be equal to a `Sample.name`.
    """
    name = models.CharField(_(u"name"), max_length=30)
    sample = models.ForeignKey(Sample, verbose_name=_(u"sample"), related_name="aliases")
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _(u"name alias")
        verbose_name_plural = _(u"name aliases")
admin.site.register(SampleAlias)

class SampleSplit(Process):
    u"""A process where a sample is split into many child samples.  The sample
    split itself is a process of the *parent*, whereas the children point to it
    through `Sample.split_origin`.  This way one can walk though the path of
    relationship in both directions.
    """
    parent = models.ForeignKey(Sample, verbose_name=_(u"parent"))
    u"""This field exists just for a fast lookup.  Its existence is actually a
    violation of the non-redundancy rule in database models because one could
    find the parent via the samples attribute every process has, too."""
    def __unicode__(self):
        return _(u"split of %s") % self.parent.name
    def get_additional_template_context(self, process_context):
        u"""See `SixChamberDeposition.get_additional_template_context` for
        general information.

        :Parameters:
          - `process_context`: context information for this process.  This
            routine needs ``current_sample`` and ``original_sample`` from the
            process context.

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          sample split template: ``"parent"``, ``"original_sample"``,  and
          ``"current_sample"``.

        :rtype: dict mapping string to arbitrary objects
        """
        assert process_context.current_sample
        if process_context.current_sample != process_context.original_sample:
            parent = process_context.current_sample
        else:
            parent = None
        return {"parent": parent, "original_sample": process_context.original_sample,
                "current_sample": process_context.current_sample}
    class Meta:
        verbose_name = _(u"sample split")
        verbose_name_plural = _(u"sample splits")
admin.site.register(SampleSplit)

substrate_materials = (
    ("asahi-u", _(u"ASAHI-U")),
    ("100-Si", _(u"silicon 100 wafer")),
    )
u"""Contains all possible choices for `Substrate.material`.
"""

class Substrate(Process):
    u"""Model for substrates.  It is very senseful, though not mandatory, that
    the very first process of a sample is a substrate process.  It is some sort
    of birth certificale of the sample.  If it doesn't exist, we don't know
    when the sample was actually created.  If the substrate process has an
    `Process.external_operator`, it is an external sample.
    """
    material = models.CharField(_(u"substrate material"), max_length=30, choices=substrate_materials)
    def __unicode__(self):
        return self.material
    class Meta:
        verbose_name = _(u"substrate")
        verbose_name_plural = _(u"substrates")
admin.site.register(Substrate)

sample_death_reasons = (
    ("split", _(u"completely split")),
    ("lost", _(u"lost and unfindable")),
    ("destroyed", _(u"completely destroyed")),
    )
u"""Contains all possible choices for `SampleDeath.reason`.
"""

class SampleDeath(Process):
    u"""This special process marks the end of the sample.  It can have various
    reasons accoring to `sample_death_reasons`.  It is impossible to add
    processes to a sample if it has a `SampleDeath` process, and its timestamp
    must be the last.
    """
    reason = models.CharField(_(u"cause of death"), max_length=50, choices=sample_death_reasons)
    def __unicode__(self):
        try:
            return _(u"cease of existence of %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            return _(u"cease of existence #%d") % self.id
    class Meta:
        verbose_name = _(u"cease of existence")
        verbose_name_plural = _(u"ceases of existence")
admin.site.register(SampleDeath)

class Comment(Process):
    u"""Adds a comment to the history of a sample.  This is also a so-called
    result process, i.e. it is allowed for being connected with a
    `SampleSeries`.
    """
    contents = models.TextField(_(u"contents"))
    def __unicode__(self):
        try:
            return _(u"comment about %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            try:
                return _(u"comment about %s") % self.sample_series.get()
            except SampleSeries.DoesNotExist, SampleSeries.MultipleObjectsReturned:
                return _(u"comment #%d") % self.id
    def get_additional_template_context(self, process_context):
        u"""See `SixChamberDeposition.get_additional_template_context` for
        general information.

        :Parameters:
          - `process_context`: context information for this process.  This
            routine needs only ``user`` from the process context.

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with one additional fields that is supposed to be given to the
          sample split template, namely ``"edit_url"``.

        :rtype: dict mapping str to str
        """
        if process_context.user == self.operator:
            return {"edit_url":
                        django.core.urlresolvers.reverse("samples.views.comment.edit", kwargs={"process_id": self.id})}
        else:
            return {}
    @classmethod
    def get_add_url(cls):
        u"""Yields the URL to the “add new” page for this process class.  This
        method must be defined for all result processes.

        :Return:
          Full but relative URL to the resource where you can add new `Comment`
          instances.

        :rtype: str
        """
        return django.core.urlresolvers.reverse("samples.views.comment.new")
    class Meta:
        verbose_name = _(u"comment")
        verbose_name_plural = _(u"comments")
admin.site.register(Comment)
result_process_classes.add(Comment)

class SampleSeries(models.Model):
    u"""A sample series groups together zero or more `Sample`.  It must belong
    to a group, and it may contain processes, however, only *result processes*
    (see `result_process_classes`).  The `name` and the `timestamp` of a sample
    series can never change after it has been created.

    FixMe: *Maybe* it's better to have result processes with its own common
    parent class.
    """
    name = models.CharField(_(u"name"), max_length=50, primary_key=True,
                            help_text=_(u"must be of the form “YY-originator-name”"))
    timestamp = models.DateTimeField(_(u"timestamp"))
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, related_name="sample_series",
                                                     verbose_name=_(u"currently responsible person"))
    samples = models.ManyToManyField(Sample, blank=True, verbose_name=_(u"samples"), related_name="series")
    results = models.ManyToManyField(Process, blank=True, related_name="sample_series", verbose_name=_(u"results"))
    group = models.ForeignKey(django.contrib.auth.models.Group, related_name="sample_series", verbose_name=_(u"group"))
    def __unicode__(self):
        return self.name
    def add_result_process(self, result_process):
        u"""Adds a new result process to the sample series.  The main purpose of
        this method is that it tests whether the given process really is a
        *result* process.

        :Parameters:
          - `result_process`: the result process to be added

        :type result_process: `Process`, however it must be in
          `result_process_classes`
        """
        assert result_process.__class__ in result_process_classes
        self.results.add(result_process)
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.sample_series.show", [urlquote(self.name, safe="")])
    class Meta:
        verbose_name = _(u"sample series")
        verbose_name_plural = _(u"sample serieses")
admin.site.register(SampleSeries)

languages = (
    ("de", "Deutsch"),
    ("en", "English"),
    )
u"""Contains all possible choices for `UserDetails.language`.
"""

class UserDetails(models.Model):
    u"""Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.

    Warning and FixMe: Currently, you run into server errors if you try to surf
    on Chantal without `UserDetails` because they are frequently used.
    Normally, there is no fallback if `UserDetails` are not avaibale (with the
    notable exception being
    `chantal.middleware.locale.LocaleMiddleware.get_language_for_user`).  There
    should be a central point for getting it – possibly as a static method of
    this class – with a decent fallback.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_(u"user"))
    language = models.CharField(_(u"language"), max_length=10, choices=languages)
    phone = models.CharField(_(u"phone"), max_length=20)
    my_samples = models.ManyToManyField(Sample, blank=True, related_name="watchers", verbose_name=_(u"my samples"))
    my_layers = models.CharField(_(u"my layers"), max_length=255, blank=True)
    u"""This string is of the form ``"nickname1: deposition1-layer1, nickname2:
    deposition2-layer2, ..."``, where “nickname” can be chosen freely except
    that it mustn't contain “:” or “,” or whitespace.  “deposition” is the
    *process id* (``Process.id``, not the deposition number!) of the
    deposition, and “layer” is the layer number (`Layer.number`).
    """
    def __unicode__(self):
        return unicode(self.user)
    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")
admin.site.register(UserDetails)

class FeedEntry(models.Model):
    u"""Abstract base model for newsfeed entries.  This is also not really
    abstract as it has a table in the database, however, it is never
    instantiated itself.  Instead, see `find_actual_instance` which is also
    injected into this class.
    """
    timestamp = models.DateTimeField(_(u"timestamp"), auto_now_add=True)
    link = models.CharField(_(u"link"), max_length=128, help_text=_(u"without domain and the leading \"/\""), blank=True)
    user = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"user"), related_name="feed_entries")
    sha1_hash = models.CharField(_(u"SHA1 hex digest"), max_length=40, blank=True, editable=False)
    u"""You'll never calculate the SHA-1 hash yourself.  It is done in
    `save`."""
    def __unicode__(self):
        return _(u"feed entry #%d") % self.id
    def get_title(self):
        u"""Return the title of this feed entry, as a plain string (no HTML).

        :Return:
          The title of this feed entry without any markup.

        :rtype: unicode
        """
        raise NotImplementedError
    def save(self, *args, **kwargs):
        u"""Before saving the feed entry, I calculate an unsalted SHA-1 from
        the timestamp, the username, and the link (if given).  It is used for
        the GUID of this entry.

        :Return:
          ``None``
        """
        entry_hash = hashlib.sha1()
        entry_hash.update(repr(self.timestamp))
        entry_hash.update(repr(self.user))
        entry_hash.update(repr(self.link))
        self.sha1_hash = entry_hash.hexdigest()
        super(FeedEntry, self).save(*args, **kwargs)
    class Meta:
        verbose_name = _(u"feed entry")
        verbose_name_plural = _(u"feed entries")
        ordering = ["-timestamp"]

class FeedNewSamples(FeedEntry):
    u"""Model for feed entries about new samples having been added to the database.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"))
    group = models.ForeignKey(django.contrib.auth.models.Group, null=True, blank=True, verbose_name=_(u"group"))
    originator = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"originator"))
    u"""The person who added the sample(s)."""
    def get_title(self):
        # FixMe: Must distinguish between one or more samples.
        if self.group:
            return _(u"%(originator)s has added new samples in group %(group)s") % \
                {"originator": get_really_full_name(self.originator), "group": self.group}
        else:
            return _(u"%s has added new samples") % get_really_full_name(self.originator)
    class Meta:
        verbose_name = _(u"new samples feed entry")
        verbose_name_plural = _(u"new samples feed entries")
admin.site.register(FeedNewSamples)

import copy, inspect
_globals = copy.copy(globals())
all_models = [cls for cls in _globals.values() if inspect.isclass(cls) and issubclass(cls, models.Model)]
class_hierarchy = inspect.getclasstree(all_models)
u"""Rather complicated list structure that represents the class hierarchy of
models in this module.  Nobody needs to understand it as long as the internal
`inject_direct_subclasses` is working."""
def find_actual_instance(self):
    u"""This is a module function but is is injected into ``Models.model`` to
    become a class method for all models of Chantal.  If you call this method
    on a database instance, you get the leaf class instance of this model.  For
    example, if you retrieved a `Process` from the database, you get the
    `SixChamberDeposition` (if it is one).  This way, polymorphism actually
    works with the relational database.

    :Return:
      an instance of the actual model class for this database entry.

    :rtype: ``models.Model``.
    """
    try:
        return self.__actual_instance
    except AttributeError:
        if not self.direct_subclasses:
            self.__actual_instance = self
        else:
            for cls in self.direct_subclasses:
                name = cls.__name__.lower()
                if hasattr(self, name):
                    instance = getattr(self, name)
                    self.__actual_instance = instance.find_actual_instance()
                    break
            else:
                raise Exception("internal error: instance not found")
        return self.__actual_instance
models.Model.find_actual_instance = find_actual_instance
def inject_direct_subclasses(parent, hierarchy):
    u"""This is a mere helper function which injects a list with all subclasses
    into the class itself, under the name ``direct_subclasses``.  It is only
    for use by `find_actual_instance`.

    This is basically a tree walker through the qeird nested data structure
    returned by ``inspect.getclasstree`` and stored in `class_hierarchy`.

    :Parameters:
      - `parent`: the class to which the subclasses should be added
      - `hierarchy`: the remaining class inheritance hierarchy that has to be
        processed.

    :type parent: class, descendant of ``models.Model``
    :type hierarchy: list as returned by ``inspect.getclasstree``
    """
    i = 0
    while i < len(hierarchy):
        hierarchy[i][0].direct_subclasses = []
        if parent:
            parent.direct_subclasses.append(hierarchy[i][0])
        if i + 1 < len(hierarchy) and isinstance(hierarchy[i+1], list):
            inject_direct_subclasses(hierarchy[i][0], hierarchy[i+1])
            i += 2
        else:
            i += 1
inject_direct_subclasses(None, class_hierarchy)
del _globals, cls
