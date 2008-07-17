#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
import django.contrib.auth.models

class Operator(models.Model):
    name = models.CharField(max_length=50)
    email = models.EmailField(primary_key=True)
    phone = models.CharField(max_length=20)
    def __unicode__(self):
        return self.name
    class Admin:
        pass

class Process(models.Model):
    timestamp = models.DateTimeField()
    operator = models.ForeignKey(Operator)
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
        verbose_name_plural = "processes"
    class Admin:
        pass

class SixChamberDeposition(Process):
    deposition_number = models.CharField(max_length=15, unique=True)
    carrier = models.CharField(max_length=10)
    comments = models.TextField(blank=True)
    def __unicode__(self):
        return "6-chamber deposition " + self.deposition_number
    class Meta:
        verbose_name = "6-chamber deposition"
    class Admin:
        pass

class HallMeasurement(Process):
    def __unicode__(self):
        return "%s" % (self.name)
    class Admin:
        pass

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
    number = models.IntegerField("layer number")
    chamber = models.CharField(max_length=5, choices=six_chamber_chamber_choices)
    deposition = models.ForeignKey(SixChamberDeposition)
    pressure = models.CharField("deposition pressure", max_length=15, help_text="with unit", blank=True)
    time = models.CharField("deposition time", max_length=9, help_text="format HH:MM:SS", blank=True)
    substrate_electrode_distance = models.DecimalField("substrate–electrode distance", null=True, blank=True, max_digits=4,
                                                       decimal_places=1, help_text=u"in mm")
    comments = models.TextField(blank=True)
    transfer_in_chamber = models.CharField("transfer in the chamber", max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField("pre-heat", max_length=9, null=True, blank=True, help_text="format HH:MM:SS")
    gas_pre_heat_gas = models.CharField("gas of gas pre-heat", max_length=10, blank=True)
    gas_pre_heat_pressure = models.CharField("pressure of gas pre-heat", max_length=15, blank=True, help_text="with unit")
    gas_pre_heat_time = models.CharField("time of gas pre-heat", max_length=15, blank=True, help_text="format HH:MM:SS")
    heating_temperature = models.IntegerField(help_text=u"in ℃", null=True, blank=True)
    transfer_out_of_chamber = models.CharField("transfer out of the chamber", max_length=10, default="Ar", blank=True)
    plasma_start_power = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text=u"in W")
    plasma_start_with_carrier = models.BooleanField(default=False, null=True, blank=True)
    deposition_frequency = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text=u"in MHz")
    deposition_power = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text=u"in W")
    base_pressure = models.FloatField(help_text=u"in Torr", null=True, blank=True)
    def __unicode__(self):
        return u"layer %d of %s" % (self.number, self.deposition)
    class Meta:
        verbose_name = "6-chamber layer"
        unique_together = ("deposition", "number")
        ordering = ['number']
    class Admin:
        pass

six_chamber_gas_choices = (
    ("SiH4", "SiH4"),
    ("H2", "H2"),
    ("PH3+SiH4", "PH3 in 2% SiH4"),
    ("TMB", "TMB in 1% He"),
    ("B2H6", "B2H6 in 5ppm H2"),
    ("CH4", "CH4"),
    ("CO2", "CO2"),
    ("GeH4", "GeH4"),
    ("Ar", "Ar"),
    ("Si2H6", "Si2H6"),
    ("PH3", "PH3 in 10 ppm H2"))
    
class SixChamberChannel(models.Model):
    number = models.IntegerField("channel")
    layer = models.ForeignKey(SixChamberLayer)
    gas = models.CharField("gas and dilution", max_length=30, choices=six_chamber_gas_choices)
    flow_rate = models.DecimalField(max_digits=4, decimal_places=1, help_text="in sccm")
    def __unicode__(self):
        return u"channel %d of %s" % (self.number, self.layer)
    class Meta:
        verbose_name = "6-chamber channel"
        unique_together = ("layer", "number")
        ordering = ['number']
    class Admin:
        pass

class Sample(models.Model):
    name = models.SlugField(max_length=30, primary_key=True)
    current_location = models.CharField(max_length=50)
    currently_responsible_person = models.ForeignKey(Operator)
    tags = models.CharField(max_length=255, blank=True, help_text="separated with commas, no whitespace")
    aliases = models.CharField(max_length=64, blank=True, help_text="separated with commas, no whitespace")
    split_origin = models.ForeignKey("SampleSplit", null=True, blank=True, related_name="split_origin")
    processes = models.ManyToManyField(Process, null=True, blank=True)
    def __unicode__(self):
        return self.name
    class Admin:
        pass

class SampleSplit(Process):
    parent = models.ForeignKey(Sample)  # for a fast lookup
    class Admin:
        pass

languages = (
    ("de", "Deutsch"),
    ("en", "English"),
    )
class UserDetails(models.Model):
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True)
    language = models.CharField(max_length=10, choices=languages)
    def __unicode__(self):
        return unicode(self.user)
    class Admin:
        pass

import copy, inspect
_globals = copy.copy(globals())
process_types = [cls.__name__.lower() for cls in _globals.values() if inspect.isclass(cls) and issubclass(cls, Process)]
del _globals, cls
