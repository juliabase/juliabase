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


"""Models for IEF-5-specific physical processes except depositions.  This
includes measurements, etching processes, clean room work etc.
"""

from __future__ import absolute_import, unicode_literals

import os.path, codecs, glob, sys
import matplotlib.transforms, numpy
from django.utils.translation import ugettext_lazy as _, ugettext, string_concat
from django.db import models
from django.db.models import Q
import django.core.urlresolvers
from django.core.validators import MinValueValidator
from django.utils.http import urlquote
from django.conf import settings
from samples import permissions
import samples.models_depositions
from samples.models import Process, Sample, PhysicalProcess
from samples.data_tree import DataNode, DataItem
from chantal_common.utils import register_abstract_model, format_lazy
from chantal_common import search
from samples.views import utils
from chantal_institute import layouts
import chantal_institute.views.shared_utils as institute_utils


substrate_materials = (
        # Translators: sample substrate type
    ("custom", _("custom")),
    ("asahi-u", "ASAHI-U"),
    ("asahi-vu", "ASAHI-VU"),
    ("corning", _("Corning glass")),
    ("glass", _("glass")),
    ("si-wafer", _("silicon wafer")),
    ("quartz", _("quartz")),
    ("sapphire", _("sapphire")),
    ("aluminium foil", _("aluminium foil")),
    )
"""Contains all possible choices for `Substrate.material`.
"""

class Substrate(PhysicalProcess):
    """Model for substrates.  It is the very first process of a sample.  It is
    some sort of birth certificale of the sample.  If it doesn't exist, we
    don't know when the sample was actually created.  If the substrate process
    has an `Process.external_operator`, it is an external sample.

    Note that it doesn't define permissions because everyone can create
    substrates.

    Additionally, we don't implement ``get_add_link`` because a substrate
    cannot be added by users.  Instead, it is created implicitly whenever new
    samples are created.
    """
    material = models.CharField(_("substrate material"), max_length=30, choices=substrate_materials)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("substrate")
        verbose_name_plural = _("substrates")

    def __unicode__(self):
        return _("{material} substrate #{number}").format(material=self.get_material_display(), number=self.id)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(Substrate, self).get_data()
        data_node.items.append(DataItem("ID", self.id))
        data_node.items.append(DataItem("material", self.material))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(Substrate, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("material"), self.get_material_display()))
        return data_node

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_substrate", kwargs={"substrate_id": self.id})
        else:
            context["edit_url"] = None
        return super(Substrate, self).get_context_for_user(user, context)


pds_apparatus_choices = (
    ("pds1", _("PDS #1")),
    ("pds2", _("PDS #2"))
)

class PDSMeasurement(PhysicalProcess):
    """Model for PDS measurements.
    """
    number = models.PositiveIntegerField(_("PDS number"), unique=True, db_index=True)
    raw_datafile = models.CharField(_("raw data file"), max_length=200,
                                    help_text=_("only the relative path below \"pds/\""))
    apparatus = models.CharField(_("apparatus"), max_length=15, choices=pds_apparatus_choices, default="pds1")

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("PDS measurement")
        verbose_name_plural = _("PDS measurements")
        _ = lambda x: x
        permissions = (("add_pds_measurement", _("Can add PDS measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_pds_measurement", _("Can edit perms for PDS measurements")),
                       ("view_every_pds_measurement", _("Can view all PDS measurements")))
        ordering = ["number"]

    def __unicode__(self):
        _ = ugettext
        try:
            return _("PDS measurement of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("PDS measurement #{number}").format(number=self.number)

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        _ = ugettext
        evaluated = os.path.basename(filename).lower().startswith("a_")
        x_values, y_values = utils.read_techplot_file(filename)
        axes.semilogy(x_values, y_values)
        axes.set_xlabel(_("energy in eV"))
        axes.set_ylabel(_("α in cm⁻¹") if evaluated else _("PDS signal in a.u."))
        if not evaluated:
            axes.text(0.05, 0.95, _("unevaluated"), verticalalignment="top", horizontalalignment="left",
                      transform=axes.transAxes, bbox={"edgecolor": "white", "facecolor": "white", "pad": 5}, style="italic")

    def get_datafile_name(self, plot_id):
        return os.path.join(settings.PDS_ROOT_DIR, self.raw_datafile)

    def get_plotfile_basename(self, plot_id):
        return "pds_{0}".format(self.samples.get()).replace("*", "")

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.pds_measurement.show", (), {"pds_number": urlquote(self.number, safe="")})

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_pds_measurement")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        plot_locations = self.calculate_plot_locations()
        context["thumbnail"], context["figure"] = plot_locations["thumbnail_url"], plot_locations["plot_url"]
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_pds_measurement", kwargs={"pds_number": self.number})
        else:
            context["edit_url"] = None
        return super(PDSMeasurement, self).get_context_for_user(user, context)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(PDSMeasurement, self).get_data()
        data_node.items.append(DataItem("PDS number", self.number))
        data_node.items.append(DataItem("apparatus", self.apparatus))
        data_node.items.append(DataItem("raw data file", self.raw_datafile))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(PDSMeasurement, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("PDS number"), self.number))
        data_node.items.append(DataItem(_("apparatus"), self.get_apparatus_display()))
        data_node.items.append(DataItem(_("raw data file"), self.raw_datafile))
        return data_node


class SolarsimulatorCell(models.Model):
    position = models.CharField(_("cell position"), max_length=5)
    cell_index = models.PositiveIntegerField(_("cell index"))
    data_file = models.CharField(_("data file"), max_length=200, db_index=True,
                                 help_text=_("only the relative path below \"maike_user/ascii files/\""))

    class Meta:
        abstract = True

    def __unicode__(self):
        _ = ugettext
        return _("cell {position} of {solarsimulator_measurement}").format(
            position=self.position, solarsimulator_measurement=self.measurement)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = DataNode("cell position {0}".format(self.position))
        data_node.items = [DataItem("cell index", self.cell_index),
                           DataItem("cell position", self.position),
                           DataItem("data file name", self.data_file), ]
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = DataNode(self, _("cell position {position}").format(position=self.position))
        data_node.items = [DataItem(_("cell index"), self.cell_index),
                           DataItem(_("cell position"), self.position),
                           DataItem(_("data file name"), self.data_file), ]
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :Return:
          the tree node for this model instance

        :rtype: ``chantal_common.search.SearchTreeNode``
        """
        search_fields = search.convert_fields_to_search_fields(cls)
        return search.SearchTreeNode(cls, {}, search_fields)


irradiance_choices = (("AM1.5", "AM1.5"),
                      ("OG590", "OG590"),
                      ("BG7", "BG7"))

class SolarsimulatorPhotoMeasurement(PhysicalProcess):
    irradiance = models.CharField(_("irradiance"), max_length=10, choices=irradiance_choices)
    temperature = models.DecimalField(_("temperature"), max_digits=3, decimal_places=1, help_text=_("in ℃"),
                                      default=25.0)
    best_cell_eta = models.FloatField(_("η of best cell"), help_text=_("in %"),
                                      null=True, blank=True)
    best_cell_voc = models.FloatField(_("voc of best cell"), help_text=_("in V"),
                                      null=True, blank=True)
    best_cell_isc = models.FloatField(_("isc of best cell"), help_text=_("in mA/cm²"),
                                      null=True, blank=True)
    best_cell_ff = models.FloatField(_("ff of best cell"), help_text=_(u"in %"), null=True, blank=True)
    best_cell_rsh = models.FloatField(_("rsh of best cell"), help_text=_("in Ω"), null=True, blank=True)
    best_cell_rs = models.FloatField(_("rs of best cell"), help_text=_("in Ω"), null=True, blank=True)
    best_cell_isc_b = models.FloatField(_("isc of best cell blue"), help_text=_("in mA/cm²"),
                                        null=True, blank=True)
    best_cell_isc_r = models.FloatField(_("isc of best cell red"), help_text=_("in mA/cm²"),
                                        null=True, blank=True)
    best_cell_ff_b = models.FloatField(_("ff of best cell blue"), help_text=_("in %"), null=True, blank=True)
    best_cell_ff_r = models.FloatField(_("ff of best cell red"), help_text=_("in %"), null=True, blank=True)
    median_eta = models.FloatField(_("median of η"), help_text=_(u"in %"), null=True, blank=True)
    median_voc = models.FloatField(_("median of voc"), help_text=_("in V"), null=True, blank=True)
    median_isc = models.FloatField(_("median of isc"), help_text=_("in mA/cm²"), null=True,
                                   blank=True)
    median_ff = models.FloatField(_("median of ff"), help_text=_("in %"), null=True, blank=True)
    median_rsh = models.FloatField(_("median of rsh"), help_text=_("in Ω"), null=True, blank=True)
    median_rs = models.FloatField(_("median of rs"), help_text=_("in Ω"), null=True, blank=True)
    median_isc_b = models.FloatField(_("median of isc blue"), help_text=_("in mA/cm²"), null=True,
                                     blank=True)
    median_isc_r = models.FloatField(_("median of isc red"), help_text=_("in mA/cm²"), null=True,
                                     blank=True)
    median_ff_b = models.FloatField(_("median of ff blue"), help_text=_("in %"), null=True, blank=True)
    median_ff_r = models.FloatField(_("median of ff red"), help_text=_("in %"), null=True, blank=True)
    average_five_best_eta = models.FloatField(_("η of average five best"), help_text=_("in %"), null=True,
                                              blank=True)
    average_five_best_voc = models.FloatField(_("voc of average five best"), help_text=_("in V"),
                                              null=True, blank=True)
    average_five_best_isc = models.FloatField(_("isc of average five best"),
                                              help_text=_("in mA/cm²"), null=True, blank=True)
    average_five_best_ff = models.FloatField(_("ff of average five best"), help_text=_("in %"), null=True,
                                             blank=True)
    average_five_best_rsh = models.FloatField(_("rsh of average five best"), help_text=_("in Ω"),
                                              null=True, blank=True)
    average_five_best_rs = models.FloatField(_("rs of average five best"), help_text=_("in Ω"),
                                             null=True, blank=True)
    average_five_best_isc_b = models.FloatField(_("isc of average five best blue"),
                                                help_text=_("in mA/cm²"), null=True, blank=True)
    average_five_best_isc_r = models.FloatField(_("isc of average five best red"),
                                                help_text=_("in mA/cm²"), null=True, blank=True)
    average_five_best_ff_b = models.FloatField(_("ff of average five best blue"), help_text=_("in %"), null=True,
                                               blank=True)
    average_five_best_ff_r = models.FloatField(_("ff of average five best red"), help_text=_("in %"), null=True,
                                               blank=True)
    cell_yield = models.PositiveSmallIntegerField(_("yield"), null=True, blank=True)


    class Meta(PhysicalProcess.Meta):
        verbose_name = _("solarsimulator photo measurement")
        verbose_name_plural = _("solarsimulator photo measurements")
        _ = lambda x: x
        permissions = (("add_solarsimulator_photo_measurement", _("Can add photo measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_solarsimulator_photo_measurement",
                        _("Can edit perms for photo measurements")),
                       ("view_every_solarsimulator_photo_measurement", _("Can view all photo measurements")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("solarsimulator photo measurement of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("solarsimulator photo measurement")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_solarsimulator_photo_measurement", kwargs={"process_id": self.id})
        else:
            context["edit_url"] = None
        sample = self.samples.get()
        if "shapes" not in context:
            layout = layouts.get_layout(sample, self)
            context["shapes"] = layout.get_map_shapes() if layout else {}
        context["thumbnail_layout"] = django.core.urlresolvers.reverse(
            "chantal_institute.views.samples.layout.show_layout", kwargs={"sample_id": sample.id, "process_id": self.id})
        if "cells" not in context:
            context["cells"] = self.photo_cells.all()
        if "image_urls" not in context:
            context["image_urls"] = {}
            for cell in context["cells"]:
                plot_locations = self.calculate_plot_locations(plot_id=cell.position)
                _thumbnail, _figure = plot_locations["thumbnail_url"], plot_locations["plot_url"]
                context["image_urls"][cell.position] = (_thumbnail, _figure)
        if "default_cell" not in context:
            if self.irradiance == "AM1.5":
                default_cell = sorted([(cell.eta, cell.position) for cell in context["cells"]], reverse=True)[0][1]
            else:
                default_cell = sorted([(cell.isc, cell.position) for cell in context["cells"]], reverse=True)[0][1]
            context["default_cell"] = (default_cell,) + context["image_urls"][default_cell]
        return super(SolarsimulatorPhotoMeasurement, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_solarsimulator_photo_measurement")

    def get_data(self):
        data_node = super(SolarsimulatorPhotoMeasurement, self).get_data()
        data_node.items.extend([DataItem("irradiance", self.irradiance),
                                DataItem("temperature/degC", self.temperature), ])
        data_node.children = [photo_cell.get_data() for photo_cell in self.photo_cells.all()]
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(SolarsimulatorPhotoMeasurement, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("irradiance"), self.irradiance),
                                DataItem(_("temperature") + "/℃", self.temperature)])
        if self.irradiance == "AM1.5":
            data_node.items.extend([DataItem(_("η of best cell") + "/%", utils.round(self.best_cell_eta, 3)),
                                DataItem(_("voc of best cell") + "/V", utils.round(self.best_cell_voc, 3)),
                                DataItem(_("isc of best cell") + "/mA/cm²", utils.round(self.best_cell_isc, 3)),
                                DataItem(_("ff of best cell") + "/%", utils.round(self.best_cell_ff, 3)),
                                DataItem(_("rsh of best cell") + "/Ω", utils.round(self.best_cell_rsh, 3)),
                                DataItem(_("rs of best cell") + "/Ω", utils.round(self.best_cell_rs, 3)),
                                DataItem(_("isc of best cell") + _(" blue") + "/mA/cm²", utils.round(self.best_cell_isc_b, 3)),
                                DataItem(_("isc of best cell") + _(" red") + "/mA/cm²", utils.round(self.best_cell_isc_r, 3)),
                                DataItem(_("ff of best cell") + _(" blue") + "/%", utils.round(self.best_cell_ff_b, 3)),
                                DataItem(_("ff of best cell") + _(" red") + "/%", utils.round(self.best_cell_ff_r, 3)),
                                DataItem(_("median of η") + "/%", utils.round(self.median_eta, 3)),
                                DataItem(_("median of voc") + "/V", utils.round(self.median_voc, 3)),
                                DataItem(_("median of isc") + "/mA/cm²", utils.round(self.median_isc, 3)),
                                DataItem(_("median of ff") + "/%", utils.round(self.median_ff, 3)),
                                DataItem(_("median of rsh") + "/Ω", utils.round(self.median_rsh, 3)),
                                DataItem(_("median of rs") + "/Ω", utils.round(self.median_rs, 3)),
                                DataItem(_("median of isc") + _(" blue") + "/mA/cm²", utils.round(self.median_isc_b, 3)),
                                DataItem(_("median of isc") + _(" red") + "/mA/cm²", utils.round(self.median_isc_r, 3)),
                                DataItem(_("median of ff") + _(" blue") + "/%", utils.round(self.median_ff_b, 3)),
                                DataItem(_("median of ff") + _(" red") + "/%", utils.round(self.median_ff_r, 3)),
                                DataItem(_("η of average_five_best") + "/%", utils.round(self.average_five_best_eta, 3)),
                                DataItem(_("voc of average five best") + "/V", utils.round(self.average_five_best_voc, 3)),
                                DataItem(_("isc of average five best") + "/mA/cm²",
                                         utils.round(self.average_five_best_isc, 3)),
                                DataItem(_("ff of average five best") + "/%", utils.round(self.average_five_best_ff, 3)),
                                DataItem(_("rsh of average five best") + "/Ω", utils.round(self.average_five_best_rsh, 3)),
                                DataItem(_("rs of average five best") + "/Ω", utils.round(self.average_five_best_rs, 3)),
                                DataItem(_("isc of average five best") + _(" blue") + "/mA/cm²",
                                         utils.round(self.average_five_best_isc_b, 3)),
                                DataItem(_("isc of average five best") + _(" red") + "/mA/cm²",
                                         utils.round(self.average_five_best_isc_r, 3)),
                                DataItem(_("ff of average five best") + _(" blue") + "/%", utils.round(self.average_five_best_ff_b, 3)),
                                DataItem(_("ff of average five best") + _(" red") + "/%", utils.round(self.average_five_best_ff_r, 3)),
                                DataItem(_("yield"), self.cell_yield)])
        return data_node

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        _ = ugettext
        related_cell = self.photo_cells.get(position=plot_id)
        x_values, y_values = institute_utils.read_solarsimulator_plot_file(filename, columns=(0, int(related_cell.cell_index)))
        y_values = 1000 * numpy.array(y_values)
        if not related_cell.area:
            raise utils.PlotError("Area was zero, so could not determine current density.")
        y_values /= related_cell.area
        if for_thumbnail:
            axes.set_position((0.2, 0.15, 0.6, 0.8))
        axes.plot(x_values, y_values)
        axes.axvline(color="black", x=0, zorder=0, linestyle="-")
        axes.axhline(color="black", y=0, zorder=0, linestyle="-")
        fontsize = 12
        axes.set_xlabel(_("voltage in V"), fontsize=fontsize)
        axes.set_ylabel(_("current density in mA/cm²"), fontsize=fontsize)

    def get_datafile_name(self, plot_id):
        try:
            related_cell = self.photo_cells.get(position=plot_id)
        except SolarsimulatorPhotoCellMeasurement.DoesNotExist:
            return None
        return os.path.join(settings.SOLARSIMULATOR_1_ROOT_DIR, related_cell.data_file)

    def get_plotfile_basename(self, plot_id):
        try:
            related_cell = self.photo_cells.get(position=plot_id)
        except SolarsimulatorPhotoCellMeasurement.DoesNotExist:
            return None
        return "{filename}_{position}".format(filename=related_cell.data_file, position=related_cell.position)

    @classmethod
    def get_search_tree_node(cls):
        model_field = super(SolarsimulatorPhotoMeasurement, cls).get_search_tree_node()
        model_field.search_fields = [search.TextSearchField(cls, "operator", "username"),
                         search.TextSearchField(cls, "external_operator", "name"),
                         search.DateTimeSearchField(cls, "timestamp"),
                         search.TextSearchField(cls, "comments"),
                         search.ChoiceSearchField(cls, "irradiance"),
                         search.IntervalSearchField(cls, "temperature"),
                         search.IntervalSearchField(cls, "best_cell_eta"),
                         search.IntervalSearchField(cls, "best_cell_voc"),
                         search.IntervalSearchField(cls, "best_cell_isc"),
                         search.IntervalSearchField(cls, "best_cell_ff"),
                         search.IntervalSearchField(cls, "best_cell_isc_b"),
                         search.IntervalSearchField(cls, "best_cell_isc_r"),
                         search.IntervalSearchField(cls, "best_cell_ff_b"),
                         search.IntervalSearchField(cls, "best_cell_ff_r"),
                         search.IntervalSearchField(cls, "median_eta"),
                         search.IntervalSearchField(cls, "median_voc"),
                         search.IntervalSearchField(cls, "median_isc"),
                         search.IntervalSearchField(cls, "median_ff"),
                         search.IntervalSearchField(cls, "median_isc_b"),
                         search.IntervalSearchField(cls, "median_isc_r"),
                         search.IntervalSearchField(cls, "median_ff_b"),
                         search.IntervalSearchField(cls, "median_ff_r"),
                         search.IntervalSearchField(cls, "average_five_best_eta"),
                         search.IntervalSearchField(cls, "average_five_best_voc"),
                         search.IntervalSearchField(cls, "average_five_best_isc"),
                         search.IntervalSearchField(cls, "average_five_best_ff"),
                         search.IntervalSearchField(cls, "average_five_best_isc_b"),
                         search.IntervalSearchField(cls, "average_five_best_isc_r"),
                         search.IntervalSearchField(cls, "average_five_best_ff_b"),
                         search.IntervalSearchField(cls, "average_five_best_ff_r"),
                         search.IntervalSearchField(cls, "cell_yield")]
        return model_field


class SolarsimulatorPhotoCellMeasurement(SolarsimulatorCell):
    measurement = models.ForeignKey(SolarsimulatorPhotoMeasurement, related_name="photo_cells",
                                    verbose_name=_("solarsimulator photo measurement"))
    area = models.FloatField(_("area"), help_text=_("in cm²"), null=True, blank=True)
    eta = models.FloatField(_("efficiency η"), help_text=_("in %"), null=True, blank=True)
    p_max = models.FloatField(_("maximum power point"), help_text=_("in mW"), null=True, blank=True)
    ff = models.FloatField(_("fill factor"), help_text=_("in %"), null=True, blank=True)
    voc = models.FloatField(_("open circuit voltage"), help_text=_("in V"), null=True, blank=True)
    isc = models.FloatField(_("short-circuit current density"), help_text=_("in mA/cm²"), null=True, blank=True)
    rs = models.FloatField(_("series resistance"), help_text=_("in Ω"), null=True, blank=True)
    rsh = models.FloatField(_("shunt resistance"), help_text=_("in Ω"), null=True, blank=True)
    corr_fact = models.FloatField(_("correction factor"), help_text=_("in %"), null=True, blank=True)

    class Meta:
        verbose_name = _("solarsimulator photo cell measurement")
        verbose_name_plural = _("solarsimulator photo cell measurements")
        unique_together = (("measurement", "position"), ("cell_index", "data_file"), ("position", "data_file"))

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(SolarsimulatorPhotoCellMeasurement, self).get_data()
        data_node.items.extend([DataItem("area/cm^2", self.area),
                           DataItem("efficiency/%", self.eta),
                           DataItem("maximum power point/mW", self.p_max),
                           DataItem("fill factor/%", self.ff),
                           DataItem("open circuit voltage/V", self.voc),
                           DataItem("short-circuit current density/(mA/cm^2)", self.isc),
                           DataItem("series resistance/Ohm", self.rs),
                           DataItem("shunt resistance/Ohm", self.rsh),
                           DataItem("correction factor/%", self.corr_fact)])
        return data_node

    def get_data_for_table_export(self):
        return NotImplementedError


layout_choices = (("juelich standard", "Jülich standard"),
                  ("custom", _("custom")),)

class Structuring(Process):
    """Pseudo-Process which contains structuring/mask/layout information.  It
    may contain the cell layout for solarsimulator measurements, or the
    compound hall bar/contacts layout of Hall samples, or conductivity gap
    layout etc.

    This process is supposed to be between the deposition/evaporation/etching
    processes on the one hand and the measurement processes on the other hand.
    A structuring may be immediately after the evaporation that created the
    layout, or it may be after a sequence of clean room processes which
    resulted in the layout.

    Since many layouts can be parameterised by length and width, they have
    their own numberical fields here.  More complex parameters must be written
    to ``parameters``, in JSON, or comma-separated, or however.  It only must
    be understandable by the layout class.  Furthermore, you should design the
    syntax of the ``parameters`` field so that it can be used in the advanced
    search.

    If the layout is fixed anyway, don't use ``length``, ``width``, or
    ``parameters``.
    """
    layout = models.CharField(_("layout"), max_length=30, choices=layout_choices)
    length = models.FloatField(_("length"), help_text=_("in mm"), blank=True, null=True)
    width = models.FloatField(_("width"), help_text=_("in mm"), blank=True, null=True)
    parameters = models.TextField(_("parameters"), blank=True)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("structuring")
        verbose_name_plural = _("structurings")
