#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _
from django.contrib import admin

default_location_of_processed_samples = {}

class ExternalOperator(models.Model):
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
    timestamp = models.DateTimeField(_(u"timestamp"))
    operator = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"operator"))
    external_operator = models.ForeignKey(ExternalOperator, verbose_name=_("external operator"), null=True, blank=True)
    def __unicode__(self):
        return unicode(self.find_actual_instance())
    class Meta:
        ordering = ['timestamp']
        verbose_name = _(u"process")
        verbose_name_plural = _(u"processes")

class Deposition(Process):
    number = models.CharField(_(u"deposition number"), max_length=15, unique=True)
    def __unicode__(self):
        return unicode(self.number)
    class Meta:
        verbose_name = _(u"deposition")
        verbose_name_plural = _(u"depositions")

class SixChamberDeposition(Deposition):
    carrier = models.CharField(_(u"carrier"), max_length=10, blank=True)
    comments = models.TextField(_(u"comments"), blank=True)
    def __unicode__(self):
        return unicode(_(u"6-chamber deposition ")) + super(SixChamberDeposition, self).__unicode__()
    def get_additional_template_context(self, process_context):
        if process_context.user.has_perm("change_sixchamberdeposition"):
            return {"edit_url": "6-chamber_deposition/edit/"+self.number,
                    "duplicate_url": "6-chamber_deposition/add/?copy_from="+self.number}
        else:
            return {}
    class Meta:
        verbose_name = _(u"6-chamber deposition")
        verbose_name_plural = _(u"6-chamber depositions")
default_location_of_processed_samples[SixChamberDeposition] = _(u"6-chamber deposition lab")
admin.site.register(SixChamberDeposition)

class HallMeasurement(Process):
    def __unicode__(self):
        return unicode(self.name)
    class Meta:
        verbose_name = _(u"Hall measurement")
        verbose_name_plural = _(u"Hall measurements")
admin.site.register(HallMeasurement)

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

class Layer(models.Model):
    number = models.IntegerField(_(u"layer number"))
    # Validity constraint:  There must be a ForeignField called "deposition" to
    # the actual deposition Model, with related_name="layers".  (Otherwise,
    # duck typing doesn't work.)
    class Meta:
        abstract = True
        ordering = ['number']
        unique_together = ("deposition", "number")
        verbose_name = _(u"layer")
        verbose_name_plural = _(u"layers")

class SixChamberLayer(Layer):
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
    
class SixChamberChannel(models.Model):
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
        ordering = ['number']
admin.site.register(SixChamberChannel)

class Sample(models.Model):
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
        # Note that `processes` is not set because many-to-many fields can only
        # be set after the object was saved.
        return Sample(name=self.name, current_location=self.current_location,
                            currently_responsible_person=self.currently_responsible_person, tags=self.tags,
                            split_origin=self.split_origin, group=self.group)
    class Meta:
        verbose_name = _(u"sample")
        verbose_name_plural = _(u"samples")
        permissions = (("view_sample", "Can view all samples"),)
admin.site.register(Sample)

class SampleAlias(models.Model):
    name = models.CharField(_(u"name"), max_length=30)
    sample = models.ForeignKey(Sample, verbose_name=_(u"sample"), related_name="aliases")
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _(u"name alias")
        verbose_name_plural = _(u"name aliases")
admin.site.register(SampleAlias)

class SampleSplit(Process):
    # for a fast lookup; actually a violation of the non-redundancy rule
    # because one could find the parent via the samples attribute every process
    # has, too.
    parent = models.ForeignKey(Sample, verbose_name=_(u"parent"))
    def __unicode__(self):
        return self.parent.name
    def get_additional_template_context(self, process_context):
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

sample_death_reasons = (
    ("split", _(u"completely split")),
    ("lost", _(u"lost and unfindable")),
    ("destroyed", _(u"completely destroyed")),
    )

class SampleDeath(Process):
    reason = models.CharField(_(u"cause of death"), max_length=50, choices=sample_death_reasons)
    def __unicode__(self):
        return self.reason
    class Meta:
        verbose_name = _(u"cease of existence")
        verbose_name_plural = _(u"ceases of existence")
admin.site.register(SampleDeath)

class SampleSeries(models.Model):
    name = models.CharField(_(u"name"), max_length=50)
    originator = models.ForeignKey(django.contrib.auth.models.User, related_name="sample_series",
                                   verbose_name=_(u"originator"))
    timestamp = models.DateTimeField(_(u"timestamp"))
    # Redundant to timestamp, but necessary for "unique_together" below
    year = models.IntegerField(_(u"year"))
    samples = models.ManyToManyField(Sample, blank=True, verbose_name=_(u"samples"), related_name="series")
    results = models.ManyToManyField(Process, blank=True, related_name="sample_series", verbose_name=_(u"results"))
    group = models.ForeignKey(django.contrib.auth.models.Group, related_name="sample_series", verbose_name=_(u"group"))
    def __unicode__(self):
        return _(u"%(name)s (%(originator)s %(year)s)") % {"name": self.name,
                                                           "originator": self.originator.get_full_name() or \
                                                               unicode(self.originator),
                                                           "year": self.year}
    class Meta:
        unique_together = ("name", "originator", "year")
        verbose_name = _(u"sample series")
        verbose_name_plural = _(u"sample serieses")
admin.site.register(SampleSeries)

languages = (
    ("de", "Deutsch"),
    ("en", "English"),
    )
class UserDetails(models.Model):
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_(u"user"))
    language = models.CharField(_(u"language"), max_length=10, choices=languages)
    phone = models.CharField(_(u"phone"), max_length=20)
    my_samples = models.ManyToManyField(Sample, blank=True, related_name="watchers", verbose_name=_(u"my samples"))
    my_layers = models.CharField(_(u"my layers"), max_length=255, blank=True)
    def __unicode__(self):
        return unicode(self.user)
    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")
admin.site.register(UserDetails)

import copy, inspect
_globals = copy.copy(globals())
all_models = [cls for cls in _globals.values() if inspect.isclass(cls) and issubclass(cls, models.Model)]
class_hierarchy = inspect.getclasstree(all_models)
def find_actual_instance(self):
    if not self.direct_subclasses:
        return self
    for cls in self.direct_subclasses:
        name = cls.__name__.lower()
        if hasattr(self, name):
            instance = getattr(self, name)
            return instance.find_actual_instance()
    else:
        raise Exception("internal error: instance not found")
models.Model.find_actual_instance = find_actual_instance
def inject_direct_subclasses(parent, hierarchy):
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
