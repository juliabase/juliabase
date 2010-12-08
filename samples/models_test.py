#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

u"""Models for testing Chantal-Samples.  Never use this code as a starting
point for your own work.  It does not represent best common practises in the
Chantal world.  In particular, nothing is translatable here.
"""

import os.path
from django.db import models
import django.core.urlresolvers
from django.utils.http import urlquote
from django.conf import settings
from chantal_common.utils import register_abstract_model
from chantal_common import search
from samples import permissions
import samples.models
from samples.models import Sample, PhysicalProcess, Process
from samples.views.shared_utils import read_techplot_file
from samples.data_tree import DataNode, DataItem


apparatus_choices = (
    ("setup1", u"Setup #1"),
    ("setup2", u"Setup #2")
)

class TestPhysicalProcess(PhysicalProcess):
    u"""Test model for physical measurements.
    """
    number = models.PositiveIntegerField(u"measurement number", unique=True, db_index=True)
    raw_datafile = models.CharField(u"raw data file", max_length=200,
                                    help_text=u"only the relative path below \"data/\"")
    evaluated_datafile = models.CharField(u"evaluated data file", max_length=200,
                                          help_text="only the relative path below \"data/\"", blank=True)
    apparatus = models.CharField(u"apparatus", max_length=15, choices=apparatus_choices, default="setup1")

    class Meta(PhysicalProcess.Meta):
        permissions = (("add_measurement", "Can add test measurements"),
                       ("edit_permissions_for_measurement", "Can edit perms for test measurements"),
                       ("view_every_measurement", "Can view all test measurements"))
        verbose_name = u"test measurement"
        verbose_name_plural = u"test measurements"
        ordering = ["number"]

    def __unicode__(self):
        return u"Test measurement #{number}".format(number=self.number)

    def draw_plot(self, axes, number, filename, for_thumbnail):
        x_values, y_values = read_techplot_file(filename)
        axes.semilogy(x_values, y_values)
        axes.set_xlabel(u"abscissa")
        axes.set_ylabel(u"ordinate")

    def get_datafile_name(self, number):
        if self.evaluated_datafile:
            return os.path.join("/mnt/data", self.evaluated_datafile)
        else:
            return os.path.join("/mnt/data", self.raw_datafile)

    def get_plotfile_basename(self, number):
        return ("measurement_for_{0}".format(self.samples.get())).replace("*", "")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(TestPhysicalProcess, self).get_data()
        data_node.items.append(DataItem(u"number", self.number))
        data_node.items.append(DataItem(u"apparatus", self.apparatus))
        data_node.items.append(DataItem(u"raw data file", self.raw_datafile))
        data_node.items.append(DataItem(u"evaluated data file", self.evaluated_datafile))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        data_node = super(TestPhysicalProcess, self).get_data_for_table_export()
        data_node.items.append(DataItem(u"number", self.number))
        data_node.items.append(DataItem(u"apparatus", self.get_apparatus_display()))
        data_node.items.append(DataItem(u"raw data file", self.raw_datafile))
        data_node.items.append(DataItem(u"evaluated data file", self.evaluated_datafile))
        return data_node


class AbstractMeasurement(PhysicalProcess):
    number = models.PositiveIntegerField(u"number", unique=True, db_index=True)

    class Meta(PhysicalProcess.Meta):
        abstract = True

    def __unicode__(self):
        return u"Appararus {apparatus_number} measurement of {sample}".format(apparatus_number=self.get_apparatus_number(),
                                                                              sample=self.samples.get())

    @classmethod
    def get_apparatus_number(cls):
        return {AbstractMeasurementOne: 1, AbstractMeasurementTwo: 2}[cls]

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(AbstractMeasurement, self).get_data()
        data_node.items.append(DataItem(u"number", self.number))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data` for the documentation.
        data_node = super(AbstractMeasurement, self).get_data_for_table_export()
        data_node.items.append(DataItem(u"number", self.number))
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        if cls != AbstractMeasurement:
            # So that derived classes don't get included into the searchable
            # models in the advanced search
            raise NotImplementedError
        search_fields = [search.TextSearchField(cls, "operator", "username"),
                         search.TextSearchField(cls, "external_operator", "name")]
        search_fields.extend(
            search.convert_fields_to_search_fields(cls, ["timestamp_inaccuracy", "cache_keys", "last_modified"]))
        related_models = {Sample: "samples"}
        return search.AbstractSearchTreeNode(
            Process, related_models, search_fields, [AbstractMeasurementOne, AbstractMeasurementTwo], u"apparatus")

register_abstract_model(AbstractMeasurement)


class AbstractMeasurementOne(AbstractMeasurement):

    class Meta(AbstractMeasurement.Meta):
        verbose_name = u"Apparatus {apparatus_number} measurement".format(apparatus_number=1)
        verbose_name_plural = u"Apparatus {apparatus_number} measurements".format(apparatus_number=1)
        permissions = (("add_abstract_measurement_one", u"Can add Apparatus 1 measurements"),
                       ("edit_permissions_for_abstract_measurement_one", "Can edit perms for Apparatus 1 measurements"),
                       ("view_every_abstract_measurement_one", "Can view all Apparatus 1 measurements"))


class AbstractMeasurementTwo(AbstractMeasurement):

    class Meta(AbstractMeasurement.Meta):
        verbose_name = u"Apparatus {apparatus_number} measurement".format(apparatus_number=2)
        verbose_name_plural = u"Apparatus {apparatus_number} measurements".format(apparatus_number=2)
        permissions = (("add_abstract_measurement_two", u"Can add Apparatus 2 measurements"),
                       ("edit_permissions_for_abstract_measurement_two", "Can edit perms for Apparatus 2 measurements"),
                       ("view_every_abstract_measurement_two", "Can view all Apparatus 2 measurements"))
