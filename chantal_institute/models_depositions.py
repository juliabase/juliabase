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


"""Models for IEF-5-specific depositions.  This includes the deposition models
themselves as well as models for layers.  Additionally, there are miscellaneous
models like the one to 6-chamber deposition channels.
"""

from __future__ import absolute_import, unicode_literals

import re
from decimal import Decimal
from django.utils.translation import ugettext_lazy as _, ugettext, pgettext_lazy
import django.core.urlresolvers
from django.utils.http import urlquote, urlquote_plus
from django.db import models
import samples.models_depositions
from samples import permissions
from samples.data_tree import DataNode, DataItem
from chantal_common import search
from chantal_common import models as chantal_common_models
from django.utils.translation import string_concat
from django.contrib.auth.models import User
from chantal_common.utils import get_really_full_name


class SixChamberDeposition(samples.models_depositions.Deposition):
    """6-chamber depositions.
    """
        # Translators: Of a deposition system
    carrier = models.CharField(_("carrier"), max_length=10, blank=True)

    class Meta(samples.models_depositions.Deposition.Meta):
        verbose_name = _("6-chamber deposition")
        verbose_name_plural = _("6-chamber depositions")
        _ = lambda x: x
        permissions = (("add_six_chamber_deposition", _("Can add 6-chamber depositions")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_six_chamber_deposition", _("Can edit perms for 6-chamber depositions")),
                       ("view_every_six_chamber_deposition", _("Can view all 6-chamber depositions")),
                       ("edit_every_six_chamber_deposition", _("Can edit all 6-chamber depositions")))

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.six_chamber_deposition.show", [urlquote(self.number, safe="")])

    @classmethod
    def get_add_link(cls):
        """Return the URL to the “add” view for this process.

        This method marks the current class as a so-called physical process.
        This implies that it also must have an “add-edit” permission.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_6-chamber_deposition")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_6-chamber_deposition", kwargs={"deposition_number": self.number})
        else:
            context["edit_url"] = None
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_6-chamber_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(SixChamberDeposition, self).get_context_for_user(user, context)

    @classmethod
    def get_lab_notebook_context(cls, year, month):
        # I only change ordering here.
        processes = cls.objects.filter(timestamp__year=year, timestamp__month=month).select_related()
        return {"processes": sorted(processes, key=lambda process: int(process.number.rpartition("-")[2]), reverse=True)}

    @classmethod
    def get_lab_notebook_data(cls, year, month):
        _ = ugettext
        depositions = cls.get_lab_notebook_context(year, month)["processes"]
        data = DataNode(_("lab notebook for {process_name}").format(process_name=cls._meta.verbose_name_plural))
        for deposition in depositions:
            for layer in deposition.layers.all():
                layer_data = layer.get_data_for_table_export()
                layer_data.descriptive_name = ""
                layer_data.items.insert(0, DataItem(_("deposition number"), deposition.number))
                data.children.append(layer_data)
        return data

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(SixChamberDeposition, self).get_data()
        data_node.items.append(DataItem("carrier", self.carrier))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(SixChamberDeposition, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("carrier"), self.carrier))
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        model_field = super(SixChamberDeposition, cls).get_search_tree_node()
        model_field.search_fields.append(search.BooleanSearchField(cls, "finished"))
        return model_field

samples.models_depositions.default_location_of_deposited_samples[SixChamberDeposition] = _("6-chamber deposition lab")


six_chamber_chamber_choices = (
    ("#1", "#1"),
    ("#2", "#2"),
    ("#3", "#3"),
    ("#4", "#4"),
    ("#5", "#5"),
    ("#6", "#6"))
"""Contains all possible choices for `SixChamberLayer.chamber`.
"""

class SixChamberLayer(samples.models_depositions.Layer):
    """One layer in a 6-chamber deposition.

    FixMe: Maybe ``SixChamberLayer.chamber`` should become optional, too?
    """
    deposition = models.ForeignKey(SixChamberDeposition, related_name="layers", verbose_name=_("deposition"))
    chamber = models.CharField(_("chamber"), max_length=5, choices=six_chamber_chamber_choices)
        # Translators: Physical unit is meant
    pressure = models.CharField(_("deposition pressure"), max_length=15, help_text=_("with unit"), blank=True)
    time = models.CharField(_("deposition time"), max_length=9, help_text=_("format HH:MM:SS"), blank=True)
    substrate_electrode_distance = \
        models.DecimalField(_("substrate–electrode distance"), null=True, blank=True, max_digits=4,
                            decimal_places=1, help_text=_("in mm"))
    comments = models.TextField(_("comments"), blank=True)
    transfer_in_chamber = models.CharField(_("transfer in the chamber"), max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField(_("pre-heat"), max_length=9, blank=True, help_text=_("format HH:MM:SS"))
    gas_pre_heat_gas = models.CharField(_("gas of gas pre-heat"), max_length=10, blank=True)
    gas_pre_heat_pressure = models.CharField(_("pressure of gas pre-heat"), max_length=15, blank=True,
                                             help_text=_("with unit"))
    gas_pre_heat_time = models.CharField(_("time of gas pre-heat"), max_length=15, blank=True,
                                         help_text=_("format HH:MM:SS"))
    heating_temperature = models.IntegerField(_("heating temperature"), help_text=_("in ℃"), null=True, blank=True)
    transfer_out_of_chamber = models.CharField(_("transfer out of the chamber"), max_length=10, default="Ar", blank=True)
    plasma_start_power = models.DecimalField(_("plasma start power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                             # Translators: Watt
                                             help_text=_("in W"))
    plasma_start_with_carrier = models.BooleanField(_("plasma start with carrier"), default=False)
    deposition_frequency = models.DecimalField(_("deposition frequency"), max_digits=5, decimal_places=2,
                                               null=True, blank=True, help_text=_("in MHz"))
    deposition_power = models.DecimalField(_("deposition power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text=_("in W"))
    base_pressure = models.FloatField(_("base pressure"), help_text=_("in Torr"), null=True, blank=True)

    class Meta(samples.models_depositions.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("6-chamber layer")
        verbose_name_plural = _("6-chamber layers")

    def __unicode__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = super(SixChamberLayer, self).get_data()
        data_node.items.extend([DataItem("chamber", self.chamber),
                                DataItem("p", self.pressure),
                                DataItem("time", self.time),
                                DataItem("electr. dist./mm", self.substrate_electrode_distance),
                                DataItem("transfer in the chamber", self.transfer_in_chamber),
                                DataItem("pre-heat", self.pre_heat),
                                DataItem("gas of gas pre-heat", self.gas_pre_heat_gas),
                                DataItem("pressure of gas pre-heat", self.gas_pre_heat_pressure),
                                DataItem("time of gas pre-heat", self.gas_pre_heat_time),
                                DataItem("T/degC", self.heating_temperature),
                                DataItem("transfer out of the chamber", self.transfer_out_of_chamber),
                                DataItem("P_start/W", self.plasma_start_power),
                                DataItem("plasma start with carrier", self.plasma_start_with_carrier),
                                DataItem("f/MHz", self.deposition_frequency),
                                DataItem("P/W", self.deposition_power),
                                DataItem("p_base/Torr", self.base_pressure),
                                DataItem("comments", self.comments)])
        data_node.children.extend(channel.get_data() for channel in self.channels.all())
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(SixChamberLayer, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("chamber"), self.get_chamber_display()),
                                DataItem("p", self.pressure),
                                DataItem(_("time"), self.time),
                                DataItem(_("electr. dist.") + "/mm", self.substrate_electrode_distance),
                                DataItem(_("transfer in the chamber"), self.transfer_in_chamber),
                                DataItem(_("pre-heat"), self.pre_heat),
                                DataItem(_("gas of gas pre-heat"), self.gas_pre_heat_gas),
                                DataItem(_("pressure of gas pre-heat"), self.gas_pre_heat_pressure),
                                DataItem(_("time of gas pre-heat"), self.gas_pre_heat_time),
                                DataItem("T/℃", self.heating_temperature),
                                DataItem(_("transfer out of the chamber"), self.transfer_out_of_chamber),
                                DataItem(_("P_start") + "/W", self.plasma_start_power),
                                DataItem(_("plasma start with carrier"),
                                         _("yes") if self.plasma_start_with_carrier else _("no")),
                                DataItem("f/MHz", self.deposition_frequency),
                                DataItem("P/W", self.deposition_power),
                                DataItem(_("p_base") + "/Torr", self.base_pressure),
                                DataItem(_("comments"), self.comments)])
        flow_rates = {}
        for channel in self.channels.all():
            flow_rates[channel.gas] = unicode(channel.flow_rate)
        gas_names = dict(six_chamber_gas_choices)
        for gas_name in gas_names:
            data_node.items.append(DataItem(unicode(gas_names[gas_name]) + " " + _("(in sccm)"),
                                            flow_rates.get(gas_name, "")))
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :Return:
          the tree node for this model instance

        :rtype: ``chantal_common.search.SearchTreeNode``
        """
        model_field = super(SixChamberLayer, cls).get_search_tree_node()
        model_field.related_models[SixChamberChannel] = "channels"
        return model_field


six_chamber_gas_choices = (
    ("SiH4", "SiH₄"),
    ("H2", "H₂"),
    ("PH3+SiH4", _("2% PH₃ in SiH₄")),
    ("TMB", _("1% TMB in He")),
    ("B2H6", _("5ppm B₂H₆ in H₂")),
    ("CH4", "CH₄"),
    ("CO2", "CO₂"),
    ("GeH4", "GeH₄"),
    ("Ar", "Ar"),
    ("Si2H6", "Si₂H₆"),
    ("PH3_10ppm", _("10 ppm PH₃ in H₂")),
    ("PH3_5pc", _("5% PH₃ in H₂"))
)
"""Contains all possible choices for `SixChamberChannel.gas`.
"""

class SixChamberChannel(models.Model):
    """One channel of a certain layer in a 6-chamber deposition.
    """
    number = models.PositiveIntegerField(_("channel"))
    layer = models.ForeignKey(SixChamberLayer, related_name="channels", verbose_name=_("layer"))
    gas = models.CharField(_("gas and dilution"), max_length=30, choices=six_chamber_gas_choices)
    flow_rate = models.DecimalField(_("flow rate"), max_digits=6, decimal_places=2, help_text=_("in sccm"))

    class Meta:
        verbose_name = _("6-chamber channel")
        verbose_name_plural = _("6-chamber channels")
        unique_together = ("layer", "number")
        ordering = ["number"]

    def __unicode__(self):
        _ = ugettext
        return _("channel {number} of {layer}").format(number=self.number, layer=self.layer)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = DataNode("channel {0}".format(self.number))
        data_node.items.append(DataItem("number", self.number))
        data_node.items.append(DataItem("gas", self.gas))
        data_node.items.append(DataItem("flow rate in sccm", self.flow_rate))
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :Return:
          the tree node for this model instance

        :rtype: ``chantal_common.search.SearchTreeNode``
        """
        search_fields = [search.IntegerSearchField(cls, "number"), search.ChoiceSearchField(cls, "gas"),
                         search.IntervalSearchField(cls, "flow_rate")]
        return search.SearchTreeNode(cls, {}, search_fields)


large_area_carrier_choices = (
    ("1", "1"),
    ("2", "2"),
)
large_area_substrate_size_choices = (
    ("10x10", "10×10 cm²"),
    ("30x30", "30×30 cm²"),
)
large_area_load_chamber_choices = (
    ("LL1", "LL1"),
    ("LL2", "LL2"),
)
large_area_sample_holder_choices = (
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
)

class LargeAreaDeposition(samples.models_depositions.Deposition):
    """Large-area depositions.
    """
        # Translators: Of a deposition system
    carrier = models.CharField(_("carrier"), max_length=2, choices=large_area_carrier_choices, blank=True)
    substrate_size = models.CharField(_("substrate size"), max_length=8, choices=large_area_substrate_size_choices,
                                      blank=True)
    load_chamber = models.CharField(_("load chamber"), max_length=4, choices=large_area_load_chamber_choices, blank=True)
    sample_holder = models.CharField(_("sample holder"), max_length=2, choices=large_area_sample_holder_choices, blank=True)

    class Meta(samples.models_depositions.Deposition.Meta):
        verbose_name = _("large-area deposition")
        verbose_name_plural = _("large-area depositions")
        _ = lambda x: x
        permissions = (("add_large_area_deposition", _("Can add large-area depositions")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_large_area_deposition", _("Can edit perms for large-area depositions")),
                       ("view_every_large_area_deposition", _("Can view all large-area depositions")),
                       ("edit_every_large_area_deposition", _("Can edit all large-area depositions")))

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.large_area_deposition.show", [urlquote(self.number, safe="")])

    @classmethod
    def get_add_link(cls):
        """Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_large-area_deposition")

    @classmethod
    def get_lab_notebook_data(cls, year, month):
        depositions = cls.get_lab_notebook_context(year, month)["processes"]
        data = DataNode(_("lab notebook for {process_name}").format(process_name=cls._meta.verbose_name_plural))
        for deposition in depositions:
            for layer in deposition.layers.all():
                data.children.append(layer.get_data_for_table_export())
                data.children[-1].descriptive_name = ""
        return data

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_large-area_deposition", kwargs={"deposition_number": self.number})
        else:
            context["edit_url"] = None
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_large-area_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(LargeAreaDeposition, self).get_context_for_user(user, context)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(LargeAreaDeposition, self).get_data()
        data_node.items.append(DataItem("carrier", self.carrier))
        data_node.items.append(DataItem("substrate size", self.substrate_size))
        data_node.items.append(DataItem("load chamber", self.load_chamber))
        data_node.items.append(DataItem("sample holder", self.sample_holder))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LargeAreaDeposition, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("carrier"), self.get_carrier_display()))
        data_node.items.append(DataItem(_("substrate size"), self.get_substrate_size_display()))
        data_node.items.append(DataItem(_("load chamber"), self.get_load_chamber_display()))
        data_node.items.append(DataItem(_("sample holder"), self.get_sample_holder_display()))
        return data_node

samples.models_depositions.default_location_of_deposited_samples[LargeAreaDeposition] = _("large-area deposition lab")


large_area_layer_type_choices = (
    ("p", "p"),
    ("i", "i"),
    ("n", "n"),
)
large_area_station_choices = (
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
)
large_area_hf_frequency_choices = (
    (Decimal("13.56"), "13.56"),
    (Decimal("27.12"), "27.12"),
    (Decimal("40.68"), "40.68"),
)
# FixMe: should this really be made translatable?
large_area_electrode_choices = (
    ("NN large PC1", _("NN large PC1")),
    ("NN large PC2", _("NN large PC2")),
    ("NN large PC3", _("NN large PC3")),
    ("NN small 1", _("NN small 1")),
    ("NN small 2", _("NN small 2")),
    ("NN40 large PC1", _("NN40 large PC1")),
    ("NN40 large PC2", _("NN40 large PC2")),
)

class LargeAreaLayer(samples.models_depositions.Layer):
    """One layer in a large-area deposition.

    *Important*: Numbers of large-area layers are the numbers after the “L-”
    because they must be ordinary integers!  This means that all layers of a
    deposition must be in the same calendar year, oh well …
    """
    deposition = models.ForeignKey(LargeAreaDeposition, related_name="layers", verbose_name=_("deposition"))
    date = models.DateField(_("date"))
    layer_type = models.CharField(_("layer type"), max_length=2, choices=large_area_layer_type_choices)
    station = models.CharField(_("station"), max_length=2, choices=large_area_station_choices)
    sih4 = models.DecimalField(_("SiH₄"), max_digits=5, decimal_places=2, help_text=_("in sccm"))
    sih4_end = models.DecimalField(_("SiH₄<sup>end</sup>"), max_digits=5, decimal_places=2, help_text=_("in sccm"),
                                   null=True, blank=True)
    h2 = models.DecimalField(_("H₂"), max_digits=5, decimal_places=1, help_text=_("in sccm"))
    h2_end = models.DecimalField(_("H₂<sup>end</sup>"), max_digits=5, decimal_places=1, help_text=_("in sccm"),
                                 null=True, blank=True)
    tmb = models.DecimalField("TMB", max_digits=5, decimal_places=2, help_text=_("in sccm"), null=True, blank=True)
    ch4 = models.DecimalField("CH₄", max_digits=3, decimal_places=1, help_text=_("in sccm"), null=True, blank=True)
    co2 = models.DecimalField("CO₂", max_digits=4, decimal_places=1, help_text=_("in sccm"), null=True, blank=True)
    ph3 = models.DecimalField("PH₃", max_digits=3, decimal_places=1, help_text=_("in sccm"), null=True, blank=True)
    power = models.DecimalField(_("power"), max_digits=5, decimal_places=1, help_text=_("in W"))
    pressure = models.DecimalField(_("pressure"), max_digits=3, decimal_places=1, help_text=_("in Torr"))
    temperature = models.DecimalField(_("temperature"), max_digits=4, decimal_places=1, help_text=_("in ℃"))
    hf_frequency = models.DecimalField(_("HF frequency"), max_digits=5, decimal_places=2,
                                       choices=large_area_hf_frequency_choices, help_text=_("in MHz"))
    time = models.IntegerField(_("time"), help_text=_("in sec"))
    dc_bias = models.DecimalField(_("DC bias"), max_digits=3, decimal_places=1, help_text=_("in V"), null=True, blank=True)
    electrode = models.CharField(_("electrode"), max_length=30, choices=large_area_electrode_choices)
    electrodes_distance = models.DecimalField(_("electrodes distance"), max_digits=4, decimal_places=1,
                                               help_text=_("in mm"))

    class Meta(samples.models_depositions.Layer.Meta):
        verbose_name = _("large-area layer")
        verbose_name_plural = _("large-area layers")

    def __unicode__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def calculate_sc(self, when):
        if when == "start":
            sih4 = self.sih4
            h2 = self.h2
        elif when == "end":
            if self.sih4_end is None and self.h2_end is None:
                return None
            sih4 = self.sih4_end if self.sih4_end is not None else self.sih4
            h2 = self.h2_end if self.h2_end is not None else self.h2
        sih4, h2 = float(sih4), float(h2)
        if sih4 == h2 == 0:
            return "NaN"
        else:
            return "{0:5.2f}".format(sih4 * 0.6 / (sih4 * 0.6 + h2) * 100)

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = super(LargeAreaLayer, self).get_data()
        data_node.items.extend([DataItem("date", self.date),
                                DataItem("layer type", self.layer_type),
                                DataItem("station", self.station),
                                DataItem("SiH4/sccm", self.sih4),
                                DataItem("SiH4_end/sccm", self.sih4_end),
                                DataItem("H2/sccm", self.h2),
                                DataItem("H2_end/sccm", self.h2_end),
                                DataItem("TMB/sccm", self.tmb),
                                DataItem("CH4/sccm", self.ch4),
                                DataItem("CO2/sccm", self.co2),
                                DataItem("PH3/sccm", self.ph3),
                                DataItem("SC/%", self.calculate_sc("start")),
                                DataItem("SC_end/%", self.calculate_sc("end")),
                                DataItem("P/W", self.power),
                                DataItem("p/Torr", self.pressure),
                                DataItem("T/degC", self.temperature),
                                DataItem("f_HF/MHz", self.hf_frequency),
                                DataItem("time/s", self.time),
                                DataItem("DC bias/V", self.dc_bias),
                                DataItem("electrode", self.electrode),
                                DataItem("electr. dist./mm", self.electrodes_distance)])
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LargeAreaLayer, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("date"), self.date),
                                DataItem(_("layer type"), self.get_layer_type_display()),
                                DataItem(_("station"), self.get_station_display()),
                                DataItem("SiH₄/sccm", self.sih4),
                                DataItem(_("SiH₄_end") + "/sccm", self.sih4_end),
                                DataItem("H₂/sccm", self.h2),
                                DataItem(_("H₂_end") + "/sccm", self.h2_end),
                                DataItem("TMB/sccm", self.tmb),
                                DataItem("CH₄/sccm", self.ch4),
                                DataItem("CO₂/sccm", self.co2),
                                DataItem("PH₃/sccm", self.ph3),
                                DataItem("SC/%", self.calculate_sc("start")),
                                DataItem(_("SC_end") + "/%", self.calculate_sc("end")),
                                DataItem("P/W", self.power),
                                DataItem("p/Torr", self.pressure),
                                DataItem("T/℃", self.temperature),
                                DataItem("f_HF/MHz", self.hf_frequency),
                                DataItem(_("time") + "/s", self.time),
                                DataItem(_("DC bias") + "/V", self.dc_bias),
                                DataItem(_("electrode"), self.get_electrode_display()),
                                DataItem(_("electr. dist.") + "/mm", self.electrodes_distance)])
        return data_node


cluster_tool_wire_material_choices = (
    ("unknown", _("unknown")),
    ("rhenium", _("rhenium")),
    ("tantalum", _("tantalum")),
    ("tungsten", _("tungsten")),
)

class ClusterToolHotWireLayer(models.Model):
    """Abstract Model for the hot-wire layers
    """
    pressure = models.DecimalField(_("deposition pressure"), max_digits=5, decimal_places=3, help_text=_("in mbar"),
                                   null=True, blank=True)
    time = models.CharField(_("deposition time"), max_length=9, help_text=_("format HH:MM:SS"), blank=True)
    substrate_wire_distance = models.DecimalField(_("substrate–wire distance"), null=True, blank=True, max_digits=4,
                                                  decimal_places=1, help_text=_("in mm"))
    comments = models.TextField(_("comments"), blank=True)
    transfer_in_chamber = models.CharField(_("transfer in the chamber"), max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField(_("pre-heat"), max_length=9, blank=True, help_text=_("format HH:MM:SS"))
    gas_pre_heat_gas = models.CharField(_("gas of gas pre-heat"), max_length=10, blank=True)
    gas_pre_heat_pressure = models.DecimalField(_("pressure of gas pre-heat"), max_digits=5, decimal_places=3,
                                                null=True, blank=True, help_text=_("in mbar"))
    gas_pre_heat_time = models.CharField(_("time of gas pre-heat"), max_length=15, blank=True,
                                         help_text=_("format HH:MM:SS"))
    heating_temperature = models.IntegerField(_("heating temperature"), help_text=_("in ℃"), null=True, blank=True)
    transfer_out_of_chamber = models.CharField(_("transfer out of the chamber"), max_length=10, default="Ar", blank=True)
    filament_temperature = models.DecimalField(_("filament temperature"), max_digits=5, decimal_places=1,
                                               null=True, blank=True, help_text=_("in ℃"))
    current = models.DecimalField(_("wire current"), max_digits=6, decimal_places=2, null=True, blank=True,
                                  # Translators: Ampère
                                  help_text=_("in A"))
    voltage = models.DecimalField(_("wire voltage"), max_digits=6, decimal_places=2, null=True, blank=True,
                                  # Translators: Volt
                                  help_text=_("in V"))
    wire_power = models.DecimalField(_("wire power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                     help_text=_("in W"))
    wire_material = models.CharField(_("wire material"), max_length=20, choices=cluster_tool_wire_material_choices)
    base_pressure = models.FloatField(_("base pressure"), help_text=_("in mbar"), null=True, blank=True)

    class Meta:
        abstract = True

    def get_data_items(self):
        return [DataItem("pressure/mbar", self.pressure),
                DataItem("time", self.time),
                DataItem("substrate-wire distance/mm", self.substrate_wire_distance),
                DataItem("comments", self.comments),
                DataItem("transfer in chamber", self.transfer_in_chamber),
                DataItem("pre-heat", self.pre_heat),
                DataItem("gas pre-heat gas", self.gas_pre_heat_gas),
                DataItem("gas pre-heat pressure/mbar", self.gas_pre_heat_pressure),
                DataItem("gas pre-heat time", self.gas_pre_heat_time),
                DataItem("heating temperature/degC", self.heating_temperature),
                DataItem("transfer out of chamber", self.transfer_out_of_chamber),
                DataItem("filament temperature/degC", self.filament_temperature),
                DataItem("current/A", self.current),
                DataItem("voltage/V", self.voltage),
                DataItem("wire power/W", self.wire_power),
                DataItem("wire material", self.wire_material),
                DataItem("base pressure/mbar", self.base_pressure)]

    def get_data_items_for_table_export(self):
        _ = ugettext
        return [DataItem(_("pressure") + "/mbar", self.pressure),
                DataItem(_("time"), self.time),
                DataItem(_("substrate–wire distance") + "/mm", self.substrate_wire_distance),
                DataItem(_("comments"), self.comments),
                DataItem(_("transfer in chamber"), self.transfer_in_chamber),
                DataItem(_("pre-heat"), self.pre_heat),
                DataItem(_("gas pre-heat gas"), self.gas_pre_heat_gas),
                DataItem(_("gas pre-heat pressure") + "/mbar", self.gas_pre_heat_pressure),
                DataItem(_("gas pre-heat time"), self.gas_pre_heat_time),
                DataItem(_("heating temperature") + "/degC", self.heating_temperature),
                DataItem(_("transfer out of chamber"), self.transfer_out_of_chamber),
                DataItem(_("filament temperature") + "/degC", self.filament_temperature),
                DataItem(_("current") + "/A", self.current),
                DataItem(_("voltage") + "/V", self.voltage),
                DataItem(_("wire power") + "/W", self.wire_power),
                DataItem(_("wire material"), self.get_wire_material_display()),
                DataItem(_("base pressure") + "/mbar", self.base_pressure)]


cluster_tool_pecvd_chamber_choices = (
    ("#1", "#1"),
    ("#2", "#2"),
    ("#3", "#3"),
)

class ClusterToolPECVDLayer(models.Model):
    """Abstract Model for the PECVD layers
    """
    chamber = models.CharField(_("chamber"), max_length=5, choices=cluster_tool_pecvd_chamber_choices)
    pressure = models.DecimalField(_("deposition pressure"), max_digits=5, decimal_places=3, help_text=_("in mbar"),
                                   null=True, blank=True)
    time = models.CharField(_("deposition time"), max_length=9, help_text=_("format HH:MM:SS"), blank=True)
    substrate_electrode_distance = \
        models.DecimalField(_("substrate–electrode distance"), null=True, blank=True, max_digits=4,
                            decimal_places=1, help_text=_("in mm"))
    comments = models.TextField(_("comments"), blank=True)
    transfer_in_chamber = models.CharField(_("transfer in the chamber"), max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField(_("pre-heat"), max_length=9, blank=True, help_text=_("format HH:MM:SS"))
    gas_pre_heat_gas = models.CharField(_("gas of gas pre-heat"), max_length=10, blank=True)
    gas_pre_heat_pressure = models.DecimalField(_("pressure of gas pre-heat"), max_digits=5, decimal_places=3,
                                                null=True, blank=True, help_text=_("in mbar"))
    gas_pre_heat_time = models.CharField(_("time of gas pre-heat"), max_length=15, blank=True,
                                         help_text=_("format HH:MM:SS"))
    heating_temperature = models.IntegerField(_("heating temperature"), help_text=_("in ℃"), null=True, blank=True)
    transfer_out_of_chamber = models.CharField(_("transfer out of the chamber"), max_length=10, default="Ar", blank=True)
    plasma_start_power = models.DecimalField(_("plasma start power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                             help_text=_("in W"))
    plasma_start_with_shutter = models.BooleanField(_("plasma start with shutter"), default=False)
    deposition_power = models.DecimalField(_("deposition power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text=_("in W"))
    base_pressure = models.FloatField(_("base pressure"), help_text=_("in mbar"), null=True, blank=True)

    class Meta:
        abstract = True

    def get_data_items(self):
        return [DataItem("chamber", self.chamber),
                DataItem("pressure/mbar", self.pressure),
                DataItem("time", self.time),
                DataItem("substrate-electrode distance/mm", self.substrate_electrode_distance),
                DataItem("comments", self.comments),
                DataItem("transfer in chamber", self.transfer_in_chamber),
                DataItem("pre-heat", self.pre_heat),
                DataItem("gas pre-heat gas", self.gas_pre_heat_gas),
                DataItem("gas pre-heat pressure/mbar", self.gas_pre_heat_pressure),
                DataItem("gas pre-heat time", self.gas_pre_heat_time),
                DataItem("heating temperature/degC", self.heating_temperature),
                DataItem("transfer out of chamber", self.transfer_out_of_chamber),
                DataItem("plasma start power/W", self.plasma_start_power),
                DataItem("plasma start with shutter", self.plasma_start_with_shutter),
                DataItem("deposition frequency/MHz", self.deposition_frequency),
                DataItem("deposition power/W", self.deposition_power),
                DataItem("base pressure/mbar", self.base_pressure)]

    def get_data_items_for_table_export(self):
        _ = ugettext
        return [DataItem(_("chamber"), self.get_chamber_display()),
                DataItem(_("pressure") + "/mbar", self.pressure),
                DataItem(_("time"), self.time),
                DataItem(_("substrate–electrode distance") + "/mm", self.substrate_electrode_distance),
                DataItem(_("comments"), self.comments),
                DataItem(_("transfer in chamber"), self.transfer_in_chamber),
                DataItem(_("pre-heat"), self.pre_heat),
                DataItem(_("gas pre-heat gas"), self.gas_pre_heat_gas),
                DataItem(_("gas pre-heat pressure") + "/mbar", self.gas_pre_heat_pressure),
                DataItem(_("gas pre-heat time"), self.gas_pre_heat_time),
                DataItem(_("heating temperature") + "/degC", self.heating_temperature),
                DataItem(_("transfer out of chamber"), self.transfer_out_of_chamber),
                DataItem(_("plasma start power") + "/W", self.plasma_start_power),
                DataItem(_("plasma start with shutter"), _("yes") if self.plasma_start_with_shutter else _("no")),
                DataItem(_("deposition frequency") + "/MHz", self.deposition_frequency),
                DataItem(_("deposition power") + "/W", self.deposition_power),
                DataItem(_("base pressure") + "/mbar", self.base_pressure)]


class OldClusterToolHotWireAndPECVDGases(models.Model):
    h2 = models.DecimalField("H₂", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    sih4 = models.DecimalField("SiH₄", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    mms = models.DecimalField("MMS", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    tmb = models.DecimalField("TMB", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    co2 = models.DecimalField("CO₂", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    ph3 = models.DecimalField("PH₃", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    ch4 = models.DecimalField("CH₄", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    ar = models.DecimalField("Ar", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))

    class Meta:
        abstract = True

    def get_data_items(self):
        return [DataItem("H2/sccm", self.h2),
                DataItem("SiH4/sccm", self.sih4),
                DataItem("MMS/sccm", self.mms),
                DataItem("TMB/sccm", self.tmb),
                DataItem("CO2/sccm", self.co2),
                DataItem("PH3/sccm", self.ph3),
                DataItem("CH4/sccm", self.ch4),
                DataItem("Ar/sccm", self.ar)]

    def get_data_items_for_table_export(self):
        return [DataItem("H₂/sccm", self.h2),
                DataItem("SiH₄/sccm", self.sih4),
                DataItem("MMS/sccm", self.mms),
                DataItem("TMB/sccm", self.tmb),
                DataItem("CO₂/sccm", self.co2),
                DataItem("PH₃/sccm", self.ph3),
                DataItem("CH₄/sccm", self.ch4),
                DataItem("Ar/sccm", self.ar)]


class PHotWireGases(models.Model):
    h2 = models.DecimalField("H₂", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    sih4 = models.DecimalField("SiH₄", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    mms = models.DecimalField("MMS", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    tmb = models.DecimalField("TMB", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    ch4 = models.DecimalField("CH₄", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    ph3_sih4 = models.DecimalField("2% PH₃ in SiH₄", max_digits=5, decimal_places=2, null=True, blank=True,
                                   help_text=_("in sccm"))
    ar = models.DecimalField("Ar", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    tmal = models.DecimalField("TMAl", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))

    class Meta:
        abstract = True

    def get_data_items(self):
        return [DataItem("H2/sccm", self.h2),
                DataItem("SiH4/sccm", self.sih4),
                DataItem("MMS/sccm", self.mms),
                DataItem("TMB/sccm", self.tmb),
                DataItem("CH4/sccm", self.ch4),
                DataItem("2% PH3 in SiH4/sccm", self.ph3_sih4),
                DataItem("Ar/sccm", self.ar),
                DataItem("TMAl/sccm", self.tmal)]

    def get_data_items_for_table_export(self):
        return [DataItem("H₂/sccm", self.h2),
                DataItem("SiH₄/sccm", self.sih4),
                DataItem("MMS/sccm", self.mms),
                DataItem("TMB/sccm", self.tmb),
                DataItem("CH₄/sccm", self.ch4),
                DataItem("2% PH₃ in SiH₄/sccm", self.ph3_sih4),
                DataItem("Ar/sccm", self.ar),
                DataItem("TMAl/sccm", self.tmal)]


class NewClusterToolHotWireAndPECVDGases(models.Model):
    h2 = models.DecimalField("H₂", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    sih4 = models.DecimalField("SiH₄", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    tmb = models.DecimalField("TMB", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    co2 = models.DecimalField("CO₂", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    ph3 = models.DecimalField("PH₃", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    ch4 = models.DecimalField("CH₄", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    ar = models.DecimalField("Ar", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    geh4 = models.DecimalField("GeH₄", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    b2h6 = models.DecimalField("B₂H₆", max_digits=5, decimal_places=2, null=True, blank=True, help_text=_("in sccm"))
    sih4_29 = models.DecimalField("²⁹SiH₄", max_digits=5, decimal_places=2, null=True, blank=True,
                                  help_text=_("in sccm"))

    class Meta:
        abstract = True

    def get_data_items(self):
        return [DataItem("H2/sccm", self.h2),
                DataItem("SiH4/sccm", self.sih4),
                DataItem("TMB/sccm", self.tmb),
                DataItem("CO2/sccm", self.co2),
                DataItem("PH3/sccm", self.ph3),
                DataItem("CH4/sccm", self.ch4),
                DataItem("Ar/sccm", self.ar),
                DataItem("GeH4/sccm", self.geh4),
                DataItem("B2H6/sccm", self.b2h6),
                DataItem("29-SiH4/sccm", self.sih4_29)]

    def get_data_items_for_table_export(self):
        return [DataItem("H₂/sccm", self.h2),
                DataItem("SiH₄/sccm", self.sih4),
                DataItem("TMB/sccm", self.tmb),
                DataItem("CO₂/sccm", self.co2),
                DataItem("PH₃/sccm", self.ph3),
                DataItem("CH₄/sccm", self.ch4),
                DataItem("Ar/sccm", self.ar),
                DataItem("GeH₄/sccm", self.geh4),
                DataItem("B₂H₆/sccm", self.b2h6),
                DataItem("²⁹SiH₄/sccm", self.sih4_29)]


class OldClusterToolDeposition(samples.models_depositions.Deposition):
    """Old cluster tool depositions.  It is also called “cluster tool I”.
    """
    carrier = models.CharField(_("carrier"), max_length=10, blank=True)

    class Meta(samples.models_depositions.Deposition.Meta):
        verbose_name = _("cluster tool I deposition")
        verbose_name_plural = _("cluster tool I depositions")
        _ = lambda x: x
        permissions = (("add_old_cluster_tool_deposition", _("Can add cluster tool I depositions")),
                       ("edit_permissions_for_old_cluster_tool_deposition",
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                        _("Can edit perms for cluster tool I depositions")),
                       ("view_every_old_cluster_tool_deposition", _("Can view all cluster tool I depositions")),
                       ("edit_every_old_cluster_tool_deposition", _("Can edit all cluster tool I depositions")))

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.old_cluster_tool_deposition.show", [urlquote(self.number, safe="")])

    @classmethod
    def get_add_link(cls):
        """Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_old_cluster_tool_deposition")

    @classmethod
    def get_lab_notebook_data(cls, year, month):
        _ = ugettext
        depositions = cls.get_lab_notebook_context(year, month)["processes"]
        data = DataNode(_("lab notebook for {process_name}").format(process_name=cls._meta.verbose_name_plural))
        for deposition in depositions:
            for layer in deposition.layers.all():
                # Attention: Here, I must call ``actual_instance`` because
                # cluster-tool layers are heterogeneous.
                layer_data = layer.actual_instance.get_data_for_table_export()
                layer_data.descriptive_name = ""
                layer_data.items.insert(0, DataItem(_("deposition number"), deposition.number))
                data.children.append(layer_data)
        return data

    def get_context_for_user(self, user, old_context):
        """
        Additionally, because this is a cluster tool and thus has different
        type of layers, I add a layer list ``layers`` to the template context.
        The template can't access the layers with ``process.layers.all()``
        because they are polymorphic.  But ``layers`` can be conveniently
        digested by the template.
        """
        context = old_context.copy()
        layers = []
        for layer in self.layers.all():
            try:
                layer = layer.oldclustertoolhotwirelayer
                layer.type = "hot-wire"
            except OldClusterToolHotWireLayer.DoesNotExist:
                layer = layer.oldclustertoolpecvdlayer
                layer.type = "PECVD"
            layers.append(layer)
        context["layers"] = layers
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = django.core.urlresolvers.reverse("edit_old_cluster_tool_deposition",
                                                                   kwargs={"deposition_number": self.number})
        else:
            context["edit_url"] = None
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_old_cluster_tool_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(OldClusterToolDeposition, self).get_context_for_user(user, context)

    def get_data(self):
        data_node = super(OldClusterToolDeposition, self).get_data()
        data_node.items.append(DataItem("carrier", self.carrier))
        data_node.children = [layer.actual_instance.get_data() for layer in self.layers.all()]
        return data_node

    def get_data_for_table_export(self):
        _ = ugettext
        data_node = super(OldClusterToolDeposition, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("carrier"), self.carrier))
        data_node.children = [layer.actual_instance.get_data_for_table_export() for layer in self.layers.all()]
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.  I must override the inherited method because I want to offer
        the layer models directly instead of the proxy class
        `OldClusterToolLayer`.

        :Return:
          the tree node for this model instance

        :rtype: ``chantal_common.search.SearchTreeNode``
        """
        model_field = super(OldClusterToolDeposition, cls).get_search_tree_node()
        model_field.related_models.update({OldClusterToolHotWireLayer: "layers", OldClusterToolPECVDLayer: "layers"})
        del model_field.related_models[OldClusterToolLayer]
        return model_field

samples.models_depositions.default_location_of_deposited_samples[OldClusterToolDeposition] = \
    _("large-area deposition lab")


class OldClusterToolLayer(samples.models_depositions.Layer, chantal_common_models.PolymorphicModel):
    """Model for a layer the old “cluster tool”.  Note that this is the common
    base class for the actual layer models `OldClusterToolHotWireLayer` and
    `OldClusterToolPECVDLayer`.  This is *not* an abstract model though because
    it needs to be back-referenced from the deposition.  I need inheritance and
    polymorphism here because cluster tools may have layers with very different
    fields.
    """
    deposition = models.ForeignKey(OldClusterToolDeposition, related_name="layers", verbose_name=_("deposition"))

    class Meta(samples.models_depositions.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("cluster tool I layer")
        verbose_name_plural = _("cluster tool I layers")

    def __unicode__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)


class OldClusterToolHotWireLayer(OldClusterToolLayer, OldClusterToolHotWireAndPECVDGases, ClusterToolHotWireLayer):
    """Model for a hot-wire layer in the old cluster tool.  We have no
    “chamber” field here because there is only one hot-wire chamber anyway.
    """

    class Meta(OldClusterToolLayer.Meta):
        verbose_name = _("cluster tool I hot-wire layer")
        verbose_name_plural = _("cluster tool I hot-wire layers")

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = samples.models_depositions.Layer.get_data(self)
        data_node.items.append(DataItem("layer type", "hot-wire"))
        data_node.items.extend(ClusterToolHotWireLayer.get_data_items(self) +
                               OldClusterToolHotWireAndPECVDGases.get_data_items(self))
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        data_node = samples.models_depositions.Layer.get_data_for_table_export(self)
        data_node.items.extend(ClusterToolHotWireLayer.get_data_items_for_table_export(self) +
                               OldClusterToolHotWireAndPECVDGases.get_data_items_for_table_export(self))
        return data_node


class OldClusterToolPECVDLayer(OldClusterToolLayer, OldClusterToolHotWireAndPECVDGases, ClusterToolPECVDLayer):
    """Model for a PECDV layer in the old cluster tool.
    """
    deposition_frequency = models.DecimalField(_("deposition frequency"), max_digits=5, decimal_places=2,
                                               null=True, blank=True, help_text=_("in MHz"))
    class Meta(OldClusterToolLayer.Meta):
        verbose_name = _("cluster tool I PECVD layer")
        verbose_name_plural = _("cluster tool I PECVD layers")

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = samples.models_depositions.Layer.get_data(self)
        data_node.items.append(DataItem("layer type", "PECVD"))
        data_node.items.extend(ClusterToolPECVDLayer.get_data_items(self) +
                               OldClusterToolHotWireAndPECVDGases.get_data_items(self))
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        data_node = samples.models_depositions.Layer.get_data_for_table_export(self)
        data_node.items.extend(ClusterToolPECVDLayer.get_data_items_for_table_export(self) +
                               OldClusterToolHotWireAndPECVDGases.get_data_items_for_table_export(self))
        return data_node


class NewClusterToolDeposition(samples.models_depositions.Deposition):
    """New Cluster Tool depositions.  It is also called “cluster tool II”.
    """
    carrier = models.CharField(_("carrier"), max_length=10, blank=True)

    class Meta(samples.models_depositions.Deposition.Meta):
        verbose_name = _("cluster tool II deposition")
        verbose_name_plural = _("cluster tool II depositions")
        _ = lambda x: x
        permissions = (("add_new_cluster_tool_deposition", _("Can add cluster tool II depositions")),
                       ("edit_permissions_for_new_cluster_tool_deposition",
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                        _("Can edit perms for cluster tool II depositions")),
                       ("view_every_new_cluster_tool_deposition", _("Can view all cluster tool II depositions")),
                       ("edit_every_new_cluster_tool_deposition", _("Can edit all cluster tool II depositions")))

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.new_cluster_tool_deposition.show", [urlquote(self.number, safe="")])


    @classmethod
    def get_lab_notebook_data(cls, year, month):
        _ = ugettext
        depositions = cls.get_lab_notebook_context(year, month)["processes"]
        data = DataNode(_("lab notebook for {process_name}").format(process_name=cls._meta.verbose_name_plural))
        for deposition in depositions:
            for layer in deposition.layers.all():
                # Attention: Here, I must call ``actual_instance`` because
                # cluster-tool layers are heterogeneous.
                layer_data = layer.actual_instance.get_data_for_table_export()
                layer_data.descriptive_name = ""
                layer_data.items.insert(0, DataItem(_("deposition number"), deposition.number))
                data.children.append(layer_data)
        return data

    def get_context_for_user(self, user, old_context):
        """
        Additionally, because this is a cluster tool and thus has different
        type of layers, I add a layer list ``layers`` to the template context.
        The template can't access the layers with ``process.layers.all()``
        because they are polymorphic.  But ``layers`` can be conveniently
        digested by the template.
        """
        context = old_context.copy()
        layers = []
        for layer in self.layers.all():
            try:
                layer = layer.newclustertoolhotwirelayer
                layer.type = "hot-wire"
            except NewClusterToolHotWireLayer.DoesNotExist:
                try:
                    layer = layer.newclustertoolpecvdlayer
                    layer.type = "PECVD"
                except NewClusterToolPECVDLayer.DoesNotExist:
                    layer = layer.newclustertoolsputterlayer
                    layer.type = "Sputter"
            layers.append(layer)
        context["layers"] = layers
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = django.core.urlresolvers.reverse("edit_new_cluster_tool_deposition",
                                                                   kwargs={"deposition_number": self.number})
        else:
            context["edit_url"] = None
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_new_cluster_tool_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(NewClusterToolDeposition, self).get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        """Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_new_cluster_tool_deposition")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(NewClusterToolDeposition, self).get_data()
        data_node.items.append(DataItem("carrier", self.carrier))
        data_node.children = [layer.get_data() for layer in self.layers.all()]
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(NewClusterToolDeposition, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("carrier"), self.carrier))
        data_node.children = [layer.actual_instance.get_data_for_table_export() for layer in self.layers.all()]
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.  I must override the inherited method because I want to offer
        the layer models directly instead of the proxy class
        `NewClusterToolLayer`.

        :Return:
          the tree node for this model instance

        :rtype: ``chantal_common.search.SearchTreeNode``
        """
        model_field = super(NewClusterToolDeposition, cls).get_search_tree_node()
        model_field.related_models.update({NewClusterToolHotWireLayer: "layers", NewClusterToolPECVDLayer: "layers",
                                           NewClusterToolSputterLayer: "layers"})
        del model_field.related_models[NewClusterToolLayer]
        return model_field

samples.models_depositions.default_location_of_deposited_samples[NewClusterToolDeposition] = \
    _("cluster tool II deposition lab")


class NewClusterToolLayer(samples.models_depositions.Layer, chantal_common_models.PolymorphicModel):
    """Model for a layer the new “cluster tool”.  Note that the new cluster tool
    has the same infrastructure as the old cluster tool.
    All i have to do, is to derive the layers from the old cluster tool.
    """
    deposition = models.ForeignKey(NewClusterToolDeposition, related_name="layers", verbose_name=_("deposition"))

    class Meta(samples.models_depositions.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("cluster tool II layer")
        verbose_name_plural = _("cluster tool II layers")

    def __unicode__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)


class NewClusterToolHotWireLayer(NewClusterToolLayer, NewClusterToolHotWireAndPECVDGases, ClusterToolHotWireLayer):
    """Model for a hot-wire layer in the new cluster tool.  We have no
    “chamber” field here because there is only one hot-wire chamber anyway.
    """

    class Meta(OldClusterToolLayer.Meta):
        verbose_name = _("cluster tool II hot-wire layer")
        verbose_name_plural = _("cluster tool II hot-wire layers")

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = samples.models_depositions.Layer.get_data(self)
        data_node.items.append(DataItem("layer type", "hot-wire"))
        data_node.items.extend(ClusterToolHotWireLayer.get_data_items(self) +
                               NewClusterToolHotWireAndPECVDGases.get_data_items(self))
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        data_node = samples.models_depositions.Layer.get_data_for_table_export(self)
        data_node.items.extend(ClusterToolHotWireLayer.get_data_items_for_table_export(self) +
                               NewClusterToolHotWireAndPECVDGases.get_data_items_for_table_export(self))
        return data_node


new_cluster_tool_frequency_choices = (
    (Decimal("13.56"), "13.56"),
    (Decimal("81.36"), "81.36"),
)

class NewClusterToolPECVDLayer(NewClusterToolLayer, NewClusterToolHotWireAndPECVDGases, ClusterToolPECVDLayer):
    """Model for a PECDV layer in the new cluster tool.
    """
    deposition_frequency = models.DecimalField(_("deposition frequency"), max_digits=5, decimal_places=2,
                                               choices=new_cluster_tool_frequency_choices, null=True, blank=True,
                                               help_text=_("in MHz"))

    class Meta(OldClusterToolLayer.Meta):
        verbose_name = _("cluster tool II PECVD layer")
        verbose_name_plural = _("cluster tool II PECVD layers")

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = samples.models_depositions.Layer.get_data(self)
        data_node.items.append(DataItem("layer type", "PECVD"))
        data_node.items.extend(ClusterToolPECVDLayer.get_data_items(self) +
                               NewClusterToolHotWireAndPECVDGases.get_data_items(self))
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        data_node = samples.models_depositions.Layer.get_data_for_table_export(self)
        data_node.items.extend(ClusterToolPECVDLayer.get_data_items_for_table_export(self) +
                               NewClusterToolHotWireAndPECVDGases.get_data_items_for_table_export(self))
        return data_node


cluter_tool_sputter_loading_chamber_choices = (
    ("MC1", "MC1"),
    ("MC2", "MC2")
)

class NewClusterToolSputterLayer(NewClusterToolLayer):
    """Model for a Sputter layer in the new cluster tool.
    """
    comments = models.TextField(_("comments"), blank=True)
    base_pressure = models.FloatField(_("base pressure"), null=True, blank=True, help_text=_("in mbar"))
    working_pressure = models.FloatField(_("working pressure"), null=True, blank=True, help_text=_("in mbar"))
    valve = models.DecimalField(_("valve"), max_digits=6, decimal_places=3, null=True, blank=True, help_text=_("in %"))
        # Translators: "set" in the sense of "setted"
    set_temperature = models.IntegerField(_("set temperature"), blank=True, null=True, help_text=_("in ℃"))
    thermocouple = models.DecimalField(_("thermocouple"), max_digits=4, decimal_places=1, blank=True, null=True,
                                       help_text=_("in ℃"))
    ts = models.DecimalField("T<sub>S</sub>", max_digits=4, decimal_places=1, blank=True, null=True, help_text=_("in ℃"))
    pyrometer = models.DecimalField(_("pyrometer"), max_digits=4, decimal_places=1, blank=True, null=True,
                                    help_text=_("in ℃"))
    ar = models.DecimalField("Ar", max_digits=5, decimal_places=2, help_text=_("in sccm"), null=True, blank=True)
    o2 = models.DecimalField("O₂", max_digits=5, decimal_places=2, help_text=_("in sccm"), null=True, blank=True)
    ar_o2 = models.DecimalField("1% Ar/O₂", max_digits=5, decimal_places=2, help_text=_("in sccm"), null=True, blank=True)
    pre_heat = models.IntegerField(_("pre-heat"), help_text=_("in min"), null=True, blank=True)
    pre_sputter_time = models.DecimalField(_("pre-sputter time"), help_text=_("in min"), max_digits=6, decimal_places=2,
                                          null=True, blank=True)
    large_shutter = models.CharField(_("large shutter"), max_length=30, blank=True)
    small_shutter = models.CharField(_("small shutter"), max_length=30, blank=True)
    substrate_holder = models.CharField(_("substrate holder"), max_length=15, blank=True)
    rotational_speed = models.DecimalField(_("rotational speed"), max_digits=6, decimal_places=3, null=True, blank=True,
                                           help_text=_("in rpm"))
    loading_chamber = models.CharField(_("loading chamber"), max_length=3, blank=True,
                                       choices=cluter_tool_sputter_loading_chamber_choices)

    class Meta(NewClusterToolLayer.Meta):
        verbose_name = _("cluster tool II sputter layer")
        verbose_name_plural = _("cluster tool II sputter layers")

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = samples.models_depositions.Layer.get_data(self)
        data_node.items.append(DataItem("layer type", "sputter"))
        data_node.items.extend([
                DataItem("comments", self.comments),
                DataItem("base pressure/mbar", self.base_pressure),
                DataItem("working pressure/mbar", self.working_pressure),
                DataItem("valve/%", self.valve),
                DataItem("set temperature/degC", self.set_temperature),
                DataItem("thermocouple/degC", self.thermocouple),
                DataItem("T_S/degC", self.ts),
                DataItem("pyrometer/degC", self.pyrometer),
                DataItem("Ar/sccm", self.ar),
                DataItem("O2/sccm", self.o2),
                DataItem("1% Ar+O2/sccm", self.ar_o2),
                DataItem("pre-heat/min", self.pre_heat),
                DataItem("pre-sputter time/min", self.pre_sputter),
                DataItem("large shutter", self.large_shutter),
                DataItem("small shutter", self.small_shutter),
                DataItem("substrate holder", self.substrate_holder),
                DataItem("rotational speed/rpm", self.rotational_speed),
                DataItem("loading chamber", self.loading_chamber)])
        data_node.children.extend(slot.get_data() for slot in self.slots.all())
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = samples.models_depositions.Layer.get_data_for_table_export(self)
        data_node.items.extend([
                DataItem(_("comments"), self.comments),
                DataItem(_("base pressure") + "/mbar", self.base_pressure),
                DataItem(_("working pressure") + "/mbar", self.working_pressure),
                DataItem(_("valve") + "/%", self.valve),
                DataItem(_("set temperature") + "/degC", self.set_temperature),
                DataItem(_("thermocouple") + "/degC", self.thermocouple),
                DataItem("T_S/degC", self.ts),
                DataItem(_("pyrometer") + "/degC", self.pyrometer),
                DataItem("Ar/sccm", self.ar),
                DataItem("O₂/sccm", self.o2),
                DataItem("1% Ar+O₂/sccm", self.ar_o2),
                DataItem(_("pre-heat") + "/min", self.pre_heat),
                DataItem(_("pre-sputter time") + "/min", self.pre_sputter_time),
                DataItem(_("large shutter"), self.large_shutter),
                DataItem(_("small shutter"), self.small_shutter),
                DataItem(_("substrate holder"), self.substrate_holder),
                DataItem(_("rotational speed") + "/rpm", self.rotational_speed),
                DataItem(_("loading chamber"), self.get_loading_chamber_display())])
        data_node.children.extend(slot.get_data_for_table_export() for slot in self.slots.all())
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        node = super(NewClusterToolSputterLayer, cls).get_search_tree_node()
        node.related_models[NewClusterToolSputterSlot] = "slots"
        return node


cluster_tool_target_choices = (
    ("ZnO:Ga 1%", "ZnO:Ga 1%"),
    ("ZnO:Ga 2%", "ZnO:Ga 2%"),
    ("ZnO (i)", "ZnO (i)"),
    ("ZnO:Al 0.5%", "ZnO:Al 0.5%"),
    ("ZnO:Al 1%", "ZnO:Al 1%"),
    ("Ag", "Ag"),
    ("ZnMgO 50%", "ZnMgO 50%"),
    ("Ion", "Ion"),
    )

cluster_tool_sputter_mode_choices = (
    ("RF", "RF"),
    ("DC", "DC"),
    )

class NewClusterToolSputterSlot(models.Model):
    """Model for the sputter slot.  Since in the Cluster Tool II, all three
    sputter slots may be active at the same time, *and* many fields are shared
    between the slots, I have a distinct model for them.  However, the slots
    are not identical: One may have DC or RF, one only DC, and one only RF
    (Ion).  But still, there are many fields in common.

    Note that a Cluster-Tool-II sputter layer has exactly three sputter slots,
    although the “mode” field may be empty, which means that this slot was not
    used.

    The edit view must assure that only consistent data is saved in the slots.
    Since all slot instances must be that same, the RDBMS backend cannot do
    this.  In particular, since a slot may be unused, no field can be required.
    """
    layer = models.ForeignKey(NewClusterToolSputterLayer, related_name="slots", verbose_name=_("layer"))
    number = models.PositiveSmallIntegerField(_("number"))
    mode = models.CharField(_("mode"), max_length=15, choices=cluster_tool_sputter_mode_choices, blank=True, null=True)
    target = models.CharField(_("target"), max_length=30, choices=cluster_tool_target_choices, blank=True)
    time = models.DecimalField(_("time"), max_digits=6, decimal_places=2, null=True, blank=True, help_text=_("in min"))
    power = models.IntegerField(_("power"), blank=True, null=True, help_text=_("in W"))
    power_end = models.IntegerField(string_concat(_("power"), "<sup>end</sup>"), blank=True, null=True,
                                    help_text=_("in W"))
    cl = models.IntegerField("C<sub>L</sub>", null=True, blank=True)
    ct = models.IntegerField("C<sub>T</sub>", null=True, blank=True)
    voltage = models.DecimalField(_("voltage"), max_digits=6, decimal_places=3, null=True, blank=True, help_text=_("in V"))
    voltage_end = models.DecimalField(_("voltage<sup>end</sup>"), max_digits=6, decimal_places=3, null=True, blank=True,
                                      help_text=_("in V"))
    refl_power = models.IntegerField(_("refl. power"), blank=True, null=True, help_text=_("in W"))
    current = models.DecimalField(_("current"), max_digits=6, decimal_places=3, null=True, blank=True, help_text=_("in A"))
    current_end = models.DecimalField(string_concat(_("current"), "<sup>end</sup>"), max_digits=6, decimal_places=3,
                                      null=True, blank=True, help_text=_("in A"))
    u_bias = models.DecimalField("U<sub>bias</sub>", max_digits=6, decimal_places=3, null=True, blank=True,
                                 help_text=_("in V"))
    u_bias_end = models.DecimalField("U<sub>bias</sub><sup>end</sup>", max_digits=6, decimal_places=3,
                                     null=True, blank=True, help_text=_("in V"))

    class Meta:
        verbose_name = _("cluster-tool-II sputter slot")
        verbose_name_plural = _("cluster-tool-II sputter slots")
        unique_together = ("layer", "number")
        ordering = ["number"]

    def __unicode__(self):
        _ = ugettext
        return _("slot {number} of {layer}").format(number=self.number, layer=self.layer)

    def get_data(self):
        data_node = DataNode("slot {0}".format(self.number))
        data_node.items.extend([
                DataItem("mode", self.mode),
                DataItem("target", self.target),
                DataItem("time/min", self.time),
                DataItem("power/W", self.power),
                DataItem("power^end/W", self.power_end),
                DataItem("C_L", self.cl),
                DataItem("C_T", self.ct),
                DataItem("voltage/V", self.voltage),
                DataItem("voltage^end/V", self.voltage_end),
                DataItem("refl. power/W", self.refl_power),
                DataItem("current/A", self.current),
                DataItem("current^end/A", self.current_end),
                DataItem("U_bias/V", self.u_bias),
                DataItem("U_bias^end/V", self.u_bias_end)])
        return data_node

    def get_data_for_table_export(self):
        _ = ugettext
        data_node = DataNode(_("slot {0}").format(self.number))
        data_node.items.extend([
                DataItem(_("mode"), self.get_mode_display()),
                DataItem(_("target"), self.get_target_display()),
                DataItem(_("time") + "/min", self.time),
                DataItem(_("power") + "/W", self.power),
                DataItem(_("power") + "^end/W", self.power_end),
                DataItem("C_L", self.cl),
                DataItem("C_T", self.ct),
                DataItem(_("voltage") + "/V", self.voltage),
                DataItem(_("voltage") + "^end/V", self.voltage_end),
                DataItem(_("refl. power") + "/W", self.refl_power),
                DataItem(_("current") + "/A", self.current),
                DataItem(_("current") + "^end/A", self.current_end),
                DataItem("U_bias" + "/V", self.u_bias),
                DataItem("U_bias" + "^end/V", self.u_bias_end)])
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


class PHotWireDeposition(samples.models_depositions.Deposition):
    """p-Hot Wire depositions.
    """

    class Meta(samples.models_depositions.Deposition.Meta):
        verbose_name = _("p-hot-wire deposition")
        verbose_name_plural = _("p-hot-wire depositions")
        _ = lambda x: x
        permissions = (("add_p_hot_wire_deposition", _("Can add p-hot-wire depositions")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_p_hot_wire_deposition", _("Can edit perms for p-hot-wire depositions")),
                       ("view_every_p_hot_wire_deposition", _("Can view all p-hot-wire depositions")),
                       ("edit_every_p_hot_wire_deposition", _("Can edit all p-hot-wire depositions")))

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.p_hot_wire_deposition.show", [urlquote(self.number, safe="")])

    @classmethod
    def get_add_link(cls):
        """Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_p_hot_wire_deposition")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_p_hot_wire_deposition", kwargs={"deposition_number": self.number})
        else:
            context["edit_url"] = None
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_p_hot_wire_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(PHotWireDeposition, self).get_context_for_user(user, context)

samples.models_depositions.default_location_of_deposited_samples[PHotWireDeposition] = _("p-hot-wire deposition lab")


class PHotWireLayer(samples.models_depositions.Layer, PHotWireGases, ClusterToolHotWireLayer):
    deposition = models.ForeignKey(PHotWireDeposition, related_name="layers", verbose_name=_("deposition"))

    class Meta(samples.models_depositions.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("p-hot-wire deposition layer")
        verbose_name_plural = _("p-hot-wire deposition layers")

    def __unicode__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = samples.models_depositions.Layer.get_data(self)
        data_node.items.extend(ClusterToolHotWireLayer.get_data_items(self) + PHotWireGases.get_data_items(self))
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        data_node = samples.models_depositions.Layer.get_data_for_table_export(self)
        data_node.items.extend(ClusterToolHotWireLayer.get_data_items_for_table_export(self) +
                               PHotWireGases.get_data_items_for_table_export(self))
        return data_node


class FiveChamberDeposition(samples.models_depositions.Deposition):
    """5-chamber depositions.
    """
    class Meta(samples.models_depositions.Deposition.Meta):
        verbose_name = _("5-chamber deposition")
        verbose_name_plural = _("5-chamber depositions")
        _ = lambda x: x
        permissions = (("add_five_chamber_deposition", _("Can add 5-chamber depositions")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_five_chamber_deposition", _("Can edit perms for 5-chamber depositions")),
                       ("view_every_five_chamber_deposition", _("Can view all 5-chamber depositions")),
                       ("edit_every_five_chamber_deposition", _("Can edit all 5-chamber depositions")))

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.five_chamber_deposition.show", [urlquote(self.number, safe="")])

    @classmethod
    def get_add_link(cls):
        """Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_5-chamber_deposition")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_5-chamber_deposition", kwargs={"deposition_number": self.number})
        else:
            context["edit_url"] = None
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_5-chamber_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(FiveChamberDeposition, self).get_context_for_user(user, context)

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.  I must override the inherited method because I want to offer
        the layer models directly instead of the proxy class
        `NewClusterToolLayer`.

        :Return:
          the tree node for this model instance

        :rtype: ``chantal_common.search.SearchTreeNode``
        """
        model_field = super(FiveChamberDeposition, cls).get_search_tree_node()
        model_field.related_models.update({FiveChamberLayer: "layers"})
        return model_field

samples.models_depositions.default_location_of_deposited_samples[FiveChamberDeposition] = _("5-chamber deposition lab")


five_chamber_chamber_choices = (
    ("i1", "i1"),
    ("i2", "i2"),
    ("i3", "i3"),
    ("p", "p"),
    ("n", "n"),
)

five_chamber_layer_type_choices = (
    ("p", "p"),
    ("i", "i"),
    ("n", "n"),
)

five_chamber_hf_frequency_choices = (
    (Decimal("13.26"), "13.26"),
    (Decimal("13.56"), "13.56"),
    (Decimal("16.56"), "16.56"),
    (Decimal("40"), "40"),
    (Decimal("100"), "100"),
)

five_chamber_impurity_choices = (
    ("O2", "O₂"),
    ("N2", "N₂"),
    ("PH3", "PH₃"),
    ("TMB", "TMB"),
    ("Air", _("Air")),
)

five_chamber_measurement_choices = (
    ("Raman", "Raman"),
    ("OES", "OES"),
    ("FTIR", "FTIR"),
)

class FiveChamberLayer(samples.models_depositions.Layer):
    """One layer in a 5-chamber deposition.
    """
    deposition = models.ForeignKey(FiveChamberDeposition, related_name="layers", verbose_name=_("deposition"))
    date = models.DateField(_("date"))
    layer_type = models.CharField(_("layer type"), max_length=2, choices=five_chamber_layer_type_choices, blank=True)
    chamber = models.CharField(_("chamber"), max_length=2, choices=five_chamber_chamber_choices)
    sih4 = models.DecimalField("SiH₄", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    h2 = models.DecimalField("H₂", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    tmb = models.DecimalField("TMB", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    ch4 = models.DecimalField("CH₄", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    co2 = models.DecimalField("CO₂", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    ph3 = models.DecimalField("PH₃", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    power = models.DecimalField(_("power"), max_digits=7, decimal_places=3, help_text=_("in W"), null=True, blank=True)
    pressure = models.DecimalField(_("pressure"), max_digits=7, decimal_places=3, help_text=_("in Torr"), null=True,
                                   blank=True)
    base_pressure = models.FloatField(_("base pressure"), help_text=_("in Torr"), null=True,
                                   blank=True)
    temperature_1 = models.DecimalField(_("temperature 1"), max_digits=7, decimal_places=3, help_text=_("in ℃"),
                                      null=True, blank=True)
    temperature_2 = models.DecimalField(_("temperature 2"), max_digits=7, decimal_places=3, help_text=_("in ℃"),
                                      null=True, blank=True)
    hf_frequency = models.DecimalField(_("HF frequency"), max_digits=5, decimal_places=2, null=True, blank=True,
                                       choices=five_chamber_hf_frequency_choices, help_text=_("in MHz"))
    time = models.IntegerField(_("time"), help_text=_("in sec"), null=True, blank=True)
    dc_bias = models.DecimalField(_("DC bias"), max_digits=7, decimal_places=3, help_text=_("in V"), null=True,
                                  blank=True)
    electrodes_distance = models.DecimalField(_("electrodes distance"), max_digits=7, decimal_places=3,
                                               help_text=_("in mm"), null=True, blank=True)
    impurity = models.CharField(_("impurity"), max_length=5, choices=five_chamber_impurity_choices, blank=True)
    in_situ_measurement = models.CharField(_("in-situ measurement"), max_length=10, blank=True,
                                            choices=five_chamber_measurement_choices)
    data_file = models.CharField(_("measurement data file"), max_length=80, blank=True,
                                 help_text=_("only the relative path below \"5k_PECVD/\""))

    class Meta(samples.models_depositions.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("5-chamber layer")
        verbose_name_plural = _("5-chamber layers")

    def __unicode__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = super(FiveChamberLayer, self).get_data()
        if self.sih4 and self.h2:
            silane_normalized = 0.6 * float(self.sih4)
            silane_concentration = silane_normalized / (silane_normalized + float(self.h2)) * 100
        else:
            silane_concentration = 0
        data_node.items.extend([DataItem("date", self.date),
                                DataItem("layer type", self.layer_type),
                                DataItem("chamber", self.chamber),
                                DataItem("SiH4/sccm", self.sih4),
                                DataItem("H2/sccm", self.h2),
                                DataItem("TMB/sccm", self.tmb),
                                DataItem("CH4/sccm", self.ch4),
                                DataItem("CO2/sccm", self.co2),
                                DataItem("PH3/sccm", self.ph3),
                                DataItem("SC/%", "{0:5.2f}".format(silane_concentration)),
                                DataItem("power/W", self.power),
                                DataItem("pressure/Torr", self.pressure),
                                DataItem("base pressure/Torr", self.base_pressure),
                                DataItem("T/degC (1)", self.temperature_1),
                                DataItem("T/degC (2)", self.temperature_2),
                                DataItem("f_HF/MHz", self.hf_frequency),
                                DataItem("time/s", self.time),
                                DataItem("DC bias/V", self.dc_bias),
                                DataItem("elec. dist./mm", self.electrodes_distance),
                                DataItem("impurity", self.impurity),
                                DataItem("in-situ measurement", self.in_situ_measurement),
                                DataItem("data file", self.data_file)])
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(FiveChamberLayer, self).get_data_for_table_export()
        if self.sih4 and self.h2:
            silane_normalized = 0.6 * float(self.sih4)
            silane_concentration = silane_normalized / (silane_normalized + float(self.h2)) * 100
        else:
            silane_concentration = 0
        data_node.items.extend([DataItem(_("date"), self.date),
                                DataItem(_("layer type"), self.get_layer_type_display()),
                                DataItem(_("chamber"), self.get_chamber_display()),
                                DataItem("SiH₄/sccm", self.sih4),
                                DataItem("H₂/sccm", self.h2),
                                DataItem("TMB/sccm", self.tmb),
                                DataItem("CH₄/sccm", self.ch4),
                                DataItem("CO₂/sccm", self.co2),
                                DataItem("PH₃/sccm", self.ph3),
                                DataItem("SC/%", "{0:5.2f}".format(silane_concentration)),
                                DataItem(_("power") + "/W", self.power),
                                DataItem(_("pressure") + "/Torr", self.pressure),
                                DataItem(_("base pressure") + "/Torr", self.base_pressure),
                                DataItem("T/℃ (1)", self.temperature_1),
                                DataItem("T/℃ (2)", self.temperature_2),
                                DataItem("f_HF/MHz", self.hf_frequency),
                                DataItem(_("time") + "/s", self.time),
                                DataItem(_("DC bias") + "/V", self.dc_bias),
                                DataItem(_("elec. dist.") + "/mm", self.electrodes_distance),
                                DataItem(_("impurity"), self.get_impurity_display()),
                                DataItem(_("in-situ measurement"), self.get_in_situ_measurement_display()),
                                DataItem(_("data file"), self.data_file)])
        return data_node


large_sputter_deposition_index_pattern = re.compile(r"\d\dV-(?P<number>\d+)(?P<trailer>.*)")
def normalize_large_sputter_deposition_index(deposition):
    match = large_sputter_deposition_index_pattern.match(deposition.number)
    return "{0:04}{1}".format(int(match.group(1)), match.group(1))

large_sputter_loadlock_choices = (
    ("??", _("unknown")),
    ("PC1", "PC1"),
    ("PC3", "PC3")
)

class LargeSputterDeposition(samples.models_depositions.Deposition):
    """large sputter depositions.
    """
    loadlock = models.CharField(_("loadlock"), max_length=3, choices=large_sputter_loadlock_choices, blank=True)

    class Meta(samples.models_depositions.Deposition.Meta):
        verbose_name = _("large sputter deposition")
        verbose_name_plural = _("large sputter depositions")
        _ = lambda x: x
        permissions = (("add_large_sputter_deposition", _("Can add large sputter depositions")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_large_sputter_deposition", _("Can edit perms for large sputter depositions")),
                       ("view_every_large_sputter_deposition", _("Can view all large sputter depositions")),
                       ("edit_every_large_sputter_deposition", _("Can edit all large sputter depositions")))

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.large_sputter_deposition.show", [urlquote(self.number, safe="")])

    @classmethod
    def get_add_link(cls):
        """Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_large_sputter_deposition")

    @classmethod
    def get_lab_notebook_context(cls, year, month):
        # I only change ordering here.
        processes = cls.objects.filter(timestamp__year=year, timestamp__month=month).select_related()
        return {"processes": sorted(processes, key=normalize_large_sputter_deposition_index, reverse=True)}

    @classmethod
    def get_lab_notebook_data(cls, year, month):
        # FixMe: Should this be the method of the parent class?  It seems to
        # occur with every deposition.
        _ = ugettext
        depositions = cls.get_lab_notebook_context(year, month)["processes"]
        data = DataNode(_("lab notebook for {process_name}").format(process_name=cls._meta.verbose_name_plural))
        for deposition in depositions:
            for layer in deposition.layers.all():
                layer_data = layer.get_data_for_table_export()
                layer_data.descriptive_name = ""
                layer_data.items.insert(0, DataItem(_("deposition number"), deposition.number))
                data.children.append(layer_data)
        return data

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(LargeSputterDeposition, self).get_data()
        data_node.items.append(DataItem("loadlock", self.loadlock))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LargeSputterDeposition, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("loadlock"), self.get_loadlock_display()))
        return data_node

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_large_sputter_deposition", kwargs={"deposition_number": self.number})
        else:
            context["edit_url"] = None
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_large_sputter_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(LargeSputterDeposition, self).get_context_for_user(user, context)

samples.models_depositions.default_location_of_deposited_samples[LargeSputterDeposition] = _("large sputter deposition lab")


large_sputter_target_choices = (
    ("ZnOAl2O3 0.5%", "ZnOAl₂O₃ 0.5%"),
    ("ZnOAl2O3 0.75%", "ZnOAl₂O₃ 0.75%"),
    ("ZnOAl2O3 1%", "ZnOAl₂O₃ 1%"),
    ("ZnOAl2O3 2%", "ZnOAl₂O₃ 2%"),
    ("Ag", "Ag"),
    ("Ion", "Ion"),
    ("ZnAl 0.2%", "ZnAl 0.2%"),
    ("ZnAl 0.5%", "ZnAl 0.5%"),
    ("ZnAl 0.55%", "ZnAl 0.55%"),
    ("ZnAl 1%", "ZnAl 1%"),
    ("ZnAl 2%", "ZnAl 2%"),
    ("Sispa", "Sispa 10wt%"),
)

large_sputter_mode_choices = (
    ("rf", "rf"),
    ("DC", "DC"),
    ("pulse", _("pulse")),
    ("MF", "MF"),
    ("R-MF", "R-MF"),
)

class LargeSputterLayer(samples.models_depositions.Layer):
    """One layer in a large sputter deposition.
    """
    deposition = models.ForeignKey(LargeSputterDeposition, related_name="layers", verbose_name=_("deposition"))
    layer_description = models.TextField(_("layer description"), blank=True)
    target = models.CharField(_("target"), max_length=30, choices=large_sputter_target_choices)
    mode = models.CharField(_("mode"), max_length=6, choices=large_sputter_mode_choices)
    rpm = models.IntegerField(_("&#x64; (tube target)"), help_text=_("in rpm"), null=True, blank=True)
    temperature_ll = models.IntegerField(_("temperature LL"), help_text=_("in ℃"), null=True, blank=True)
    temperature_pc_1 = models.IntegerField(string_concat(_("temperature PC"), " 1"), help_text=_("in ℃"),
                                           null=True, blank=True)
    temperature_pc_2 = models.IntegerField(string_concat(_("temperature PC"), " 2"), help_text=_("in ℃"),
                                           null=True, blank=True)
    temperature_pc_3 = models.IntegerField(string_concat(_("temperature PC"), " 3"), help_text=_("in ℃"),
                                           null=True, blank=True)
    temperature_smc_1 = models.IntegerField("T<sub>S</sub><sup>MC</sup> 1", help_text=_("in ℃"), null=True, blank=True)
    temperature_smc_2 = models.IntegerField("T<sub>S</sub><sup>MC</sup> 2", help_text=_("in ℃"), null=True, blank=True)
    temperature_smc_3 = models.IntegerField("T<sub>S</sub><sup>MC</sup> 3", help_text=_("in ℃"), null=True, blank=True)
    pre_heat = models.IntegerField(_("pre-heat"), help_text=_("in min"), null=True, blank=True)
    operating_pressure = models.DecimalField(_("opertating pressure"), max_digits=5, decimal_places=2,
                                             help_text=_("in 10⁻³ mbar"))
    base_pressure = models.DecimalField(_("base pressure"), max_digits=5, decimal_places=2, help_text=_("in 10⁻⁷ mbar"),
                                        null=True, blank=True)
    throttle = models.DecimalField(_("throttle"), max_digits=4, decimal_places=1, help_text=_("in %"),
                                   null=True, blank=True)
    gen_power = models.DecimalField(_("gen. power"), max_digits=5, decimal_places=2, help_text=_("in kW"),
                                    null=True, blank=True)
    ref_power = models.DecimalField(_("ref. power"), max_digits=3, decimal_places=1, help_text=_("in W"),
                                    null=True, blank=True)
    voltage_1 = models.IntegerField(string_concat(_("voltage"), " 1"), help_text=_("in V"), null=True, blank=True)
    voltage_2 = models.IntegerField(string_concat(_("voltage"), " 2"), help_text=_("in V"), null=True, blank=True)
    current_1 = models.DecimalField(string_concat(_("current"), " 1"), max_digits=5, decimal_places=3,
                                    help_text=_("in A"), null=True, blank=True)
    current_2 = models.DecimalField(string_concat(_("current"), " 2"), max_digits=5, decimal_places=3,
                                    help_text=_("in A"), null=True, blank=True)
    cl = models.IntegerField("C<sub>L</sub>", null=True, blank=True)
    ct = models.IntegerField("C<sub>T</sub>", null=True, blank=True)
    feed_rate = models.DecimalField(_("feed rate"), max_digits=6, decimal_places=3, help_text=_("in mm/s"),
                                    null=True, blank=True)
    steps = models.IntegerField(pgettext_lazy("large sputter deposition", "steps"), null=True, blank=True)
    static_time = models.DecimalField(_("static time"), max_digits=6, decimal_places=2, help_text=_("in min"),
                                      null=True, blank=True)
    ar_1 = models.DecimalField("Ar 1", help_text=_("in sccm"), max_digits=6, decimal_places=3, null=True, blank=True)
    ar_2 = models.DecimalField("Ar 2", help_text=_("in sccm"), max_digits=6, decimal_places=3, null=True, blank=True)
    o2_1 = models.DecimalField("O₂ 1", help_text=_("in sccm"), max_digits=5, decimal_places=2, null=True, blank=True)
    o2_2 = models.DecimalField("O₂ 2", help_text=_("in sccm"), max_digits=5, decimal_places=2, null=True, blank=True)
    ar_o2 = models.DecimalField("Ar/O₂", help_text=_("in sccm"), max_digits=5, decimal_places=2, null=True, blank=True)
    n2 = models.DecimalField("N₂", help_text=_("in sccm"), max_digits=5, decimal_places=2, null=True, blank=True)
    pem_1 = models.IntegerField("PEM 1", null=True, blank=True)
    pem_2 = models.IntegerField("PEM 2", null=True, blank=True)
    u_cal_1 = models.IntegerField(string_concat(_("U<sub>cal</sub>"), " 1"), help_text=_("in V"), null=True, blank=True)
    u_cal_2 = models.IntegerField(string_concat(_("U<sub>cal</sub>"), " 2"), help_text=_("in V"), null=True, blank=True)
    calibration_1 = models.CharField(string_concat(_("calibration"), " 1"), max_length=10, blank=True)
    calibration_2 = models.CharField(string_concat(_("calibration"), " 2"), max_length=10, blank=True)
    frequency = models.IntegerField(_("frequency"), null=True, blank=True, help_text=_("in kHz"))
    duty_cycle = models.IntegerField(_("duty cycle"), null=True, blank=True, help_text=_("in %"))
    accumulated_power = models.DecimalField(_("accumulated power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                            help_text=_("in kWh"))

    class Meta(samples.models_depositions.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("large sputter layer")
        verbose_name_plural = _("large sputter layers")

    def __unicode__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = super(LargeSputterLayer, self).get_data()
        data_node.items.extend([DataItem("layer description", self.layer_description),
                                DataItem("target", self.target),
                                DataItem("mode", self.mode),
                                DataItem("d/rpm", self.rpm),
                                DataItem("T_LL/degC", self.temperature_ll),
                                DataItem("T_PC/degC (1)", self.temperature_pc_1),
                                DataItem("T_PC/degC (2)", self.temperature_pc_2),
                                DataItem("T_PC/degC (3)", self.temperature_pc_3),
                                DataItem("T_S^MC/degC (1)", self.temperature_smc_1),
                                DataItem("T_S^MC/degC (2)", self.temperature_smc_2),
                                DataItem("T_S^MC/degC (3)", self.temperature_smc_3),
                                DataItem("pre-heat/min", self.pre_heat),
                                DataItem("op. pressure/10^-3 mbar", self.operating_pressure),
                                DataItem("b. pressure/10^-7 mbar", self.base_pressure),
                                DataItem("throttle/%", self.throttle),
                                DataItem("gen. power/kW", self.gen_power),
                                DataItem("ref. power/W", self.ref_power),
                                DataItem("voltage/V (1)", self.voltage_1),
                                DataItem("voltage/V (2)", self.voltage_2),
                                DataItem("current/A (1)", self.current_1),
                                DataItem("current/A (2)", self.current_2),
                                DataItem("C_L", self.cl),
                                DataItem("C_T", self.ct),
                                DataItem("feed/mm/s", self.feed_rate),
                                DataItem("steps", self.steps),
                                DataItem("static time/min", self.static_time),
                                DataItem("Ar/sccm (1)", self.ar_1),
                                DataItem("Ar/sccm (2)", self.ar_2),
                                DataItem("O2/sccm (1)", self.o2_1),
                                DataItem("O2/sccm (2)", self.o2_2),
                                DataItem("Ar/O2/sccm", self.ar_o2),
                                DataItem("N2/sccm", self.n2),
                                DataItem("PEM (1)", self.pem_1),
                                DataItem("PEM (2)", self.pem_2),
                                DataItem("U_cal/V (1)", self.u_cal_1),
                                DataItem("U_cal/V (2)", self.u_cal_2),
                                DataItem("calibration (1)", self.calibration_1),
                                DataItem("calibration (2)", self.calibration_2),
                                DataItem("frequency/kHz", self.frequency),
                                DataItem("duty cycle/%", self.duty_cycle),
                                DataItem("accumulated power/kWh", self.accumulated_power)
                                ])
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LargeSputterLayer, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("layer description"), self.layer_description),
                                DataItem(_("target"), self.get_target_display()),
                                DataItem(_("mode"), self.get_mode_display()),
                                DataItem("d/rpm", self.rpm),
                                DataItem("T_LL/℃", self.temperature_ll),
                                DataItem("T_PC/℃ (1)", self.temperature_pc_1),
                                DataItem("T_PC/℃ (2)", self.temperature_pc_2),
                                DataItem("T_PC/℃ (3)", self.temperature_pc_3),
                                DataItem("T_S^MC/℃ (1)", self.temperature_smc_1),
                                DataItem("T_S^MC/℃ (2)", self.temperature_smc_2),
                                DataItem("T_S^MC/℃ (3)", self.temperature_smc_3),
                                DataItem(_("pre-heat/min"), self.pre_heat),
                                DataItem(_("op. pressure") + "/10⁻³ mbar", self.operating_pressure),
                                DataItem(_("b. pressure") + "/10⁻⁷ mbar", self.base_pressure),
                                DataItem(_("throttle") + "/%", self.throttle),
                                DataItem(_("gen. power") + "/kW", self.gen_power),
                                DataItem(_("ref. power") + "/W", self.ref_power),
                                DataItem(_("voltage") + "/V (1)", self.voltage_1),
                                DataItem(_("voltage") + "/V (2)", self.voltage_2),
                                DataItem(_("current") + "/A (1)", self.current_1),
                                DataItem(_("current") + "/A (2)", self.current_2),
                                DataItem("C_L", self.cl),
                                DataItem("C_T", self.ct),
                                DataItem(_("feed") + "/mm/s", self.feed_rate),
                                DataItem(_("steps"), self.steps),
                                DataItem(_("static time") + "/min", self.static_time),
                                DataItem("Ar/sccm (1)", self.ar_1),
                                DataItem("Ar/sccm (2)", self.ar_2),
                                DataItem("O₂/sccm (1)", self.o2_1),
                                DataItem("O₂/sccm (2)", self.o2_2),
                                DataItem("Ar/O₂/sccm", self.ar_o2),
                                DataItem("N₂/sccm", self.n2),
                                DataItem("PEM (1)", self.pem_1),
                                DataItem("PEM (2)", self.pem_2),
                                DataItem(_("U_cal") + "/V (1)", self.u_cal_1),
                                DataItem(_("U_cal") + "/V (2)", self.u_cal_2),
                                DataItem(_("calibration") + " (1)", self.calibration_1),
                                DataItem(_("calibration") + " (2)", self.calibration_2),
                                DataItem(_("frequency") + "/kHz", self.frequency),
                                DataItem(_("duty cycle") + "/%", self.duty_cycle),
                                DataItem(_("accumulated power") + "/kWh", self.accumulated_power)
                                ])
        return data_node


lada_substrate_size_choices = (
    ("10x10", "10×10 cm²"),
    ("40x40", "40×40 cm²"),
)

class LADADeposition(samples.models_depositions.Deposition):
    """LADA-Deposition.
    """
    substrate_size = models.CharField(_("substrate size"), max_length=5, choices=lada_substrate_size_choices, blank=True)
    customer = models.ForeignKey(User, related_name="lada_customer", verbose_name=_("customer"))

    class Meta(samples.models_depositions.Deposition.Meta):
        verbose_name = _("LADA deposition")
        verbose_name_plural = _("LADA depositions")
        _ = lambda x: x
        permissions = (("add_lada_deposition", _("Can add LADA depositions")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_lada_deposition", _("Can edit perms for LADA depositions")),
                       ("view_every_lada_deposition", _("Can view all LADA depositions")),
                       ("edit_every_lada_deposition", _("Can edit all LADA depositions")))

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.lada_deposition.show", [urlquote(self.number, safe="")])

    @classmethod
    def get_add_link(cls):
        """Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_lada_deposition")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_lada_deposition", kwargs={"deposition_number": self.number})
        else:
            context["edit_url"] = None
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_lada_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(LADADeposition, self).get_context_for_user(user, context)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(LADADeposition, self).get_data()
        data_node.items.append(DataItem("substrate size", self.substrate_size))
        data_node.items.append(DataItem("customer", self.customer))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LADADeposition, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("substrate size"), self.get_substrate_size_display()))
        data_node.items.append(DataItem(_("customer"), get_really_full_name(self.customer)))
        return data_node

samples.models_depositions.default_location_of_deposited_samples[LADADeposition] = _("LADA lab")


lada_hf_frequency_choices = (
    (Decimal("13.56"), "13.56"),
    (Decimal("60"), "60"),
)
lada_chamber_choices = (
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
)
lada_carrier_choices = (
    ("left", _("left")),
    ("right", _("right")),
    ("dummy", _("dummy")),
    )
lada_gas_choices = (
    ("Ar", "Ar"),
    ("NF3", "NF₃"),
    ("NF3/Ar", "NF₃ / Ar"),
)
lada_mfc_choices = (
    ("1", "1.1"),
    ("2", "1.2"),
    ("3", "2.1"),
    ("4", "2.2"),
    ("5", "2.3"),
    ("6", "2.4"),
)

class LADALayer(samples.models_depositions.Layer):
    """One layer in a lada.

    *Important*: Numbers of lada layers are the numbers after the “D-”
    because they must be ordinary integers!
    """
    deposition = models.ForeignKey(LADADeposition, related_name="layers", verbose_name=_("deposition"))
    date = models.DateField(_("date"))
    carrier = models.CharField(_("carrier"), max_length=8, choices=lada_carrier_choices, blank=True)
    layer_type = models.CharField(_("layer type"), max_length=13)
    chamber = models.CharField(_("chamber"), max_length=1, choices=lada_chamber_choices)
    sih4_1 = models.DecimalField(_("SiH₄"), max_digits=5, decimal_places=2, help_text=_("in sccm"), null=True, blank=True)
    sih4_1_end = models.DecimalField(_("SiH₄<sup>end</sup>"), max_digits=5, decimal_places=2, help_text=_("in sccm"),
                                     null=True, blank=True)
    h2_1 = models.DecimalField(_("H₂"), max_digits=5, decimal_places=1, help_text=_("in sccm"), null=True, blank=True)
    h2_1_end = models.DecimalField(_("H₂<sup>end</sup>"), max_digits=5, decimal_places=1, help_text=_("in sccm"),
                                   null=True, blank=True)
    sih4_2 = models.DecimalField(_("SiH₄"), max_digits=5, decimal_places=2, help_text=_("in sccm"), null=True, blank=True)
    sih4_2_end = models.DecimalField(_("SiH₄<sup>end</sup>"), max_digits=5, decimal_places=2, help_text=_("in sccm"),
                                     null=True, blank=True)
    ph3_1 = models.DecimalField("PH₃", max_digits=3, decimal_places=1, help_text=_("in sccm"),
                                null=True, blank=True)
    ph3_1_end = models.DecimalField("PH₃<sup>end</sup>", max_digits=3, decimal_places=1, help_text=_("in sccm"),
                                null=True, blank=True)
    h2_2 = models.DecimalField(_("H₂"), max_digits=5, decimal_places=1, help_text=_("in sccm"), null=True, blank=True)
    h2_2_end = models.DecimalField(_("H₂<sup>end</sup>"), max_digits=5, decimal_places=1, help_text=_("in sccm"),
                                   null=True, blank=True)
    ph3_2 = models.DecimalField("PH₃", max_digits=4, decimal_places=1, help_text=_("in sccm"), null=True, blank=True)
    ph3_2_end = models.DecimalField("PH₃<sup>end</sup>", max_digits=4, decimal_places=1, help_text=_("in sccm"),
                                    null=True, blank=True)
    sih4_mfc_number_1 = models.CharField(_("SiH₄ MFC"), max_length=2, choices=lada_mfc_choices, blank=True)
    h2_mfc_number_1 = models.CharField(_("H₂ MFC"), max_length=2, choices=lada_mfc_choices, blank=True)
    sih4_mfc_number_2 = models.CharField(_("SiH₄ MFC"), max_length=2, choices=lada_mfc_choices, blank=True)
    h2_mfc_number_2 = models.CharField(_("H₂ MFC"), max_length=2, choices=lada_mfc_choices, blank=True)
    silane_concentration = models.DecimalField(_("silane concentration"), max_digits=5, decimal_places=2, help_text=_("in %"),
                                               null=True, blank=True)
    silane_concentration_end = models.DecimalField(_("silane concentration end"), max_digits=5, decimal_places=2, help_text=_("in %"),
                                                   null=True, blank=True)
    tmb_1 = models.DecimalField("TMB", max_digits=5, decimal_places=2, help_text=_("in sccm"), null=True, blank=True)
    tmb_2 = models.DecimalField("TMB", max_digits=5, decimal_places=2, help_text=_("in sccm"), null=True, blank=True)
    ch4 = models.DecimalField("CH₄", max_digits=3, decimal_places=1, help_text=_("in sccm"), null=True, blank=True)
    co2 = models.DecimalField("CO₂", max_digits=4, decimal_places=1, help_text=_("in sccm"), null=True, blank=True)
    power_1 = models.DecimalField(string_concat(_("power"), " 1"), max_digits=5, decimal_places=1, help_text=_("in W"))
    power_2 = models.DecimalField(string_concat(_("power"), " 2"), max_digits=5, decimal_places=1, help_text=_("in W"),
                                  null=True, blank=True)
    pressure = models.DecimalField(_("pressure"), max_digits=4, decimal_places=2, help_text=_("in mbar"))
    base_pressure = models.FloatField(_("base pressure"), help_text=_("in mbar"), null=True, blank=True)
    hf_frequency = models.DecimalField(_("HF frequency"), max_digits=4, decimal_places=2,
                                       choices=lada_hf_frequency_choices, help_text=_("in MHz"))
    time_1 = models.IntegerField(string_concat(_("time"), " 1"), help_text=_("in sec"), null=True, blank=True)
    time_2 = models.IntegerField(string_concat(_("time"), " 2"), help_text=_("in sec"), null=True, blank=True)
    electrodes_distance = models.DecimalField(_("electrodes distance"), max_digits=4, decimal_places=1,
                                               help_text=_("in mm"), null=True, blank=True)
    temperature_substrate = models.IntegerField(_("temperature substrate"), help_text=_("in ℃"), null=True, blank=True)
    temperature_heater = models.IntegerField(_("temperature heater"), help_text=_("in ℃"), null=True, blank=True)
    temperature_heater_depo = models.IntegerField(_("temperature heater deposition"), help_text=_("in ℃"), null=True,
                                                  blank=True)
    comments = models.TextField(_("comments"), blank=True)
    power_reflected_1 = models.DecimalField(string_concat(_("reflected power"), " 1"), max_digits=5, decimal_places=1,
                                             help_text=_("in W"), null=True, blank=True)
    power_reflected_2 = models.DecimalField(string_concat(_("reflected power"), " 2"), max_digits=5, decimal_places=1,
                                             help_text=_("in W"), null=True, blank=True)
    cl_1 = models.IntegerField("C<sub>L</sub> 1", null=True, blank=True)
    ct_1 = models.IntegerField("C<sub>T</sub> 1", null=True, blank=True)
    cl_2 = models.IntegerField("C<sub>L</sub> 2", null=True, blank=True)
    ct_2 = models.IntegerField("C<sub>T</sub> 2", null=True, blank=True)
    u_dc_1 = models.DecimalField(_("U<sub>DC</sub> 1"), max_digits=3, decimal_places=1, help_text=_("in V"),
                                 null=True, blank=True)
    u_dc_2 = models.DecimalField(_("U<sub>DC</sub> 2"), max_digits=3, decimal_places=1, help_text=_("in V"),
                                 null=True, blank=True)
    additional_gas = models.CharField(_("gas"), max_length=6, choices=lada_gas_choices, blank=True)
    additional_gas_flow = models.DecimalField(_("flow rate"), max_digits=6, decimal_places=2, help_text=_("in sccm"),
                                              null=True, blank=True)
    plasma_stop = models.BooleanField(_("plasma stop"), default=False)
    v_lq = models.DecimalField("V<sub>Substr.</sub>LQ", max_digits=4, decimal_places=3, help_text=_("m/s"), null=True, blank=True)
    pendulum_lq = models.IntegerField(_("pendulum number LQ"), null=True, blank=True)

    class Meta(samples.models_depositions.Layer.Meta):
        verbose_name = _("LADA layer")
        verbose_name_plural = _("LADA layers")
        unique_together = ("deposition", "number")

    def __unicode__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = super(LADALayer, self).get_data()
        data_node.items.extend([DataItem("date", self.date),
                                DataItem("carrier", self.carrier),
                                DataItem("layer type", self.layer_type),
                                DataItem("chamber", self.chamber),
                                DataItem("SiH4/sccm (1)", self.sih4_1),
                                DataItem("SiH4_end/sccm (1)", self.sih4_1_end),
                                DataItem("SiH4/sccm (2)", self.sih4_2),
                                DataItem("SiH4_end/sccm (2)", self.sih4_2_end),
                                DataItem("H2/sccm (1)", self.h2_1),
                                DataItem("H2_end/sccm (1)", self.h2_1_end),
                                DataItem("H2/sccm (2)", self.h2_2),
                                DataItem("H2_end/sccm (2)", self.h2_2_end),
                                DataItem("PH3/sccm (1)", self.ph3_1),
                                DataItem("PH3_end/sccm (1)", self.ph3_1_end),
                                DataItem("PH3/sccm (2)", self.ph3_2),
                                DataItem("PH3_end/sccm (2)", self.ph3_2_end),
                                DataItem("SiH4 MFC/# (1)", self.sih4_mfc_number_1),
                                DataItem("SiH4 MFC/# (2)", self.sih4_mfc_number_2),
                                DataItem("H2 MFC/# (1)", self.h2_mfc_number_1),
                                DataItem("H2 MFC/# (2)", self.h2_mfc_number_2),
                                DataItem("TMB/sccm (1)", self.tmb_1),
                                DataItem("TMB/sccm (2)", self.tmb_2),
                                DataItem("CH4/sccm", self.ch4),
                                DataItem("CO2/sccm", self.co2),
                                DataItem("SC/%", self.silane_concentration),
                                DataItem("SC_end/%", self.silane_concentration_end),
                                DataItem("P/W (1)", self.power_1),
                                DataItem("P/W (2)", self.power_2),
                                DataItem("P reflected/W (1)", self.power_reflected_1),
                                DataItem("P reflected/W (2)", self.power_reflected_2),
                                DataItem("p/mbar", self.pressure),
                                DataItem("base p/mbar", self.base_pressure),
                                DataItem("f_HF/MHz", self.hf_frequency),
                                DataItem("time/s (1)", self.time_1),
                                DataItem("time/s (2)", self.time_2),
                                DataItem("electr. dist./mm", self.electrodes_distance),
                                DataItem("T substr./degC", self.temperature_substrate),
                                DataItem("T heater/degC", self.temperature_heater),
                                DataItem("T heater depo/degC", self.temperature_heater_depo),
                                DataItem("C_L (1)", self.cl_1),
                                DataItem("C_L (2)", self.cl_2),
                                DataItem("C_T (1)", self.ct_1),
                                DataItem("C_T (2)", self.ct_2),
                                DataItem("U_DC (1)", self.u_dc_1),
                                DataItem("U_DC (2)", self.u_dc_2),
                                DataItem("gas", self.additional_gas),
                                DataItem("flow rate/sccm", self.additional_gas_flow),
                                DataItem("comments", self.comments.strip()),
                                DataItem("plasa stop", self.plasma_stop),
                                DataItem("V_Substrate LQ", self.v_lq),
                                DataItem("pendulum number LQ", self.pendulum_lq)])
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(LADALayer, self).get_data_for_table_export()
        data_node.items.extend([DataItem(_("date"), self.date),
                                DataItem(_("layer type"), self.layer_type),
                                DataItem(_("carrier"), self.get_carrier_display()),
                                DataItem(_("chamber"), self.get_chamber_display()),
                                DataItem("SiH₄/sccm (1)", self.sih4_1),
                                DataItem(_("SiH₄_end") + "/sccm (1)", self.sih4_1_end),
                                DataItem("SiH₄/sccm (2)", self.sih4_2),
                                DataItem(_("SiH₄_end") + "/sccm (2)", self.sih4_2_end),
                                DataItem("H₂/sccm (1)", self.h2_1),
                                DataItem(_("H₂_end") + "/sccm (1)", self.h2_1_end),
                                DataItem("H₂/sccm (2)", self.h2_2),
                                DataItem(_("H₂_end") + "/sccm (2)", self.h2_2_end),
                                DataItem("PH₃/sccm (1)", self.ph3_1),
                                DataItem(_("PH₃_end") + "/sccm (1)", self.ph3_1_end),
                                DataItem("PH₃/sccm (2)", self.ph3_2),
                                DataItem(_("PH₃_end") + "/sccm (2)", self.ph3_2_end),
                                DataItem("SiH4 MFC/# (1)", self.sih4_mfc_number_1),
                                DataItem("SiH4 MFC/# (2)", self.sih4_mfc_number_2),
                                DataItem("H2 MFC/# (1)", self.h2_mfc_number_1),
                                DataItem("H2 MFC/# (2)", self.h2_mfc_number_2),
                                DataItem("TMB/sccm (1)", self.tmb_1),
                                DataItem("TMB/sccm (2)", self.tmb_2),
                                DataItem("CH₄/sccm", self.ch4),
                                DataItem("CO₂/sccm", self.co2),
                                DataItem("SC/%", self.silane_concentration),
                                DataItem(_("SC_end") + "/%", self.silane_concentration_end),
                                DataItem("P/W (1)", self.power_1),
                                DataItem("P/W (2)", self.power_2),
                                DataItem(_("P reflected (1)") + "/W", self.power_reflected_1),
                                DataItem(_("P reflected (2)") + "/W", self.power_reflected_2),
                                DataItem("p/mbar", self.pressure),
                                DataItem(_("base") + " p/mbar", self.base_pressure),
                                DataItem("f_HF/MHz", self.hf_frequency),
                                DataItem(_("time") + "/s (1)", self.time_1),
                                DataItem(_("time") + "/s (2)", self.time_2),
                                DataItem(_("electr. dist.") + "/mm", self.electrodes_distance),
                                DataItem(_("T substr.") + "/℃", self.temperature_substrate),
                                DataItem(_("T heater") + "/℃", self.temperature_heater),
                                DataItem(_("T heater depo") + "/℃", self.temperature_heater_depo),
                                DataItem("C_L (1)", self.cl_1),
                                DataItem("C_L (2)", self.cl_2),
                                DataItem("C_T (1)", self.ct_1),
                                DataItem("C_T (2)", self.ct_2),
                                DataItem("U_DC (1)", self.u_dc_1),
                                DataItem("U_DC (2)", self.u_dc_2),
                                DataItem(_("Gas"), self.get_additional_gas_display()),
                                DataItem(_("flow rate") + "/sccm", self.additional_gas_flow),
                                DataItem(_("comments"), self.comments.strip()),
                                DataItem(_("plasma stop"), _("yes") if self.plasma_stop else _("no")),
                                DataItem(_("V_Substrate LQ"), self.v_lq),
                                DataItem(_("pendulum number LQ"), self.pendulum_lq)])
        return data_node


class JANADeposition(samples.models_depositions.Deposition):
    """jana depositions.
    """
    class Meta(samples.models_depositions.Deposition.Meta):
        verbose_name = _("JANA deposition")
        verbose_name_plural = _("JANA depositions")
        _ = lambda x: x
        permissions = (("add_jana_deposition", _("Can add JANA depositions")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_jana_deposition", _("Can edit perms for JANA depositions")),
                       ("view_every_jana_deposition", _("Can view all JANA depositions")),
                       ("edit_every_jana_deposition", _("Can edit all JANA depositions")))

    @models.permalink
    def get_absolute_url(self):
        return ("chantal_institute.views.samples.jana_deposition.show", [urlquote(self.number, safe="")])

    @classmethod
    def get_add_link(cls):
        """Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_jana_deposition")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_edit_physical_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_jana_deposition", kwargs={"deposition_number": self.number})
        else:
            context["edit_url"] = None
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_jana_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(JANADeposition, self).get_context_for_user(user, context)


samples.models_depositions.default_location_of_deposited_samples[JANADeposition] = _("jana deposition lab")


jana_chamber_choices = (
    ("p_3K", "p_3K"),
    ("i_3K", "i_3K"),
    ("n_3K", "n_3K"),
)

jana_layer_type_choices = (
    ("p", "p"),
    ("i", "i"),
    ("n", "n"),
)

jana_hf_frequency_choices = (
    (Decimal("13.56"), "13.56"),
    (Decimal("81.36"), "81.36"),
    (Decimal("108.48"), "108.48"),
)


class JANALayer(samples.models_depositions.Layer):
    """One layer in a jana deposition.
    """
    deposition = models.ForeignKey(JANADeposition, related_name="layers", verbose_name=_("deposition"))
    date = models.DateField(_("date"))
    layer_type = models.CharField(_("layer type"), max_length=2, choices=jana_layer_type_choices, blank=True)
    chamber = models.CharField(_("chamber"), max_length=10, choices=jana_chamber_choices)
    sih4 = models.DecimalField("SiH₄", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    h2 = models.DecimalField("H₂", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    tmb = models.DecimalField("TMB", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    ch4 = models.DecimalField("CH₄", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    co2 = models.DecimalField("CO₂", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    ph3 = models.DecimalField("PH₃", max_digits=7, decimal_places=3, help_text=_("in sccm"), null=True, blank=True)
    power = models.DecimalField(_("power"), max_digits=7, decimal_places=3, help_text=_("in W"), null=True, blank=True)
    pressure = models.DecimalField(_("pressure"), max_digits=7, decimal_places=3, help_text=_("in Torr"), null=True,
                                   blank=True)
    base_pressure = models.FloatField(_("base pressure"), help_text=_("in Torr"), null=True,
                                   blank=True)
    temperature_1 = models.DecimalField(_("temperature 1"), max_digits=7, decimal_places=3, help_text=_("in ℃"),
                                      null=True, blank=True)
    temperature_2 = models.DecimalField(_("temperature 2"), max_digits=7, decimal_places=3, help_text=_("in ℃"),
                                      null=True, blank=True)
    hf_frequency = models.DecimalField(_("HF frequency"), max_digits=7, decimal_places=2, null=True, blank=True,
                                       choices=jana_hf_frequency_choices, help_text=_("in MHz"))
    time = models.IntegerField(_("time"), help_text=_("in sec"), null=True, blank=True)
    dc_bias = models.DecimalField(_("DC bias"), max_digits=7, decimal_places=3, help_text=_("in V"), null=True,
                                  blank=True)



    class Meta(samples.models_depositions.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("JANA layer")
        verbose_name_plural = _("JANA layers")

    def __unicode__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        data_node = super(JANALayer, self).get_data()
        if self.sih4 and self.h2:
            silane_normalized = 0.6 * float(self.sih4)
            silane_concentration = silane_normalized / (silane_normalized + float(self.h2)) * 100
        else:
            silane_concentration = 0
        data_node.items.extend([DataItem("date", self.date),
                                DataItem("layer type", self.layer_type),
                                DataItem("chamber", self.chamber),
                                DataItem("SiH4/sccm", self.sih4),
                                DataItem("H2/sccm", self.h2),
                                DataItem("TMB/sccm", self.tmb),
                                DataItem("CH4/sccm", self.ch4),
                                DataItem("CO2/sccm", self.co2),
                                DataItem("PH3/sccm", self.ph3),
                                DataItem("SC/%", "{0:5.2f}".format(silane_concentration)),
                                DataItem("power/W", self.power),
                                DataItem("pressure/Torr", self.pressure),
                                DataItem("base pressure/Torr", self.base_pressure),
                                DataItem("T/degC (1)", self.temperature_1),
                                DataItem("T/degC (2)", self.temperature_2),
                                DataItem("f_HF/MHz", self.hf_frequency),
                                DataItem("time/s", self.time),
                                DataItem("DC bias/V", self.dc_bias)])
        return data_node

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(JANALayer, self).get_data_for_table_export()
        if self.sih4 and self.h2:
            silane_normalized = 0.6 * float(self.sih4)
            silane_concentration = silane_normalized / (silane_normalized + float(self.h2)) * 100
        else:
            silane_concentration = 0
        data_node.items.extend([DataItem(_("date"), self.date),
                                DataItem(_("layer type"), self.get_layer_type_display()),
                                DataItem(_("chamber"), self.get_chamber_display()),
                                DataItem("SiH₄/sccm", self.sih4),
                                DataItem("H₂/sccm", self.h2),
                                DataItem("TMB/sccm", self.tmb),
                                DataItem("CH₄/sccm", self.ch4),
                                DataItem("CO₂/sccm", self.co2),
                                DataItem("PH₃/sccm", self.ph3),
                                DataItem("SC/%", "{0:5.2f}".format(silane_concentration)),
                                DataItem(_("power") + "/W", self.power),
                                DataItem(_("pressure") + "/Torr", self.pressure),
                                DataItem(_("base pressure") + "/Torr", self.base_pressure),
                                DataItem("T/℃ (1)", self.temperature_1),
                                DataItem("T/℃ (2)", self.temperature_2),
                                DataItem("f_HF/MHz", self.hf_frequency),
                                DataItem(_("time") + "/s", self.time),
                                DataItem(_("DC bias") + "/V", self.dc_bias)])
        return data_node
