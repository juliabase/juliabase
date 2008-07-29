#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _
from django.contrib import admin


class Process(models.Model):
    timestamp = models.DateTimeField(_("timestamp"))
    operator = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("operator"))
    def find_actual_process(self):
        for process_type in process_types:
            if hasattr(self, process_type):
                return getattr(self, process_type)
        else:
            raise Exception("internal error: process not found")
    def __unicode__(self):
        return unicode(self.find_actual_process())
    class Meta:
        ordering = ['timestamp']
        verbose_name = _("process")
        verbose_name_plural = _("processes")

class SixChamberDeposition(Process):
    deposition_number = models.CharField(_("deposition number"), max_length=15, unique=True)
    carrier = models.CharField(_("carrier"), max_length=10, blank=True)
    comments = models.TextField(_("comments"), blank=True)
    def __unicode__(self):
        return unicode(_("6-chamber deposition ")) + self.deposition_number
    class Meta:
        verbose_name = _("6-chamber deposition")
        verbose_name_plural = _("6-chamber depositions")

class HallMeasurement(Process):
    def __unicode__(self):
        return "%s" % (self.name)
    class Meta:
        verbose_name = _("Hall measurement")
        verbose_name_plural = _("Hall measurements")

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

class SixChamberLayer(models.Model):
    number = models.IntegerField(_("layer number"))
    chamber = models.CharField(_("chamber"), max_length=5, choices=six_chamber_chamber_choices)
    deposition = models.ForeignKey(SixChamberDeposition, related_name="layers", verbose_name=_("deposition"))
    pressure = models.CharField(_("deposition pressure"), max_length=15, help_text=_("with unit"), blank=True)
    time = models.CharField(_("deposition time"), max_length=9, help_text=_("format HH:MM:SS"), blank=True)
    substrate_electrode_distance = \
        models.DecimalField(_(u"substrate–electrode distance"), null=True, blank=True, max_digits=4,
                            decimal_places=1, help_text=_(u"in mm"))
    comments = models.TextField(_("comments"), blank=True)
    transfer_in_chamber = models.CharField(_("transfer in the chamber"), max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField(_("pre-heat"), max_length=9, null=True, blank=True, help_text=_("format HH:MM:SS"))
    gas_pre_heat_gas = models.CharField(_("gas of gas pre-heat"), max_length=10, blank=True)
    gas_pre_heat_pressure = models.CharField(_("pressure of gas pre-heat"), max_length=15, blank=True,
                                             help_text=_("with unit"))
    gas_pre_heat_time = models.CharField(_("time of gas pre-heat"), max_length=15, blank=True,
                                         help_text=_("format HH:MM:SS"))
    heating_temperature = models.IntegerField(_("heating temperature"), help_text=_(u"in ℃"), null=True, blank=True)
    transfer_out_of_chamber = models.CharField(_("transfer out of the chamber"), max_length=10, default="Ar", blank=True)
    plasma_start_power = models.DecimalField(_("plasma start power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                             help_text=_(u"in W"))
    plasma_start_with_carrier = models.BooleanField(_("plasma start with carrier"), default=False, null=True, blank=True)
    deposition_frequency = models.DecimalField(_("deposition frequency"), max_digits=5, decimal_places=2,
                                               null=True, blank=True, help_text=_(u"in MHz"))
    deposition_power = models.DecimalField(_("deposition power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text=_(u"in W"))
    base_pressure = models.FloatField(_("base pressure"), help_text=_(u"in Torr"), null=True, blank=True)
    def __unicode__(self):
        return _(u"layer %(number)d of %(deposition)s") % {"number": self.number, "deposition": self.deposition}
    class Meta:
        verbose_name = _("6-chamber layer")
        verbose_name_plural = _("6-chamber layers")
        unique_together = ("deposition", "number")
        ordering = ['number']

six_chamber_gas_choices = (
    ("SiH4", "SiH4"),
    ("H2", "H2"),
    ("PH3+SiH4", _("PH3 in 2% SiH4")),
    ("TMB", _("TMB in 1% He")),
    ("B2H6", _("B2H6 in 5ppm H2")),
    ("CH4", "CH4"),
    ("CO2", "CO2"),
    ("GeH4", "GeH4"),
    ("Ar", "Ar"),
    ("Si2H6", "Si2H6"),
    ("PH3", _("PH3 in 10 ppm H2")))
    
class SixChamberChannel(models.Model):
    number = models.IntegerField(_("channel"))
    layer = models.ForeignKey(SixChamberLayer, related_name="channels", verbose_name=_("layer"))
    gas = models.CharField(_("gas and dilution"), max_length=30, choices=six_chamber_gas_choices)
    flow_rate = models.DecimalField(_("flow rate"), max_digits=4, decimal_places=1, help_text=_("in sccm"))
    def __unicode__(self):
        return _(u"channel %(number)d of %(layer)s") % {"number": self.number, "layer": self.layer}
    class Meta:
        verbose_name = _("6-chamber channel")
        verbose_name_plural = _("6-chamber channels")
        unique_together = ("layer", "number")
        ordering = ['number']

class Sample(models.Model):
    name = models.CharField(_("name"), max_length=30, unique=True)
    current_location = models.CharField(_("current location"), max_length=50)
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, related_name="samples",
                                                     verbose_name=_("currently responsible person"))
    tags = models.CharField(_("tags"), max_length=255, blank=True, help_text=_("separated with commas, no whitespace"))
    split_origin = models.ForeignKey("SampleSplit", null=True, blank=True, related_name="pieces",
                                     verbose_name=_("split origin"))
    processes = models.ManyToManyField(Process, blank=True, related_name="samples", verbose_name=_("processes"))
    group = models.ForeignKey(django.contrib.auth.models.Group, null=True, blank=True, related_name="samples",
                              verbose_name=_("group"))
    def __unicode__(self):
        return self.name
    def duplicate(self):
        # Note that `processes` is not set because many-to-many fields can only
        # be set after the object was saved.
        return Sample(name=self.name, current_location=self.current_location,
                            currently_responsible_person=self.currently_responsible_person, tags=self.tags,
                            split_origin=self.split_origin, group=self.group)
    class Meta:
        verbose_name = _("sample")
        verbose_name_plural = _("samples")
        permissions = (("view_sample", "Can view all samples"),)

class SampleAlias(models.Model):
    name = models.CharField(_("name"), max_length=30, primary_key=True)
    sample = models.ForeignKey(Sample, verbose_name=_("sample"), related_name="aliases")
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _("name alias")
        verbose_name_plural = _("name aliases")

class SampleSplit(Process):
    # for a fast lookup; actually a violation of the non-redundancy rule
    # because one could find the parent via the samples attribute every process
    # has, too.
    parent = models.ForeignKey(Sample, verbose_name=_("parent"))
    def __unicode__(self):
        return self.parent.name
    def get_additional_template_context(self, process_context):
        if process_context.current_sample != process_context.original_sample:
            parent = process_context.current_sample
        else:
            parent = None
        return {"parent": parent, "original_sample": process_context.original_sample,
                "current_sample": process_context.current_sample}
    class Meta:
        verbose_name = _("sample split")
        verbose_name_plural = _("sample splits")

class SampleSeries(models.Model):
    name = models.CharField(_("name"), max_length=255)
    samples = models.ManyToManyField(Sample, blank=True, verbose_name=_("samples"))
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _("sample series")
        verbose_name_plural = _("sample serieses")

languages = (
    ("de", "Deutsch"),
    ("en", "English"),
    )
class UserDetails(models.Model):
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_("user"))
    language = models.CharField(_("language"), max_length=10, choices=languages)
    phone = models.CharField(_("phone"), max_length=20)
    def __unicode__(self):
        return unicode(self.user)
    class Meta:
        verbose_name = _("user details")
        verbose_name_plural = _("user details")

admin.site.register(SixChamberDeposition)
admin.site.register(HallMeasurement)
admin.site.register(SixChamberLayer)
admin.site.register(SixChamberChannel)
admin.site.register(Sample)
admin.site.register(SampleAlias)
admin.site.register(SampleSplit)
admin.site.register(SampleSeries)
admin.site.register(UserDetails)

import copy, inspect
_globals = copy.copy(globals())
process_types = [cls.__name__.lower() for cls in _globals.values() if inspect.isclass(cls) and issubclass(cls, Process)]
del _globals, cls
