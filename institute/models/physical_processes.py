#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Models for the INM-specific physical processes except depositions.  This
includes substrates and measurements.  For other institutions, etching
processes, clean room work etc. will go here, too.
"""

from __future__ import absolute_import, unicode_literals
from django.utils.encoding import python_2_unicode_compatible

import os.path
import numpy
from django.utils.translation import ugettext_lazy as _, ugettext
from django.db import models
import django.core.urlresolvers
from django.conf import settings
from samples import permissions
from samples.models import Process, Sample, PhysicalProcess
from samples.data_tree import DataItem
from jb_common import search, model_fields
from jb_common.utils.base import format_lazy, generate_permissions
import jb_common.utils.base
import samples.utils.views as utils
from samples.utils.plots import PlotError
import institute.layouts
import institute.utils.base


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

@python_2_unicode_compatible
class Substrate(PhysicalProcess):
    """Model for substrates.  It is the very first process of a sample.  It is
    some sort of birth certificale of the sample.  If it doesn't exist, we
    don't know when the sample was actually created.  If the substrate process
    has an `Process.external_operator`, it is an external sample.

    Note that it doesn't define permissions because everyone can create
    substrates.
    """
    material = models.CharField(_("substrate material"), max_length=30, choices=substrate_materials)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("substrate")
        verbose_name_plural = _("substrates")

    class JBMeta:
        editable_status = False

    def __str__(self):
        return _("{material} substrate #{number}").format(material=self.get_material_display(), number=self.id)


pds_apparatus_choices = (
    ("pds1", _("PDS #1")),
    ("pds2", _("PDS #2"))
)

class PDSMeasurement(PhysicalProcess):
    """Model for PDS measurements.
    """
    number = models.PositiveIntegerField(_("PDS number"), unique=True, db_index=True)
    raw_datafile = models.CharField(_("raw data file"), max_length=200,
                                    help_text=format_lazy(_('only the relative path below "{path}"'), path="pds_raw_data/"))
    apparatus = models.CharField(_("apparatus"), max_length=15, choices=pds_apparatus_choices, default="pds1")

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("PDS measurement")
        verbose_name_plural = _("PDS measurements")
        permissions = generate_permissions({"add", "view_every", "edit_permissions"}, "PDSMeasurement")
        ordering = ["number"]

    class JBMeta:
        identifying_field = "number"

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        x_values, y_values = numpy.loadtxt(filename, comments="#", unpack=True)
        axes.semilogy(x_values, y_values)
        axes.set_xlabel(_("energy in eV"))
        axes.set_ylabel(_("α in cm⁻¹"))

    def get_datafile_name(self, plot_id):
        return os.path.join(settings.PDS_ROOT_DIR, self.raw_datafile)

    def get_plotfile_basename(self, plot_id):
        return "pds_{0}".format(self.samples.get()).replace("*", "")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        plot_locations = self.calculate_plot_locations()
        context["thumbnail"], context["figure"] = plot_locations["thumbnail_url"], plot_locations["plot_url"]
        return super(PDSMeasurement, self).get_context_for_user(user, context)


irradiation_choices = (("AM1.5", "AM1.5"),
                       ("OG590", "OG590"),
                       ("BG7", "BG7"))

class SolarsimulatorMeasurement(PhysicalProcess):
    irradiation = models.CharField(_("irradiation"), max_length=10, choices=irradiation_choices)
    temperature = model_fields.DecimalQuantityField(_("temperature"), max_digits=3, decimal_places=1, unit="℃", default=25.0)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("solarsimulator measurement")
        verbose_name_plural = _("solarsimulator measurements")
        permissions = generate_permissions({"add", "view_every", "edit_permissions"}, "SolarsimulatorMeasurement")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        sample = self.samples.get()
        if "shapes" not in context:
            layout = institute.layouts.get_layout(sample, self)
            context["shapes"] = layout.get_map_shapes() if layout else {}
        context["thumbnail_layout"] = django.core.urlresolvers.reverse(
            "institute.views.samples.layout.show_layout", kwargs={"sample_id": sample.id, "process_id": self.id})
        if "cells" not in context:
            context["cells"] = self.cells.all()
        if "image_urls" not in context:
            context["image_urls"] = {}
            for cell in context["cells"]:
                plot_locations = self.calculate_plot_locations(plot_id=cell.position)
                _thumbnail, _figure = plot_locations["thumbnail_url"], plot_locations["plot_url"]
                context["image_urls"][cell.position] = (_thumbnail, _figure)
        if "default_cell" not in context:
            if self.irradiation == "AM1.5":
                default_cell = sorted([(cell.eta, cell.position) for cell in context["cells"]], reverse=True)[0][1]
            else:
                default_cell = sorted([(cell.isc, cell.position) for cell in context["cells"]], reverse=True)[0][1]
            context["default_cell"] = (default_cell,) + context["image_urls"][default_cell]
        return super(SolarsimulatorMeasurement, self).get_context_for_user(user, context)

    def get_data(self):
        # See `Process.get_data` for documentation of this method.
        data = super(SolarsimulatorMeasurement, self).get_data()
        for cell in self.cells.all():
            cell_data = cell.get_data()
            del cell_data["measurement"]
            data["cell position {}".format(cell.position)] = cell_data
        return data

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        data_node = super(SolarsimulatorMeasurement, self).get_data_for_table_export()
        best_eta = self.cells.aggregate(models.Max("eta"))["eta__max"]
        data_node.items.append(DataItem(_("η of best cell") + "/%", jb_common.utils.base.round(best_eta, 3)))
        return data_node

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        x_values, y_values = institute.utils.base.read_solarsimulator_plot_file(filename, position=plot_id)
        y_values = 1000 * numpy.array(y_values)
        related_cell = self.cells.get(position=plot_id)
        if not related_cell.area:
            raise PlotError("Area was zero, so could not determine current density.")
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
            related_cell = self.cells.get(position=plot_id)
        except SolarsimulatorCellMeasurement.DoesNotExist:
            return None
        return os.path.join(settings.SOLARSIMULATOR_1_ROOT_DIR, related_cell.data_file)

    def get_plotfile_basename(self, plot_id):
        try:
            related_cell = self.cells.get(position=plot_id)
        except SolarsimulatorCellMeasurement.DoesNotExist:
            return None
        return "{filename}_{position}".format(filename=related_cell.data_file, position=related_cell.position)

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        model_field = super(SolarsimulatorMeasurement, cls).get_search_tree_node()
        model_field.search_fields = [search.TextSearchField(cls, "operator", "username"),
                         search.TextSearchField(cls, "external_operator", "name"),
                         search.DateTimeSearchField(cls, "timestamp"),
                         search.TextSearchField(cls, "comments"),
                         search.ChoiceSearchField(cls, "irradiation"),
                         search.IntervalSearchField(cls, "temperature")]
        return model_field


@python_2_unicode_compatible
class SolarsimulatorCellMeasurement(models.Model):
    measurement = models.ForeignKey(SolarsimulatorMeasurement, related_name="cells",
                                    verbose_name=_("solarsimulator measurement"))
    position = models.CharField(_("cell position"), max_length=5)
    data_file = models.CharField(_("data file"), max_length=200, db_index=True,
                                 help_text=format_lazy(_('only the relative path below "{path}"'),
                                                       path="solarsimulator_raw_data/"))
    area = model_fields.FloatQuantityField(_("area"), unit="cm²", null=True, blank=True)
    eta = model_fields.FloatQuantityField(_("efficiency η"), unit="%", null=True, blank=True)
    isc = model_fields.FloatQuantityField(_("short-circuit current density"), unit="mA/cm²", null=True, blank=True)

    class Meta:
        verbose_name = _("solarsimulator cell measurement")
        verbose_name_plural = _("solarsimulator cell measurements")
        unique_together = (("measurement", "position"), ("position", "data_file"))

    def __str__(self):
        return _("cell {position} of {solarsimulator_measurement}").format(
            position=self.position, solarsimulator_measurement=self.measurement)

    def get_data(self):
        """Extract the data of this single cell measurement as a dictionary.  It is
        called only from `SolarsimulatorMeasurement.get_data`.

        :return:
          the content of all fields of this cell measurement

        :rtype: dict
        """
        return {field.name: getattr(self, field.name) for field in self._meta.fields}

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        search_fields = search.convert_fields_to_search_fields(cls)
        return search.SearchTreeNode(cls, {}, search_fields)


layout_choices = (("inm standard", "INM Standard"),
                  ("acme1", "ACME 1"),
                  ("custom", _("custom")),)

class Structuring(PhysicalProcess):
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
    length = model_fields.FloatQuantityField(_("length"), unit="mm", blank=True, null=True)
    width = model_fields.FloatQuantityField(_("width"), unit="mm", blank=True, null=True)
    parameters = models.TextField(_("parameters"), blank=True)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("structuring")
        verbose_name_plural = _("structurings")




method_choices = (("profilers&edge", _("profilometer + edge")),
                  ("ellipsometer", _("ellipsometer")),
                  ("calculated", _("calculated from deposition parameters")),
                  ("estimate", _("estimate")),
                  ("other", _("other")))

class LayerThicknessMeasurement(PhysicalProcess):
    """Database model for the layer thickness measurement.

    Note that it doesn't define permissions because everyone can create them.
    """
    thickness = model_fields.FloatQuantityField(_("layer thickness"), unit="nm")
    method = models.CharField(_("measurement method"), max_length=30, choices=method_choices, default="profilers&edge")

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("layer thickness measurement")
        verbose_name_plural = _("layer thickness measurements")

    class JBMeta:
        editable_status = False


_ = ugettext
