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


import os.path
from django.utils.translation import ugettext_lazy as _, ugettext
from django.db import models
import django.core.urlresolvers
from django.utils.http import urlquote
from django.conf import settings
from samples import permissions
import samples.models
from samples.models import Sample, PhysicalProcess
from samples.views.shared_utils import read_techplot_file
from samples.data_tree import DataNode, DataItem


apparatus_choices = (
    ("setup1", _(u"Setup #1")),
    ("setup2", _(u"Setup #2"))
)

class TestPhysicalProcess(PhysicalProcess):
    u"""Test model for physical measurements.
    """
    number = models.PositiveIntegerField(_(u"measurement number"), unique=True, db_index=True)
    raw_datafile = models.CharField(_(u"raw data file"), max_length=200,
                                    help_text=_(u"only the relative path below \"data/\""))
    evaluated_datafile = models.CharField(_(u"evaluated data file"), max_length=200,
                                          help_text=_("only the relative path below \"data/\""), blank=True)
    apparatus = models.CharField(_(u"apparatus"), max_length=15, choices=apparatus_choices, default="setup1")

    class Meta(PhysicalProcess.Meta):
        verbose_name = _(u"test measurement")
        verbose_name_plural = _(u"test measurements")
        _ = lambda x: x
        permissions = (("add_measurement", _("Can add test measurements")),
                       ("edit_permissions_for_measurement", _("Can edit perms for test measurements")),
                       ("view_every_measurement", _("Can view all test measurements")))
        ordering = ["number"]

    def __unicode__(self):
        _ = ugettext
        return _(u"Test measurement #{number}").format(number=self.number)

    def draw_plot(self, axes, number, filename, for_thumbnail):
        _ = ugettext
        x_values, y_values = read_techplot_file(filename)
        axes.semilogy(x_values, y_values)
        axes.set_xlabel(_(u"abscissa"))
        axes.set_ylabel(_(u"ordinate"))

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
        _ = ugettext
        data_node = super(TestPhysicalProcess, self).get_data_for_table_export()
        data_node.items.append(DataItem(_(u"number"), self.number))
        data_node.items.append(DataItem(_(u"apparatus"), self.get_apparatus_display()))
        data_node.items.append(DataItem(_(u"raw data file"), self.raw_datafile))
        data_node.items.append(DataItem(_(u"evaluated data file"), self.evaluated_datafile))
        return data_node
