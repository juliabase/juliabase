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
from chantal_institute.models_depositions import five_chamber_chamber_choices, five_chamber_hf_frequency_choices


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


class CleaningProcess(PhysicalProcess):
    """
    """
    cleaning_number = models.CharField(_("cleaning number"), max_length=10, blank=True)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("cleaning process")
        verbose_name_plural = _("cleaning processes")
        _ = lambda x: x
        permissions = (("add_cleaning_process", _("Can clean samples")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_cleaning_process", _("Can edit perms for cleaning processes")),
                       ("view_every_cleaning_process", _("Can view all cleaning processes")))

    def __unicode__(self):
        return self.cleaning_number

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(CleaningProcess, self).get_data()
        data_node.items.append(DataItem("cleaning number", self.cleaning_number))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(CleaningProcess, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("cleaning number"), self.cleaning_number))
        return data_node

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_cleaning_process")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_cleaning_process", kwargs={"cleaning_process_id": self.id})
        else:
            context["edit_url"] = None
        return super(CleaningProcess, self).get_context_for_user(user, context)


substrate_size_choices = (
        ("custom", _("custom")),
        ("30x30", "30×30"),
        ("40x40", "40×40"))
drying_choices = (
        ("LF", "LF"),
        ("N2", "N₂"))
class LargeAreaCleaningProcess(PhysicalProcess):
    """
    """
    cleaning_number = models.CharField(_("cleaning number"), max_length=10)
    substrate_size = models.CharField(_("substrate size"), max_length=10, choices=substrate_size_choices, help_text=_("in cm²"),
                                      blank=True)
    shower_1 = models.BooleanField(_("shower 1"), default=False)
    shower_2 = models.BooleanField(_("shower 2"), default=False)
    temperature_start = models.SmallIntegerField(_("start temperature"), help_text=_("in ℃"), blank=True, null=True)
    temperature_end = models.SmallIntegerField(_("end temperature"), help_text=_("in ℃"), blank=True, null=True)
    time = models.SmallIntegerField(_("time"), help_text=_("in min"), blank=True, null=True)
    resistance = models.DecimalField(_("resistance"), max_digits=2, decimal_places=1, help_text=_("in MΩ"), blank=True, null=True)
    conductance_value_1 = models.DecimalField(_("conductance value 1"), max_digits=3, decimal_places=1, help_text=_("in MΩ"),
                                              blank=True, null=True)
    conductance_value_2 = models.DecimalField(_("conductance value 2"), max_digits=3, decimal_places=1, help_text=_("in MΩ"),
                                              blank=True, null=True)
    drying = models.CharField(_("drying"), max_length=2, choices=drying_choices, blank=True)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("large area cleaning process")
        verbose_name_plural = _("large area cleaning processes")
        _ = lambda x: x
        permissions = (("add_large_area_cleaning_process", _("Can clean large area samples")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_large_area_cleaning_process", _("Can edit perms for large area cleaning processes")),
                       ("view_every_large_area_cleaning_process", _("Can view all large area cleaning processes")))

    def __unicode__(self):
        return self.cleaning_number

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(LargeAreaCleaningProcess, self).get_data()
        data_node.items.extend([DataItem("cleaning number", self.cleaning_number),
                                DataItem("substrate size/cm^2", self.substrate_size),
                                DataItem("shower (1)", self.shower_1),
                                DataItem("shower (2)", self.shower_2),
                                DataItem("start temperature/degC", self.temperature_start),
                                DataItem("end temperature/degC", self.temperature_end),
                                DataItem("time/min", self.time),
                                DataItem("resistance/MOhm", self.resistance),
                                DataItem("conductance value (1)/MOhm", self.conductance_value_1),
                                DataItem("conductance value (2)/MOhm", self.conductance_value_2),
                                DataItem("drying", self.drying)])
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LargeAreaCleaningProcess, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("cleaning number"), self.cleaning_number),
                                DataItem(_("substrate size") + "/cm²", self.get_substrate_size_display()),
                                DataItem(_("shower") + " (1)", self.shower_1),
                                DataItem(_("shower") + " (2)", self.shower_2),
                                DataItem(_("start temperature") + "/℃", self.temperature_start),
                                DataItem(_("end temperature") + "/℃", self.temperature_end),
                                DataItem(_("time") + "/min", self.time),
                                DataItem(_("resistance") + "/MΩ", self.resistance),
                                DataItem(_("conductance value") + " (1)/MΩ", self.conductance_value_1),
                                DataItem(_("conductance value") + " (2)/MΩ", self.conductance_value_2),
                                DataItem(_("drying"), self.get_drying_display())])
        return data_node

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_large_area_cleaning_process")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_large_area_cleaning_process", kwargs={"large_area_cleaning_process_id": self.id})
        else:
            context["edit_url"] = None
        return super(LargeAreaCleaningProcess, self).get_context_for_user(user, context)

class HallMeasurement(PhysicalProcess):
    """This model is intended to store Hall measurements.  So far, all just
    fields here …
    """

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("Hall measurement")
        verbose_name_plural = _("Hall measurements")
        _ = lambda x: x
        permissions = (("add_hall_measurement", _("Can add hall measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_hall_measurement", _("Can edit perms for hall measurements")),
                       ("view_every_hall_measurement", _("Can view all hall measurements")))

    def __unicode__(self):
        _ = ugettext
        try:
            _("hall measurement of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("hall measurement #{number}").format(number=self.pk)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        raise NotImplementedError
        return django.core.urlresolvers.reverse("add_hall_measurement")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_hall_measurement", kwargs={"id": self.pk})
        else:
            context["edit_url"] = None
        return super(HallMeasurement, self).get_context_for_user(user, context)


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
        # Translators: PDS file.  Its filename starts with "a_".
    evaluated_datafile = models.CharField(_("evaluated data file"), max_length=200,
                                          help_text=_("only the relative path below \"pds/\""), blank=True)
    phase_corrected_evaluated_datafile = models.CharField(_("phase-corrected evaluated data file"), max_length=200,
                                                          help_text=_("only the relative path below \"pds/\""), blank=True)
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
        if self.phase_corrected_evaluated_datafile:
            return os.path.join(settings.PDS_ROOT_DIR, self.phase_corrected_evaluated_datafile)
        elif self.evaluated_datafile:
            return os.path.join(settings.PDS_ROOT_DIR, self.evaluated_datafile)
        else:
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
        data_node.items.append(DataItem("evaluated data file", self.evaluated_datafile))
        data_node.items.append(DataItem("phase-corrected evaluated data file", self.phase_corrected_evaluated_datafile))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(PDSMeasurement, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("PDS number"), self.number))
        data_node.items.append(DataItem(_("apparatus"), self.get_apparatus_display()))
        data_node.items.append(DataItem(_("raw data file"), self.raw_datafile))
        data_node.items.append(DataItem(_("evaluated data file"), self.evaluated_datafile))
        data_node.items.append(DataItem(_("phase-corrected evaluated data file"), self.phase_corrected_evaluated_datafile))
        return data_node


class DektakMeasurement(PhysicalProcess):
    """Model for Dektak measurements.
    """
    number = models.PositiveIntegerField(_("Dektak number"), unique=True, db_index=True)
    thickness = models.DecimalField(_("layer thickness"), max_digits=6, decimal_places=1, help_text=_("in nm"))

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("Dektak measurement")
        verbose_name_plural = _("Dektak measurements")
        _ = lambda x: x
        permissions = (("add_dektak_measurement", _("Can add Dektak measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_dektak_measurement", _("Can edit perms for Dektak measurements")),
                       ("view_every_dektak_measurement", _("Can view all Dektak measurements")))

    def __unicode__(self):
        _ = ugettext
        return _("Dektak measurement #{number}").format(number=self.number)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_dektak_measurement")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_dektak_measurement", kwargs={"dektak_number": self.number})
        else:
            context["edit_url"] = None
        return super(DektakMeasurement, self).get_context_for_user(user, context)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(DektakMeasurement, self).get_data()
        data_node.items.append(DataItem("layer thickness/nm", self.thickness))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(DektakMeasurement, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("layer thickness") + "/nm", self.thickness))
        return data_node


luma_laser_type_choices = (
    ("red", _("red")),
)

class LumaMeasurement(PhysicalProcess):
    """Model for Luma (“Laser unterstützte Meßanlage”) measurements.
    """
    filepath = models.CharField(_("data file"), max_length=200, help_text=_("only the relative path below \"luma/\""),
                                unique=True)
    laser_type = models.CharField(_("laser type"), max_length=10, choices=luma_laser_type_choices, default="red")
    laser_intensity = models.DecimalField(_("laser intensity"), max_digits=5, decimal_places=1,
                                          help_text=string_concat(_("without filter"), ", ", _("in mW")),
                                          blank=True, null=True)
    cell_position = models.CharField(_("cell position"), max_length=5)
    cell_area = models.FloatField(_("cell area"), help_text=_("in cm²"))

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("Luma measurement")
        verbose_name_plural = _("Luma measurements")
        _ = lambda x: x
        permissions = (("add_luma_measurement", _("Can add Luma measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_luma_measurement", _("Can edit perms for Luma measurements")),
                       ("view_every_luma_measurement", _("Can view all Luma measurements")))

    def __unicode__(self):
        _ = ugettext
        return _("Luma measurement of {sample}, cell {cell}").format(sample=self.samples.get(), cell=self.cell_position)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_luma_measurement")

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        """`plot_id` is "iv" or "r_s"."""
        _ = ugettext
        dark_curve_u, dark_curve_j, vocs, jscs = institute_utils.read_luma_file(filename)
        if plot_id == "iv":
            axes.semilogy(vocs, jscs, "bo:")
            axes.semilogy(dark_curve_u, dark_curve_j)
            axes.set_xlim(0)
            axes.set_xlabel(_("Voc in V"))
            axes.set_ylabel(_("Jsc in mA/cm²"))
        else:
            assert plot_id == "r_s"
            r_s, voltages, n = institute_utils.evaluate_luma(dark_curve_u, dark_curve_j, vocs, jscs)
            r_s_axes = axes
            r_s_axes.plot(vocs, r_s, "ro:")
            r_s_axes.set_xlabel(_("voltage in V"))
            r_s_axes.set_ylabel(_("Rs in Ω·cm² (red)"))
            r_s_axes.grid(False)
            n_axes = r_s_axes.twinx()
            n_axes.plot(voltages, n, "ko:")
            n_axes.set_ylabel(_("ideal factor (black)"))
            bbox = r_s_axes.get_position()
            bbox.x0 += 0.03
            bbox.x1 -= 0.05
            r_s_axes.set_position(bbox)
            n_axes.set_position(bbox)

    def get_datafile_name(self, plot_id):
        return os.path.join(settings.LUMA_ROOT_DIR, self.filepath)

    def get_plotfile_basename(self, plot_id):
        return "luma_{0}-{1}_{2}".format(self.samples.get(), self.cell_position, plot_id).replace("*", "")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        plot_locations = self.calculate_plot_locations("iv")
        context["thumbnail_iv"], context["figure_iv"] = plot_locations["thumbnail_url"], plot_locations["plot_url"]
        plot_locations = self.calculate_plot_locations("r_s")
        context["thumbnail_r_s"], context["figure_r_s"] = plot_locations["thumbnail_url"], plot_locations["plot_url"]
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_luma_measurement", kwargs={"process_id": self.pk})
        else:
            context["edit_url"] = None
        return super(LumaMeasurement, self).get_context_for_user(user, context)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(LumaMeasurement, self).get_data()
        data_node.items.extend([DataItem("ID", self.pk),
                                DataItem("data file", self.filepath),
                                DataItem("laser type", self.laser_type),
                                DataItem("laser intensity/mW", self.laser_intensity),
                                DataItem("cell position", self.cell_position),
                                DataItem("cell area/cm^2", self.cell_area)])
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LumaMeasurement, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("data file"), self.filepath),
                                DataItem(_("laser type"), self.get_laser_type_display()),
                                DataItem(_("laser intensity") + "/mW", self.laser_intensity),
                                DataItem(_("cell position"), self.cell_position),
                                DataItem(_("cell area") + "/cm²", self.cell_area)])
        return data_node


conductivity_apparatus_choices = (
    ("conductivity0", _("conductivity #0")),
    ("conductivity1", _("conductivity #1")),
    ("conductivity2", _("conductivity #2")),
)

class ConductivityMeasurementSet(PhysicalProcess):
    """This model combines all conductivity measurements which were processed
    in the same vacuum into one single process.
    """
    apparatus = models.CharField(_("apparatus"), max_length=13, choices=conductivity_apparatus_choices)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("conductivity measurement")
        verbose_name_plural = _("conductivity measurements")
        _ = lambda x: x
        permissions = (("add_conductivity_measurement_set", _("Can add conductivity measurements")),
                       ("edit_permissions_for_conductivity_measurement_set",
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                        _("Can edit perms for conductivity measurements")),
                       ("view_every_conductivity_measurement_set", _("Can view all conductivity measurements")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("conductivity measurement of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("conductivity measurement #{number}").format(number=self.pk)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_conductivity_measurement")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = django.core.urlresolvers.reverse("edit_conductivity_measurement",
                                                                   kwargs={"conductivity_set_pk": self.pk})
        else:
            context["edit_url"] = None
        if "single_measurements" not in context:
            context["single_measurements"] = []
            for measurement in self.single_measurements.all():
                if measurement.kind in ["characteristic curve", "temperature-dependent"]:
                    plot_context = self.calculate_plot_locations(unicode(measurement.number))
                    context["single_measurements"].append(
                        (measurement, plot_context["plot_url"], plot_context["thumbnail_url"]))
                else:
                    context["single_measurements"].append((measurement, None, None))
        return super(ConductivityMeasurementSet, self).get_context_for_user(user, context)

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        from matplotlib.ticker import FormatStrFormatter
        majorFormatter = FormatStrFormatter('%1.3g')
        _ = ugettext
        kind = self.single_measurements.get(number=int(plot_id)).kind
        if kind == "characteristic curve":
            x_values, y1_values, y2_values = utils.read_techplot_file(filename, (0, 1, 2))
            y1_values = numpy.array(y1_values)
            y1_values[numpy.array(x_values) < 0] *= -1
            x_label, y_label, y2_label = _("voltage in V"), _("el. current in A"), _("σ in S/cm")
        else:
            x_values, y_values = utils.read_techplot_file(filename, (0, 2))
            x_values = 1000 / numpy.array(x_values)
            x_label, y_label = _("1/T in 1000/K"), _("σ in S/cm")
        if for_thumbnail:
            axes.set_position((0.2, 0.15, 0.6, 0.75))
        if kind == "characteristic curve":
            axes.plot(x_values, y1_values, color="b")
        else:
            axes.semilogy(x_values, y_values, color="b")
        fontsize = 9
        axes.set_xlabel(x_label, fontsize=fontsize)
        axes.set_ylabel(y_label, fontsize=fontsize)
        axes.yaxis.set_major_formatter(majorFormatter)
        for x in axes.get_xticklabels():
            x.set_fontsize(fontsize)
        for yl in axes.get_yticklabels():
            yl.set_fontsize(fontsize)
            if kind == "characteristic curve":
                yl.set_color("b")
        if kind == "characteristic curve":
            axes2 = axes.twinx()
            axes2.plot(x_values, y2_values, color="r")
            axes2.set_ylabel(y2_label, fontsize=fontsize)
            axes2.yaxis.set_major_formatter(majorFormatter)
            for yr in axes2.get_yticklabels():
                yr.set_fontsize(fontsize)
                yr.set_color("r")

    def get_datafile_name(self, plot_id):
        try:
            measurement = self.single_measurements.get(number=utils.int_or_zero(plot_id))
        except SingleConductivityMeasurement.DoesNotExist:
            return None
        return os.path.join(settings.MEASUREMENT_DATA_ROOT_DIR, measurement.filepath)

    def get_plotfile_basename(self, plot_id):
        try:
            measurement = self.single_measurements.get(number=utils.int_or_zero(plot_id))
        except SingleConductivityMeasurement.DoesNotExist:
            return None
        return "{apparatus}_{filename}".format(
            apparatus=self.apparatus,
            filename=measurement.filepath[measurement.filepath.rfind("/") + 1:].replace(".dat", ""))

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(ConductivityMeasurementSet, self).get_data()
        data_node.items.extend([DataItem("ID", self.pk),
                                DataItem("apparatus", self.apparatus)])
        data_node.children = [single_measurement.get_data() for single_measurement in self.single_measurements.all()]
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(ConductivityMeasurementSet, self).get_data_for_table_export()
        data_node.items = [DataItem(_("apparatus"), self.get_apparatus_display())]
        data_node.children = [single_measurement.get_data_for_table_export()
                              for single_measurement in self.single_measurements.all()]
        return data_node


light_choices = (
    ("dark", _("dark")),
    ("photo", _("photo")))

conductivity_kind_choices = (
    ("characteristic curve", _("characteristic curve")),
    ("temperature-dependent", _("temperature-dependent")),
    ("single sigma", _("single σ")))

class SingleConductivityMeasurement(models.Model):
    """Model for Conductivity measurements.
    """
    measurement_set = models.ForeignKey(ConductivityMeasurementSet, related_name="single_measurements",
                                        verbose_name=_("conductivity measurement set"))
    number = models.PositiveIntegerField(_("measurement number"))
    kind = models.CharField(_("kind"), choices=conductivity_kind_choices, max_length=30)
    filepath = models.CharField(_("data file"), max_length=200, help_text=_("only the relative path below \"daten/\""),
                                unique=True)
    light = models.CharField(_("light conditions"), choices=light_choices, max_length=5)
    tempering_time = models.PositiveIntegerField(_("temper time"), blank=True, null=True, help_text=_("in min"))
    tempering_temperature = models.PositiveIntegerField(_("temper temperature"), blank=True, null=True,
                                                        help_text=_("in K"))
    temperature = models.DecimalField(_("temperature"), max_digits=5, decimal_places=2, help_text=_("in K"),
                                      blank=True, null=True)
    sigma = models.FloatField("&#x3c3;", help_text=_("in S/cm"), blank=True, null=True)
    voltage = models.DecimalField(_("voltage"), max_digits=5, decimal_places=1, help_text=_("in V"),
                                  blank=True, null=True)
    assumed_thickness = models.DecimalField(_("assumed thickness"), max_digits=7, decimal_places=0, help_text=_("in nm"),
                                            blank=True, null=True)
    temperature_dependent = models.BooleanField(_("temperature-dependent"), default=False)
    in_vacuum = models.BooleanField(_("in vacuum"), default=True)
    timestamp = models.DateTimeField(_("timestamp"))
    timestamp_inaccuracy = models.PositiveSmallIntegerField(_("timestamp inaccuracy"),
                                                            choices=samples.models.timestamp_inaccuracy_choices,
                                                            default=0)
    comments = models.TextField(_("comments"), blank=True)

    class Meta(PhysicalProcess.Meta):
        ordering = ["number"]
        verbose_name = _("Single conductivity measurement")
        verbose_name_plural = _("Single conductivity measurements")
        unique_together = ("measurement_set", "number")

    def __unicode__(self):
        _ = ugettext
        return _("single conductivity measurement #{number} from {set}").format(number=self.number,
                                                                                 set=self.measurement_set)

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

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = DataNode("conductivity measurement {0}".format(self.number))
        data_node.items = [DataItem("number", self.number),
                           DataItem("data file", self.filepath),
                           DataItem("kind", self.kind),
                           DataItem("temper time/min", self.tempering_time),
                           DataItem("temper temperature/K", self.tempering_temperature),
                           DataItem("in vacuum", self.in_vacuum),
                           DataItem("light conditions", self.light),
                           DataItem("sigma/(S/cm)", self.sigma),
                           DataItem("voltage/V", self.voltage),
                           DataItem("assumed thickness/nm", self.assumed_thickness),
                           DataItem("temperature/K", self.temperature),
                           DataItem("timestamp", self.timestamp),
                           DataItem("timestamp inaccuracy", self.timestamp_inaccuracy),
                           DataItem("comments", self.comments.strip())]
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = DataNode(self, _("conductivity measurement {number}").format(number=self.number))
        data_node.items = [DataItem(_("number"), self.number),
                           DataItem(_("data file"), self.filepath),
                           DataItem(_("kind"), self.get_kind_display()),
                           DataItem(_("temper time") + "/min", self.tempering_time),
                           DataItem(_("temper temperature") + "/K", self.tempering_temperature),
                           DataItem(_("in vacuum"), self.in_vacuum),
                           DataItem(_("light conditions"), self.get_light_display()),
                           DataItem("σ/(S/cm)", self.sigma),
                           DataItem(_("voltage") + "/V", self.voltage),
                           DataItem(_("assumed thickness") + "/nm", self.assumed_thickness),
                           DataItem(_("temperature") + "/K", self.temperature),
                           DataItem(_("timestamp"), self.timestamp),
                           DataItem(_("comments"), self.comments.strip())]
        return data_node


raman_kind_choices = (
    ("single", _("single")),
    ("line scan", _("line scan")),
    ("2D", "2D"),
    ("time-resolved", _("time-resolved")),
)
raman_excitation_choices = (
    ("??", _("unknown")),
    ("413", "413"),
    ("488", "488"),
    ("532", "532"),
    ("647", "647"),
    ("752", "752"),
)
raman_setup_choices = (
    ("unknown", _("unknown")),
    ("micro", _("micro")),
    ("macro", _("macro")),
)
raman_detector_choices = (
    ("unknown", _("unknown")),
    ("silicon CCD", _("silicon CCD")),
    ("InGaAs", "InGaAs"),
    ("photomultiplier", _("photomultiplier")),
)

class RamanMeasurement(PhysicalProcess):
    """Model for the Raman Measurement
    """
    number = models.PositiveIntegerField(_("number"), unique=True, db_index=True)
    kind = models.CharField(_("kind"), max_length=20, choices=raman_kind_choices, default="single")
    datafile = models.CharField(_("data file"), max_length=200,
                                help_text=_("only the relative path below \"daten/\""), unique=True)
    evaluated_datafile = models.CharField(_("evaluated data file"), max_length=200,
                                          help_text=_("only the relative path below \"daten/\""), blank=True)
    central_wavelength = models.DecimalField(_("&#x3bb;<sub>central</sub>"), max_digits=6, decimal_places=2,
                                             help_text=_("in nm"))
    excitation_wavelength = models.CharField(_("&#x3bb;<sub>excitation</sub>"), max_length=3,
                                             choices=raman_excitation_choices, help_text=_("in nm"))
    slit = models.DecimalField(_("slit"), max_digits=5, decimal_places=2, help_text=_("in μm"))
    accumulation = models.IntegerField(_("accumulation"))
    time = models.DecimalField(_("measurement time"), max_digits=5, decimal_places=2, help_text=_("in seconds"))
    laser_power = models.DecimalField(_("laser power"), max_digits=4, decimal_places=2, help_text=_("in mW"))
    filters = models.CharField(_("filters"), max_length=200, blank=True)
    icrs = models.DecimalField("I<sub>c</sub><sup>RS</sup>", max_digits=4, decimal_places=2, help_text=_("in %"),
                               blank=True, null=True)
    grating = models.PositiveIntegerField(_("grating"), blank=True, null=True)
    objective = models.CharField(_("objective"), max_length=30, blank=True)
    position_a_si = models.DecimalField(_("peak position a-Si:H"), max_digits=5, decimal_places=2, help_text=_("in cm⁻¹"),
                                        blank=True, null=True)
    position_muc_si = models.DecimalField(_("peak position µc-Si:H"), max_digits=5, decimal_places=2,
                                          help_text=_("in cm⁻¹"), blank=True, null=True)
    width_a_si = models.DecimalField(_("peak width a-Si:H"), max_digits=5, decimal_places=2, help_text=_("in cm⁻¹"),
                                     blank=True, null=True)
    width_muc_si = models.DecimalField(_("peak width µc-Si:H"), max_digits=5, decimal_places=2, help_text=_("in cm⁻¹"),
                                       blank=True, null=True)
    through_substrate = models.BooleanField(_("measured through substrate"), default=False)
    setup = models.CharField(_("setup"), max_length=30, choices=raman_setup_choices)
    detector = models.CharField(_("detector"), max_length=30, choices=raman_detector_choices)
    dektak_measurement = models.ForeignKey(DektakMeasurement, related_name="+", null=True, blank=True,
                                           verbose_name=_("profile measurement"))
    sampling_distance_x = models.DecimalField(format_lazy(_("sampling distance {direction}"), direction="x"),
                                              max_digits=7, decimal_places=4, help_text=_("in mm"), blank=True, null=True)
    sampling_distance_y = models.DecimalField(format_lazy(_("sampling distance {direction}"), direction="y"),
                                              max_digits=7, decimal_places=4, help_text=_("in mm"), blank=True, null=True)
    number_points_x = models.PositiveIntegerField(format_lazy(_("number of points {direction}"), direction="x"),
                                                  blank=True, null=True)
    number_points_y = models.PositiveIntegerField(format_lazy(_("number of points {direction}"), direction="y"),
                                                  blank=True, null=True)
    sampling_period = models.DecimalField(_("sampling period"), max_digits=7, decimal_places=2, help_text=_("in s"),
                                          blank=True, null=True)

    class Meta(PhysicalProcess.Meta):
        abstract = True
        verbose_name = _("Raman measurement")
        verbose_name_plural = _("Raman measurements")
        # FixMe: The following line is necessary as long as
        # http://code.djangoproject.com/ticket/11369 is not fixed.
        ordering = ["timestamp"]

    def __unicode__(self):
        _ = ugettext
        return _("Raman {apparatus_number} measurement of {sample}").format(apparatus_number=self.get_apparatus_number(),
                                                                             sample=self.samples.get())

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        _ = ugettext
        evaluated = os.path.basename(filename).lower().endswith("rat")
        if evaluated:
            x_values, y_values = utils.read_techplot_file(filename)
            axes.plot(x_values, y_values)
            axes.set_ylim(ymin= -0.05)
            axes.set_xlim((400, 560))
            axes.set_ylabel(_("intensity (normalised)"))
        else:
            try:
                x_values, y_values = numpy.loadtxt(filename, usecols=(0, 1), comments="\x1a", unpack=True)
            except:
                raise utils.PlotError("File “{0}” was inaccessible or invalid.".format(os.path.basename(filename)))
            axes.plot(x_values, y_values)
            axes.set_ylabel(_("counts"))
            axes.text(0.95, 0.05, _("unevaluated"), verticalalignment="bottom", horizontalalignment="right",
                      transform=axes.transAxes, bbox={"edgecolor": "white", "facecolor": "white", "pad": 5},
                      style="italic")
            points = axes.get_position().get_points()
            points[0][0] += 0.05
            axes.set_position(matplotlib.transforms.Bbox(points))
        axes.set_xlabel(_("wavenumber in cm⁻¹"))

    def get_datafile_name(self, plot_id):
        if self.evaluated_datafile:
            filepath = os.path.join(settings.MEASUREMENT_DATA_ROOT_DIR, self.evaluated_datafile)
            return filepath if os.path.isfile(filepath) else None
        else:
            return os.path.join(settings.MEASUREMENT_DATA_ROOT_DIR, self.datafile)

    def get_plotfile_basename(self, plot_id):
        return "raman_{0}".format(self.samples.get()).replace("*", "")

    @classmethod
    def get_apparatus_number(cls):
        """Returns the number of the Raman apparatus, which is 1, 2, or 3.

        :Return:
          the number of the Raman apparatus, which is 1, 2, or 3

        :rtype: int
        """
        return {RamanMeasurementOne: 1, RamanMeasurementTwo: 2, RamanMeasurementThree: 3}[cls]

    @classmethod
    def get_lab_notebook_context(cls, year, month):
        # I only change ordering here.
        processes = cls.objects.filter(timestamp__year=year, timestamp__month=month).select_related()
        return {"processes": sorted(processes, key=lambda process: process.number, reverse=True)}

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        plot_locations = self.calculate_plot_locations()
        context["thumbnail"], context["figure"] = plot_locations["thumbnail_url"], plot_locations["plot_url"]
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = django.core.urlresolvers.reverse(
                "edit_raman_measurement", kwargs={"raman_number": self.number,
                                                  "apparatus_number": self.get_apparatus_number()})
        else:
            context["edit_url"] = None
        return super(RamanMeasurement, self).get_context_for_user(user, context)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(RamanMeasurement, self).get_data()
        data_node.items.extend([DataItem("number", self.number),
                                DataItem("data file", self.datafile),
                                DataItem("kind", self.kind),
                                DataItem("dektak measurement", self.dektak_measurement and self.dektak_measurement.id),
                                DataItem("evaluated data file", self.evaluated_datafile),
                                DataItem("lambda (central/nm)", self.central_wavelength),
                                DataItem("lambda (excitation/nm)", self.excitation_wavelength),
                                DataItem("slit/um", self.slit),
                                DataItem("accumulation", self.accumulation),
                                DataItem("measurement time/s", self.time),
                                DataItem("laser power/mW", self.laser_power),
                                DataItem("filters", self.filters),
                                DataItem("IcRS/%", self.icrs),
                                DataItem("grating", self.grating),
                                DataItem("objective", self.objective),
                                DataItem("position a-Si:H/cm^-1", self.position_a_si),
                                DataItem("position muc-Si:H/cm^-1", self.position_muc_si),
                                DataItem("width a-Si:H/cm^-1", self.width_a_si),
                                DataItem("width muc-Si:H/cm^-1", self.width_muc_si),
                                DataItem("setup", self.setup),
                                DataItem("detector", self.detector),
                                DataItem("measured through substrate", self.through_substrate),
                                DataItem("sampling distance x", self.sampling_distance_x),
                                DataItem("sampling distance y", self.sampling_distance_y),
                                DataItem("number of points x", self.number_points_x),
                                DataItem("number of points y", self.number_points_y),
                                DataItem("sampling period", self.sampling_period)])
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data` for the documentation.
        _ = ugettext
        data_node = super(RamanMeasurement, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("number"), self.number),
                                DataItem(_("kind"), self.get_kind_display()),
                                DataItem(_("data file"), self.datafile),
                                DataItem(_("evaluated data file"), self.evaluated_datafile),
                                DataItem(_("λ (central)") + "/nm", self.central_wavelength),
                                DataItem(_("λ (excitation)") + "/nm", self.get_excitation_wavelength_display()),
                                DataItem(_("slit") + "/μm", self.slit),
                                DataItem(_("accumulation"), self.accumulation),
                                DataItem(_("measurement time") + "/s", self.time),
                                DataItem(_("laser power") + "/mW", self.laser_power),
                                DataItem(_("filters"), self.filters),
                                DataItem("IcRS/%", self.icrs),
                                DataItem(_("grating"), self.grating),
                                DataItem(_("objective"), self.objective),
                                DataItem(_("position {peak}").format(peak="a-Si:H/cm⁻¹"), self.position_a_si),
                                DataItem(_("position {peak}").format(peak="µc-Si:H/cm⁻¹"), self.position_muc_si),
                                DataItem(_("width {peak}").format(peak="a-Si:H/cm⁻¹"), self.width_a_si),
                                DataItem(_("width {peak}").format(peak="µc-Si:H/cm⁻¹"), self.width_muc_si),
                                DataItem(_("setup"), self.get_setup_display()),
                                DataItem(_("detector"), self.get_detector_display()),
                                DataItem(_("measured through substrate"), self.through_substrate),
                                DataItem(_("sampling distance {direction}").format(direction="x"),
                                         self.sampling_distance_x),
                                DataItem(_("sampling distance {direction}").format(direction="y"),
                                         self.sampling_distance_y),
                                DataItem(_("number of points {direction}").format(direction="x"), self.number_points_x),
                                DataItem(_("number of points {direction}").format(direction="y"), self.number_points_y),
                                DataItem(_("sampling period"), self.sampling_period)])
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        if cls != RamanMeasurement:
            # So that derived classes don't get included into the searchable
            # models in the advanced search
            raise NotImplementedError
        search_fields = [search.TextSearchField(cls, "operator", "username"),
                         search.TextSearchField(cls, "external_operator", "name")]
        search_fields.extend(
            search.convert_fields_to_search_fields(cls, ["timestamp_inaccuracy", "cache_keys", "last_modified"]))
        related_models = {Sample: "samples"}
        return search.AbstractSearchTreeNode(
            Process, related_models, search_fields, [RamanMeasurementOne, RamanMeasurementTwo, RamanMeasurementThree],
            _("apparatus"))

register_abstract_model(RamanMeasurement)


class RamanMeasurementOne(RamanMeasurement):

    class Meta(RamanMeasurement.Meta):
        verbose_name = format_lazy(_("Raman {apparatus_number} measurement"), apparatus_number=1)
        verbose_name_plural = format_lazy(_("Raman {apparatus_number} measurements"), apparatus_number=1)
        _ = lambda x: x
        permissions = (("add_raman_measurement_one", _("Can add Raman 1 measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_raman_measurement_one", _("Can edit perms for Raman 1 measurements")),
                       ("view_every_raman_measurement_one", _("Can view all Raman 1 measurements")),
                       ("edit_every_raman_measurement_one", _("Can edit all Raman 1 measurements")))

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_raman_measurement", kwargs={"apparatus_number": 1})


class RamanMeasurementTwo(RamanMeasurement):

    class Meta(RamanMeasurement.Meta):
        verbose_name = format_lazy(_("Raman {apparatus_number} measurement"), apparatus_number=2)
        verbose_name_plural = format_lazy(_("Raman {apparatus_number} measurements"), apparatus_number=2)
        _ = lambda x: x
        permissions = (("add_raman_measurement_two", _("Can add Raman 2 measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_raman_measurement_two", _("Can edit perms for Raman 2 measurements")),
                       ("view_every_raman_measurement_two", _("Can view all Raman 2 measurements")),
                       ("edit_every_raman_measurement_two", _("Can edit all Raman 2 measurements")))

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_raman_measurement", kwargs={"apparatus_number": 2})


class RamanMeasurementThree(RamanMeasurement):

    class Meta(RamanMeasurement.Meta):
        verbose_name = format_lazy(_("Raman {apparatus_number} measurement"), apparatus_number=3)
        verbose_name_plural = format_lazy(_("Raman {apparatus_number} measurements"), apparatus_number=3)
        _ = lambda x: x
        permissions = (("add_raman_measurement_three", _("Can add Raman 3 measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_raman_measurement_three", _("Can edit perms for Raman 3 measurements")),
                       ("view_every_raman_measurement_three", _("Can view all Raman 3 measurements")),
                       ("edit_every_raman_measurement_three", _("Can edit all Raman 3 measurements")))

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_raman_measurement", kwargs={"apparatus_number": 3})


class ManualEtching(PhysicalProcess):

    """Model for the manual etching process.
    """
    number = models.CharField(_("etching number"), max_length=15, unique=True, db_index=True)
    acid_label_field = models.CharField(_("acid"), max_length=30)
    acid_value_field = models.DecimalField(_("acid concentration"), max_digits=4, decimal_places=1, help_text=_("in %"))
    temperature = models.IntegerField(_("temperature"), help_text=_("in ℃"))
    time = models.IntegerField(_("etching time"), help_text=_("in seconds"))
    resistance_before = models.DecimalField(_("surface resistance before etching"), max_digits=4, decimal_places=1,
                                            help_text=_("in Ω"), blank=True, null=True)
    resistance_after = models.DecimalField(_("surface resistance after etching"), max_digits=4, decimal_places=1,
                                           help_text=_("in Ω"), blank=True, null=True)
    thickness_before = models.PositiveIntegerField(_("layer thickness before etching"), help_text=_("in nm"),
                                                   blank=True, null=True)
    thickness_after = models.PositiveIntegerField(_("layer thickness after etching"), help_text=_("in nm"),
                                                  blank=True, null=True)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("manual etching")
        verbose_name_plural = _("manual etchings")
        _ = lambda x: x
        permissions = (("add_manual_etching", _("Can add manual etchings")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_manual_etching", _("Can edit perms for manual etchings")),
                       ("view_every_manual_etching", _("Can view all manual etchings")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("manual etching of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("manual etching #{number}").format(number=self.number)

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_manual_etching", kwargs={"etching_number": self.number})
        else:
            context["edit_url"] = None
        return super(ManualEtching, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_manual_etching")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(ManualEtching, self).get_data()
        data_node.items.extend([DataItem("acid/%", "{0} {1}".format(self.acid_label_field, self.acid_value_field)),
                                DataItem("temperature/degC", self.temperature),
                                DataItem("etching time/s", self.time),
                                DataItem("surface resistance b./Ohm", self.resistance_before),
                                DataItem("surface resistance a./Ohm", self.resistance_after),
                                DataItem("layer thickness b./nm", self.thickness_before),
                                DataItem("layer thickness a./nm", self.thickness_after)])
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(ManualEtching, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("acid") + "/%", "{0} {1}".format(self.acid_label_field,
                                                                               self.acid_value_field)),
                                DataItem(_("temperature") + "/℃", self.temperature),
                                DataItem(_("etching time") + "/s", self.time),
                                DataItem(_("surface resistance b.") + "/Ω", self.resistance_before),
                                DataItem(_("surface resistance a.") + "/Ω", self.resistance_after),
                                DataItem(_("layer thickness b.") + "/nm", self.thickness_before),
                                DataItem(_("layer thickness a.") + "/nm", self.thickness_after)])
        return data_node


sample_size_choices = (
        ("10x10", "10×10"),
        ("30x30", "30×30"),
        ("40x40", "40×40"))

class ThroughputEtching(PhysicalProcess):
    """Model for the throughput etching process.
    """
    number = models.CharField(_("etching number"), max_length=15, unique=True, db_index=True)
    acid_label_field = models.CharField(_("acid"), max_length=30)
    acid_value_field = models.DecimalField(_("acid concentration"), max_digits=4, decimal_places=1, help_text=_("in %"))
    temperature = models.IntegerField(_("temperature"), help_text=_("in ℃"))
    resistance_before = models.DecimalField(_("surface resistance before etching"), max_digits=4, decimal_places=1,
                                            help_text=_("in Ω"), blank=True, null=True)
    resistance_after = models.DecimalField(_("surface resistance after etching"), max_digits=4, decimal_places=1,
                                           help_text=_("in Ω"), blank=True, null=True)
    thickness_before = models.PositiveIntegerField(_("layer thickness before etching"), help_text=_("in nm"),
                                                   blank=True, null=True)
    thickness_after = models.PositiveIntegerField(_("layer thickness after etching"), help_text=_("in nm"),
                                                   blank=True, null=True)
    speed = models.DecimalField(_("throughput speed"), max_digits=2, decimal_places=1, help_text=_("in m/min"))
    voltage = models.DecimalField(_("voltage indicated"), max_digits=3, decimal_places=1, help_text=_("in V"))
    sample_size = models.CharField(_("sample size"), max_length=10, choices=sample_size_choices, blank=True,
                                   help_text=_("in cm²"))

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("throughput etching")
        verbose_name_plural = _("throughput etchings")
        _ = lambda x: x
        permissions = (("add_throughput_etching", _("Can add throughput etchings")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_throughput_etching", _("Can edit perms for throughput etchings")),
                       ("view_every_throughput_etching", _("Can view all throughput etchings")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("throughput etching plant process of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("throughput etching plant process #{number}").format(number=self.number)

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_throughput_etching", kwargs={"etching_number": self.number})
        else:
            context["edit_url"] = None
        return super(ThroughputEtching, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_throughput_etching")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(ThroughputEtching, self).get_data()
        data_node.items.extend([DataItem("acid/%", "{0} {1}".format(self.acid_label_field, self.acid_value_field)),
                                DataItem("temperature/degC", self.temperature),
                                DataItem("surface resistance b./Ohm", self.resistance_before),
                                DataItem("surface resistance a./Ohm", self.resistance_after),
                                DataItem("layer thickness b./nm", self.thickness_before),
                                DataItem("layer thickness a./nm", self.thickness_after),
                                DataItem("throughput speed/ m/min", self.speed),
                                DataItem("voltage indicated/V", self.voltage),
                                DataItem("sample size/cm^2", self.sample_size)])
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(ThroughputEtching, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("acid") + "/%", "{0} {1}".format(self.acid_label_field, self.acid_value_field)),
                                DataItem(_("temperature") + "/℃", self.temperature),
                                DataItem(_("surface resistance b.") + "/Ω", self.resistance_before),
                                DataItem(_("surface resistance a.") + "/Ω", self.resistance_after),
                                DataItem(_("layer thickness b.") + "/nm", self.thickness_before),
                                DataItem(_("layer thickness a.") + "/nm", self.thickness_after),
                                DataItem(_("throughput speed") + "/ m/min", self.speed),
                                DataItem(_("voltage indicated") + "/V", self.voltage),
                                DataItem(_("sample size") + "/cm²", self.get_sample_size_display())])
        return data_node


dsr_irradiance_choices = (
        ("white", _("white")),
        ("IF450nm", "IF450nm"),
        ("RG695", "RG695"))

class DSRMeasurement(PhysicalProcess):
    """Model for the DSR (Quantum Efficiency) Measurement.
    """
    cell_position = models.CharField(_("cell position"), max_length=5, blank=True)
    lens = models.BooleanField(_("lens"), default=False)
    bias = models.CharField(_("bias light"), max_length=50, blank=True)
    irradiance = models.CharField(_("irradiance"), max_length=10, choices=dsr_irradiance_choices, blank=True)
    parameter_file = models.CharField(_("measurement parameter file"), max_length=200, unique=True,
                                   help_text=(_("only the relative path below \"Messwerte/\"")))


    class Meta(PhysicalProcess.Meta):
        verbose_name = _("DSR measurement")
        verbose_name_plural = _("DSR measurements")
        _ = lambda x: x
        permissions = (("add_dsr_measurement", _("Can add DSR measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_dsr_measurement", _("Can edit perms for DSR measurements")),
                       ("view_every_dsr_measurement", _("Can view all DSR measurements")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("DSR measurement of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("DSR measurement")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_dsr_measurement", kwargs={"process_id": self.pk})
        else:
            context["edit_url"] = None
        if "iv_data_list" not in context:
            try:
                context["iv_data_list"] = self.iv_data_files.all()
            except DSRIVData.DoesNotExist:
                pass
        if "spectral_data_list" not in context:
            try:
                context["spectral_data_list"] = self.spectral_data_files.all()
            except DSRSpectralData.DoesNotExist:
                pass
        if "image_urls" not in context:
            context["image_urls"] = {}
            plot_locations = self.calculate_plot_locations(plot_id="iv")
            context["image_urls"]["iv_plot"] = (plot_locations["thumbnail_url"], plot_locations["plot_url"])
            plot_locations = self.calculate_plot_locations(plot_id="spectral")
            context["image_urls"]["spectral_plot"] = (plot_locations["thumbnail_url"], plot_locations["plot_url"])

        return super(DSRMeasurement, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_dsr_measurement")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(DSRMeasurement, self).get_data()
        data_node.items.extend([DataItem("cell_position", self.cell_position),
                                DataItem("lens", self.lens),
                                DataItem("irradiance", self.irradiance),
                                DataItem("parameter_file", self.parameter_file)])
        data_node.children = [iv_data_file.get_data() for iv_data_file in self.iv_data_files.all()]
        data_node.children.extend([spectral_data_file.get_data() for spectral_data_file in self.spectral_data_files.all()])
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(DSRMeasurement, self).get_data_for_table_export()
        data_node.items.extend([DataItem("cell_position", self.cell_position),
                                DataItem("lens", self.lens),
                                DataItem("irradiance", self.get_irradiance_display()),
                                DataItem("parameter_file", self.parameter_file)])
        data_node.children = [iv_data_file.get_data_for_table_export() for iv_data_file in self.iv_data_files.all()]
        data_node.children.extend([spectral_data_file.get_data_for_table_export()
                                   for spectral_data_file in self.spectral_data_files.all()])
        return data_node

    def draw_plot(self, axes, plot_id, filenames, for_thumbnail):
        _ = ugettext
        if for_thumbnail:
            axes.set_position((0.2, 0.15, 0.6, 0.8))
        for filename in filenames:
            if plot_id == "iv":
                x_values, y_values = institute_utils.read_dsr_plot_file(filename, columns=(0, 1))
                axes.semilogy(x_values, y_values)
            elif plot_id == "spectral":
                x_values, y_values = institute_utils.read_dsr_plot_file(filename, columns=(0, 8))
                x_values = numpy.array(x_values)
                y_values = 1239 * numpy.array(y_values) / x_values
            axes.plot(x_values, y_values, label=filename[filename.rfind(".") + 1:])
        axes.legend()
        axes.axvline(color="black", x=0, zorder=0, linestyle="-")
        axes.axhline(color="black", y=0, zorder=0, linestyle="-")
        fontsize = 12
        if plot_id == "iv":
            axes.set_xlabel(_("voltage in V"), fontsize=fontsize)
            axes.set_ylabel(_("current density in A"), fontsize=fontsize)
        elif plot_id == "spectral":
            axes.set_xlabel(_("wavelength in nm"), fontsize=fontsize)
            axes.set_ylabel(_("quantum efficiency in (A/W)/nm"), fontsize=fontsize)

    def get_datafile_name(self, plot_id):
        data_files = []
        if plot_id == "iv":
            try:
                data_files.extend([iv_data.iv_data_file for iv_data in self.iv_data_files.iterator()])
            except DSRIVData.DoesNotExist:
                pass
        elif plot_id == "spectral":
            try:
                data_files.extend(
                    [spectral_data.spectral_data_file for spectral_data in self.spectral_data_files.iterator()])
            except DSRSpectralData.DoesNotExist:
                pass
        return [os.path.join(settings.DSR_ROOT_DIR, data_file) for data_file in data_files]

    def get_plotfile_basename(self, plot_id):
        return "{plot_id}_data_of_cell_{position}".format(plot_id=plot_id, position=self.cell_position)


class DSRIVData(models.Model):
    measurement = models.ForeignKey(DSRMeasurement, related_name="iv_data_files",
                                    verbose_name=_("IV data"))
    iv_data_file = models.CharField(_("IV data file"), max_length=200, db_index=True,
                                    help_text=(_("only the relative path below \"Messwerte/\"")))

    class Meta:
        verbose_name = _("DSR measurement IV data")
        verbose_name_plural = _("DSR measurement IV data")

    def __unicode__(self):
        _ = ugettext
        try:
            return _("DSR measurement IV data of {sample}").format(sample=self.measurement.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("DSR measurement IV data")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = DataNode("iv data")
        data_node.items = [DataItem("iv_data_file", self.iv_data_file)]
        return data_node

    def get_data_for_table_export(self):
        data_node = DataNode("iv data")
        data_node.items = [DataItem("iv_data_file", self.iv_data_file)]
        return data_node

class DSRSpectralData(models.Model):
    measurement = models.ForeignKey(DSRMeasurement, related_name="spectral_data_files",
                                    verbose_name=_("spectral data"))
    spectral_data_file = models.CharField(_("spectral data file"), max_length=200, db_index=True,
                                help_text=(_("only the relative path below \"Messwerte/\"")))

    class Meta:
        verbose_name = _("DSR measurement spectral data")
        verbose_name_plural = _("DSR measurement spectral data")

    def __unicode__(self):
        _ = ugettext
        try:
            return _("DSR measurement spectral data of {sample}").format(sample=self.measurement.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("DSR measurement spectral data")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = DataNode("spectral data")
        data_node.items = [DataItem("spectral_data_file", self.spectral_data_file)]
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data` for the documentation.
        data_node = DataNode("spectral data")
        data_node.items = [DataItem("spectral_data_file", self.spectral_data_file)]
        return data_node

class IRMeasurement(PhysicalProcess):
    """Database model for the IR measurements.
    """
    number = models.PositiveIntegerField(_("IR number"), unique=True, db_index=True)
    spa_datafile = models.CharField(_("SPA data file"), max_length=200)
    csv_datafile = models.CharField(_("CSV data file"), max_length=200)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("IR measurement")
        verbose_name_plural = _("IR measurements")
        _ = lambda x: x
        permissions = (("add_ir_measurement", _("Can add IR measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_ir_measurement", _("Can edit perms for IR measurements")),
                       ("view_every_ir_measurement", _("Can view all IR measurements")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("IR measurement of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("IR measurement #{number}").format(number=self.number)

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_ir_measurement", kwargs={"ir_number": self.number})
        else:
            context["edit_url"] = None
        return super(IRMeasurement, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_ir_measurement")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(IRMeasurement, self).get_data()
        data_node.items.append(DataItem("SPA data file", self.spa_datafile))
        data_node.items.append(DataItem("CSV data file", self.csv_datafile))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(IRMeasurement, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("SPA data file"), self.spa_datafile))
        data_node.items.append(DataItem(_("CSV data file"), self.csv_datafile))
        return data_node


class SmallEvaporation(PhysicalProcess):
    """Database model for the small evaporation plant process.
    """
    number = models.CharField(_("evaporation number"), max_length=15, unique=True, db_index=True)
    pressure = models.DecimalField(_("pressure"), max_digits=5, decimal_places=1, help_text=_("in mbar"))
    thickness = models.PositiveIntegerField(_("layer thickness"), help_text=_("in nm"))

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("small evaporation")
        verbose_name_plural = _("small evaporations")
        _ = lambda x: x
        permissions = (("add_small_evaporation", _("Can add small evaporations")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_small_evaporation", _("Can edit perms for small evaporations")),
                       ("view_every_small_evaporation", _("Can view all small evaporations")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("evaporation of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("evaporation #{number}").format(number=self.number)

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_small_evaporation", kwargs={"process_number": self.number})
        else:
            context["edit_url"] = None
        return super(SmallEvaporation, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_small_evaporation")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(SmallEvaporation, self).get_data()
        data_node.items.append(DataItem("pressure/mbar", self.pressure))
        data_node.items.append(DataItem("layer thickness/nm", self.thickness))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(SmallEvaporation, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("pressure") + "/mbar", self.pressure))
        data_node.items.append(DataItem(_("layer thickness") + "/nm", self.thickness))
        return data_node


class LargeEvaporation(PhysicalProcess):
    """Database model for the large evaporation plant process.
    """
    number = models.CharField(_("evaporation number"), max_length=15, unique=True, db_index=True)
    pressure = models.DecimalField(_("pressure"), max_digits=5, decimal_places=1, help_text=_("in mbar"))
    thickness = models.PositiveIntegerField(_("layer thickness"), help_text=_("in nm"))
    material = models.CharField(_("evaporation material"), max_length=30)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("large evaporation")
        verbose_name_plural = _("large evaporations")
        _ = lambda x: x
        permissions = (("add_large_evaporation", _("Can add large evaporations")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_large_evaporation", _("Can edit perms for large evaporations")),
                       ("view_every_large_evaporation", _("Can view all large evaporations")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("evaporation of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("evaporation #{number}").format(number=self.number)

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_large_evaporation", kwargs={"process_number": self.number})
        else:
            context["edit_url"] = None
        return super(LargeEvaporation, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_large_evaporation")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(LargeEvaporation, self).get_data()
        data_node.items.extend([DataItem("pressure/mbar", self.pressure),
                                DataItem("layer thickness/nm", self.thickness),
                                DataItem("evaporation material", self.material)])
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LargeEvaporation, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("pressure") + "/mbar", self.pressure),
                                DataItem(_("layer thickness") + "/nm", self.thickness),
                                DataItem(_("evaporation material"), self.material)])
        return data_node


unit_choices = (("nm", "nm"),
              ("Å", "Å"),
              ("µm", "µm"))

methode_choices = (("profilers&edge", _("profilometer + edge")),
                 ("ellipsometer", _("ellipsometer")),
                 ("calculated", _("calculated from deposition parameters")),
                 ("estimate", _("estimate")),
                 ("other", _("other")))

class LayerThicknessMeasurement(PhysicalProcess):
    """Database model for the layer thickness measurement.

    Note that it doesn't define permissions because everyone can create
    substrates.
    """
    thickness = models.FloatField(_("layer thickness"), validators=[MinValueValidator(0)],
                                    help_text=_("in nm"))
    unit = models.CharField(_("unit"), max_length=3, choices=unit_choices, default="nm")
    method = models.CharField(_("measurement method"), max_length=30, choices=methode_choices, default="profilers&edge")
    uncertainty = models.DecimalField(_("uncertainty"), max_digits=5, decimal_places=2, blank=True, null=True,
                                      help_text=_("in %"), validators=[MinValueValidator(0)])

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("layer thickness measurement")
        verbose_name_plural = _("layer thickness measurements")

    def __unicode__(self):
        _ = ugettext
        try:
            return _("layer thickness of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("layer thickness #{number}").format(number=self.id)

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_layer_thickness", kwargs={"process_id": self.id})
        else:
            context["edit_url"] = None
        return super(LayerThicknessMeasurement, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_layer_thickness")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(LayerThicknessMeasurement, self).get_data()
        data_node.items.extend([DataItem("layer thickness", self.convert_thickness(self.thickness, "nm", self.unit)),
                                DataItem("unit", self.unit),
                                DataItem("measurement method", self.method),
                                DataItem("uncertainty", self.uncertainty)])
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LayerThicknessMeasurement, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("layer thickness"), self.convert_thickness(self.thickness, "nm", self.unit)),
                                DataItem(_("unit"), self.get_unit_display()),
                                DataItem(_("measurement method"), self.get_method_display()),
                                DataItem(_("uncertainty"), self.uncertainty)])
        return data_node

    @classmethod
    def convert_thickness(cls, value, from_unit, to_unit):
        factor = {"nm": {"Å": 10, "µm": 0.001, "nm" : 1},
                  "Å": {"nm": 0.1, "µm": 0.0001, "Å": 1},
                  "µm": {"nm": 1000, "Å": 10000, "µm": 1}}
        try:
            return value * factor[from_unit][to_unit]
        except KeyError:
            raise KeyError("Unit {0} not supported".format(sys.exc_value))


class SputterCharacterization(PhysicalProcess):
    """Database model for the post-sputtering sputter characterisation.
    """
    thickness = models.IntegerField(_("layer thickness"), blank=True, null=True, help_text=_("in nm"))
    r_square = models.FloatField("R<sub>□</sub>", blank=True, null=True, help_text=_("in Ω"))
    deposition_rate = models.DecimalField(_("deposition rate"), max_digits=4, decimal_places=1, blank=True, null=True,
                                          help_text=_("in nm/min or nm·m/min"))
    rho = models.FloatField("&#x3c1;", blank=True, null=True, help_text=_("in Ω cm"))
    large_sputter_deposition = models.ForeignKey("LargeSputterDeposition", related_name="sputter_characterizations",
                                                 null=True, blank=True, verbose_name=_("large sputter deposition"))
    new_cluster_tool_deposition = models.ForeignKey("NewClusterToolDeposition", related_name="sputter_characterizations",
                                                    null=True, blank=True, verbose_name=_("cluster tool II deposition"))

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("sputter characterization")
        verbose_name_plural = _("sputter characterizations")
        _ = lambda x: x
        permissions = (("add_sputter_characterization", _("Can add sputter characterizations")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_sputter_characterization", _("Can edit perms for sputter characterizations")),
                       ("view_every_sputter_characterization", _("Can view all sputter characterizations")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("sputter characterization of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("sputter characterization #{number}").format(number=self.id)

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_sputter_characterization", kwargs={"process_id": self.id})
        else:
            context["edit_url"] = None
        return super(SputterCharacterization, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_sputter_characterization")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(SputterCharacterization, self).get_data()
        data_node.items.extend([DataItem("layer thickness/nm", self.thickness),
                                DataItem("r_square/ohm", self.r_square),
                                DataItem("deposition rate/ nm/min", self.deposition_rate),
                                DataItem("rho/ ohm cm", self.rho),
                                DataItem("cluster tool II deposition", self.new_cluster_tool_deposition.number),
                                DataItem("large sputter deposition", self.large_sputter_deposition.number)])
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(SputterCharacterization, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("layer thickness") + "/nm", self.thickness),
                                DataItem("R_□/Ω", self.r_square),
                                DataItem(_("deposition rate") + "/ nm/min", self.deposition_rate),
                                DataItem("ρ/ Ω cm", self.rho),
                                DataItem(_("cluster tool II deposition"), self.new_cluster_tool_deposition),
                                DataItem(_("large sputter deposition"), self.large_sputter_deposition)])
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


class SolarsimulatorDarkMeasurement(PhysicalProcess):
    irradiance = models.CharField(_("irradiance"), max_length=10, default="dark")
    temperature = models.DecimalField(_("temperature"), max_digits=3, decimal_places=1, help_text=_("in ℃"),
                                      default=25.0)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("solarsimulator dark measurement")
        verbose_name_plural = _("solarsimulator dark measurements")
        _ = lambda x: x
        permissions = (("add_solarsimulator_dark_measurement", _("Can add dark measurements")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_solarsimulator_dark_measurement",
                        _("Can edit perms for dark measurements")),
                       ("view_every_solarsimulator_dark_measurement", _("Can view all dark measurements")))

    def __unicode__(self):
        _ = ugettext
        try:
            return _("solarsimulator dark measurement of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("solarsimulator dark measurement")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_solarsimulator_dark_measurement", kwargs={"process_id": self.id})
        else:
            context["edit_url"] = None
        sample = self.samples.get()
        if "shapes" not in context:
            layout = layouts.get_layout(sample, self)
            context["shapes"] = layout.get_map_shapes() if layout else {}
        context["thumbnail_layout"] = django.core.urlresolvers.reverse(
            "chantal_institute.views.samples.layout.show_layout", kwargs={"sample_id": sample.id, "process_id": self.id})
        if "cells" not in context:
            context["cells"] = self.dark_cells.all()
        if "image_urls" not in context:
            context["image_urls"] = {}
            for cell in context["cells"]:
                plot_locations = self.calculate_plot_locations(plot_id=cell.position)
                _thumbnail, _figure = plot_locations["thumbnail_url"], plot_locations["plot_url"]
                context["image_urls"][cell.position] = (_thumbnail, _figure)
        if "default_cell" not in context:
            default_cell = sorted(context["image_urls"])[0]
            context["default_cell"] = (default_cell,) + context["image_urls"][default_cell]
        return super(SolarsimulatorDarkMeasurement, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_solarsimulator_dark_measurement")

    def get_data(self):
        data_node = super(SolarsimulatorDarkMeasurement, self).get_data()
        data_node.items.extend([DataItem("irradiance", self.irradiance),
                                DataItem("temperature/degC", self.temperature), ])
        data_node.children = [dark_cell.get_data() for dark_cell in self.dark_cells.all()]
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(SolarsimulatorDarkMeasurement, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("irradiance"), self.irradiance),
                                DataItem(_("temperature") + "/℃", self.temperature)])
        return data_node

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        _ = ugettext
        related_cell = self.dark_cells.get(position=plot_id)
        x_values, y_values = institute_utils.read_solarsimulator_plot_file(filename, columns=(0, int(related_cell.cell_index)))
        y_values = 1000 * numpy.array(y_values)
        if for_thumbnail:
            axes.set_position((0.2, 0.15, 0.6, 0.8))
        axes.semilogy(x_values, numpy.abs(y_values))
        if for_thumbnail:
            x_min, x_max = axes.get_xlim()
            ticks = list(numpy.arange(0, x_min - 1e-6, -0.4))
            ticks.reverse()
            ticks += list(numpy.arange(0, x_max + 1e-6, 0.4))
            axes.set_xticks(ticks)
        axes.axvline(color="black", x=0, zorder=0, linestyle="-")
        axes.axhline(color="black", y=0, zorder=0, linestyle="-")
        fontsize = 12
        axes.set_xlabel(_("voltage in V"), fontsize=fontsize)
        axes.set_ylabel(_("current in mA"), fontsize=fontsize)

    def get_datafile_name(self, plot_id):
        try:
            related_cell = self.dark_cells.get(position=plot_id)
        except SolarsimulatorDarkCellMeasurement.DoesNotExist:
            return None
        return os.path.join(settings.SOLARSIMULATOR_1_ROOT_DIR, related_cell.data_file)

    def get_plotfile_basename(self, plot_id):
        try:
            related_cell = self.dark_cells.get(position=plot_id)
        except SolarsimulatorDarkCellMeasurement.DoesNotExist:
            return None
        return "{filename}_{position}".format(filename=related_cell.data_file, position=related_cell.position)


class SolarsimulatorDarkCellMeasurement(SolarsimulatorCell):
    measurement = models.ForeignKey(SolarsimulatorDarkMeasurement, related_name="dark_cells",
                                    verbose_name=_("solarsimulator dark measurement"))
    n_diode = models.FloatField(_("diode factor n"), null=True, blank=True)
    i_0 = models.FloatField(_("saturation current I₀"), help_text=_("in mA/cm²"), null=True, blank=True)

    class Meta:
        verbose_name = _("solarsimulator dark cell measurement")
        verbose_name_plural = _("solarsimulator dark cell measurements")
        unique_together = (("measurement", "position"), ("cell_index", "data_file"), ("position", "data_file"))

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(SolarsimulatorDarkCellMeasurement, self).get_data()
        data_node.items.extend([DataItem("diode factor n", self.n_diode),
                                DataItem("I_0/(mA/cm^2)", self.i_0)])
        return data_node

    def get_data_for_table_export(self):
        return NotImplementedError


layout_choices = (("juelich standard", "Jülich standard"),
                  ("ACME 1", "ACME 1"),
                  ("ACME 2", "ACME 2"),
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


class FiveChamberEtching(PhysicalProcess):
    """Database model for the 5-chamber etching process.
    """
    number = models.CharField(_("5-chamber etching number"), max_length=15, unique=True, db_index=True)
    chamber = models.CharField(_("chamber"), max_length=2, choices=five_chamber_chamber_choices)
    nf3 = models.DecimalField("NF₃", max_digits=3, decimal_places=1, help_text=_("in sccm"), null=True, blank=True)
    power = models.DecimalField(_("power"), max_digits=5, decimal_places=1, help_text=_("in W"), null=True, blank=True)
    pressure = models.DecimalField(_("pressure"), max_digits=3, decimal_places=1, help_text=_("in Torr"), null=True,
                                   blank=True)
    temperature = models.DecimalField(_("temperature"), max_digits=4, decimal_places=1, help_text=_("in ℃"),
                                      null=True, blank=True)
    hf_frequency = models.DecimalField(_("HF frequency"), max_digits=5, decimal_places=2, null=True, blank=True,
                                       choices=five_chamber_hf_frequency_choices, help_text=_("in MHz"))
    time = models.IntegerField(_("time"), help_text=_("in sec"), null=True, blank=True)
    dc_bias = models.DecimalField(_("DC bias"), max_digits=3, decimal_places=1, help_text=_("in V"), null=True,
                                  blank=True)
    electrodes_distance = models.DecimalField(_("electrodes distance"), max_digits=4, decimal_places=1,
                                               help_text=_("in mm"), null=True, blank=True)

    class Meta(samples.models_depositions.Layer.Meta):
        verbose_name = _("5-chamber etching process")
        verbose_name_plural = _("5-chamber etching processes")

    def __unicode__(self):
        _ = ugettext
        try:
            return _("5-Chamber etching process of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            return _("5-Chamber etching process #{number}").format(number=self.id)

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = super(FiveChamberEtching, self).get_data()
        data_node.items.extend([DataItem("chamber", self.chamber),
                                DataItem("NF3/sccm", self.nf3),
                                DataItem("power/W", self.power),
                                DataItem("pressure/Torr", self.pressure),
                                DataItem("T/degC", self.temperature),
                                DataItem("f_HF/MHz", self.hf_frequency),
                                DataItem("time/s", self.time),
                                DataItem("DC bias/V", self.dc_bias),
                                DataItem("elec. dist./mm", self.electrodes_distance), ])
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(FiveChamberEtching, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("chamber"), self.get_chamber_display()),
                                DataItem("NF₃/sccm", self.nf3),
                                DataItem(_("power") + "/W", self.power),
                                DataItem(_("pressure") + "/Torr", self.pressure),
                                DataItem(_("temperature") + "/℃", self.temperature),
                                DataItem(_("HF frequency") + "/MHz", self.hf_frequency),
                                DataItem(_("time") + "/s", self.time),
                                DataItem(_("DC bias") + "/V", self.dc_bias),
                                DataItem(_("elec. dist.") + "/mm", self.electrodes_distance), ])
        return data_node
