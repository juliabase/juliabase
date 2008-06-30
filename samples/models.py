#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

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
    # `name` needn't be unique!  Just a descriptive way like ``"deposition"``
    name = models.CharField(max_length=30)
    def __unicode__(self):
        return "%s #%d" % (self.name, self.id)
    class Meta:
        ordering = ['timestamp']
    class Admin:
        pass

class SixChambersDeposition(Process):
    run_title = models.CharField(max_length=15, unique=True)
    carrier = models.CharField(max_length=10)
    comments = models.TextField(blank=True)
    def __unicode__(self):
        return "%s %s" % (self.name, self.run_title)
    class Admin:
        pass

class HallMeasurement(Process):
    def __unicode__(self):
        return "%s" % (self.name)
    class Admin:
        pass

class SixChambersLayer(models.Model):
    models.IntegerField(primary_key=True)
    deposition = models.ForeignKey(SixChambersDeposition)
    pressure = models.CharField(max_length=15, help_text="with unit")
    time = models.TimeField()
    substrate_electrode_distance = models.FloatField(null=True, blank=True, help_text=u"in mm")
    comments = models.TextField(blank=True)
    transfer_in_chamber = models.CharField(max_length=10, default="Ar")
    pre_heat = models.TimeField(null=True, blank=True)
    argon_pre_heat = models.TimeField(null=True, blank=True)
    heating_temperature = models.FloatField(help_text=u"in ℃")
    transfer_out_of_chamber = models.CharField(max_length=10, default="Ar")
    plasma_start_power = models.FloatField(help_text=u"in W")
    plasma_start_with_carrier = models.BooleanField(default=False)
    deposition_frequence = models.FloatField(help_text=u"in MHz")
    deposition_power = models.FloatField(help_text=u"in W")
    base_pressure = models.FloatField(help_text=u"in Torr")
    def __unicode__(self):
        return str(self.number)
    class Admin:
        pass

class SixChambersChannel(models.Model):
    layer = models.ForeignKey(SixChambersLayer)
    number = models.IntegerField(primary_key=True)
    gas = models.CharField(max_length=10)
    diluted_in = models.CharField(max_length=10, null=True, blank=True)
    concentration = models.FloatField(null=True, blank=True, help_text="in percent")
    flow_rate = models.FloatField(help_text="in sccm")
    def __unicode__(self):
        return str(self.number)
    class Admin:
        pass

class Sample(models.Model):
    name = models.SlugField(max_length=30, primary_key=True)
    current_location = models.CharField(max_length=50)
    split_origin = models.ForeignKey("SampleSplit", null=True, blank=True, related_name="origin")
    processes = models.ManyToManyField(Process, null=True, blank=True)
    def __unicode__(self):
        return self.name
    class Admin:
        pass

class SampleSplit(Process):
    parent = models.ForeignKey(Sample)  # for a fast lookup
    def __unicode__(self):
        return "%s" % (self.name)
    class Admin:
        pass

