#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Models for physical processes except depositions.  This includes
measurements, etching processes, clean room work etc.  It may turn out that
measurements must get a module of their own if the number of Chantal models
increases further.
"""

import django.contrib.auth.models, os, codecs
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib import admin
from django.db import models
import django.core.urlresolvers
from django.conf import settings
from chantal.samples import permissions
from chantal.samples.models_common import Process, Sample, PlotError
import pylab


def read_techplot_file(filename, columns=(0, 1)):
    u"""Read a datafile in TechPlot format and return the content of selected
    columns.

    :Parameters:
      - `filename`: full path to the Techplot data file
      - `columns`: the columns that should be read.  Defaults to the first two,
        i.e., ``(0, 1)``.  Note that the column numbering starts with zero.

    :type filename: str
    :type columns: list of int

    :Return:
      List of all columns.  Every column is represented as a list of floating
      point values.

    :rtype: list of list of float

    :Exceptions:
      - `PlotError`: if something wents wrong with interpreting the file (I/O,
        unparseble data)
    """
    start_values = False
    try:
        datafile = codecs.open(filename, encoding="cp1252")
    except IOError:
        raise PlotError("datafile could not be opened")
    result = [[] for i in range(len(columns))]
    for line in datafile:
        if start_values:
            if line.startswith("END"):
                break
            cells = line.split()
            for column, result_array in zip(columns, result):
                try:
                    value = float(cells[column])
                except IndexError:
                    raise PlotError("datafile contained too few columns")
                except ValueError:
                    value = float("nan")
                result_array.append(value)
        elif line.startswith("BEGIN"):
            start_values = True
    datafile.close()
    return result


class HallMeasurement(Process):
    u"""This model is intended to store Hall measurements.  So far, all just
    fields here …
    """

    class Meta:
        verbose_name = _(u"Hall measurement")
        verbose_name_plural = _(u"Hall measurements")
        _ = lambda x: x
        permissions = (("add_edit_hall_measurement", _("Can create and edit hall measurements")),)

    def __unicode__(self):
        _ = ugettext
        try:
            _(u"hall measurement of %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            return _(u"hall measurement #%d") % self.pk

    @classmethod
    def get_add_link(cls):
        u"""Return all you need to generate a link to the “add” view for this
        process.  See `models_depositions.SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        raise NotImplementedError
        return django.core.urlresolvers.reverse("add_hall_measurement")

admin.site.register(HallMeasurement)


pds_root_dir = "/home/bronger/temp/pds/" if settings.IS_TESTSERVER else "/windows/T_www-data/daten/pds/"

class PDSMeasurement(Process):
    u"""Model for PDS measurements.
    """
    number = models.IntegerField(_(u"pds number"), unique=True, db_index=True)
    raw_datafile = models.CharField(_(u"raw data file"), max_length=200,
                                    help_text=_(u"only the relative path below \"pds/\""))
    evaluated_datafile = models.CharField(_(u"evaluated data file"), max_length=200,
                                          help_text=_("only the relative path below \"pds/\""), blank=True)

    class Meta:
        verbose_name = _(u"PDS measurement")
        verbose_name_plural = _(u"PDS measurements")
        _ = lambda x: x
        permissions = (("add_edit_pds_measurement", _("Can create and edit PDS measurements")),)

    def __unicode__(self):
        _ = ugettext
        try:
            return _(u"PDS measurement of %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            return _(u"PDS measurement #%d") % self.number

    def pylab_commands(self, number, filename):
        _ = ugettext
        x_values, y_values = read_techplot_file(filename)
        pylab.semilogy(x_values, y_values)
        pylab.xlabel(_(u"energy in eV"))
        pylab.ylabel(_(u"α in cm⁻¹"))

    def get_datafile_name(self, number):
        return os.path.join(pds_root_dir, self.evaluated_datafile)

    def get_imagefile_basename(self, number):
        try:
            return ("pds_%s" % self.samples.get()).replace("*", "")
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            return "pds_pds%d" % self.number

    def get_additional_template_context(self, process_context):
        u"""See
        `models_depositions.SixChamberDeposition.get_additional_template_context`.

        :Parameters:
          - `process_context`: the context of this process

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        result = {}
        result["thumbnail"], result["figure"] = self.generate_plot()
        if permissions.has_permission_to_add_edit_physical_process(process_context.user, self):
            result["edit_url"] = django.core.urlresolvers.reverse("edit_pds_measurement", kwargs={"pds_number": self.number})
        return result

    @classmethod
    def get_add_link(cls):
        u"""Return all you need to generate a link to the “add” view for this
        process.  See `models_depositions.SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_pds_measurement")

admin.site.register(PDSMeasurement)
