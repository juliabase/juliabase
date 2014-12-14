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


"""Models for IEF-5-specific depositions.  This includes the deposition models
themselves as well as models for layers.  Additionally, there are miscellaneous
models like the one to 6-chamber deposition channels.
"""

from __future__ import absolute_import, unicode_literals
from django.utils.encoding import python_2_unicode_compatible

from django.utils.translation import ugettext_lazy as _, ugettext
import django.core.urlresolvers
from django.utils.http import urlquote_plus
from django.db import models
from jb_common.utils import in_
import samples.models.depositions
from samples import permissions
from samples.data_tree import DataItem
from jb_common import models as jb_common_models


class ClusterToolHotWireAndPECVDGases(models.Model):
    h2 = models.DecimalField("H₂", max_digits=5, decimal_places=2, null=True, blank=True, help_text=in_("sccm"))
    sih4 = models.DecimalField("SiH₄", max_digits=5, decimal_places=2, null=True, blank=True, help_text=in_("sccm"))

    class Meta:
        abstract = True

    def get_data_items_for_table_export(self):
        return [DataItem("H₂/sccm", self.h2),
                DataItem("SiH₄/sccm", self.sih4), ]


class ClusterToolDeposition(samples.models.depositions.Deposition):
    """cluster tool depositions..
    """
    carrier = models.CharField(_("carrier"), max_length=10, blank=True)

    class Meta(samples.models.depositions.Deposition.Meta):
        verbose_name = _("cluster tool deposition")
        verbose_name_plural = _("cluster tool depositions")
        _ = lambda x: x
        permissions = (("add_cluster_tool_deposition", _("Can add cluster tool depositions")),
                       ("edit_permissions_for_cluster_tool_deposition",
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                        _("Can edit perms for cluster tool I depositions")),
                       ("view_every_cluster_tool_deposition", _("Can view all cluster tool depositions")),
                       ("edit_every_cluster_tool_deposition", _("Can edit all cluster tool depositions")))

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
                layer = layer.clustertoolhotwirelayer
                layer.type = "hot-wire"
            except ClusterToolHotWireLayer.DoesNotExist:
                layer = layer.clustertoolpecvdlayer
                layer.type = "PECVD"
            layers.append(layer)
        context["layers"] = layers
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_cluster_tool_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(ClusterToolDeposition, self).get_context_for_user(user, context)

    def get_data_for_table_export(self):
        _ = ugettext
        data_node = super(ClusterToolDeposition, self).get_data_for_table_export()
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

        :rtype: ``jb_common.search.SearchTreeNode``
        """
        model_field = super(ClusterToolDeposition, cls).get_search_tree_node()
        model_field.related_models.update({ClusterToolHotWireLayer: "layers", ClusterToolPECVDLayer: "layers"})
        del model_field.related_models[ClusterToolLayer]
        return model_field

samples.models.depositions.default_location_of_deposited_samples[ClusterToolDeposition] = \
    _("cluster tool deposition lab")


@python_2_unicode_compatible
class ClusterToolLayer(samples.models.depositions.Layer, jb_common_models.PolymorphicModel):
    """Model for a layer of the “cluster tool”.  Note that this is the common
    base class for the actual layer models `ClusterToolHotWireLayer` and
    `ClusterToolPECVDLayer`.  This is *not* an abstract model though because
    it needs to be back-referenced from the deposition.  I need inheritance and
    polymorphism here because cluster tools may have layers with very different
    fields.
    """
    deposition = models.ForeignKey(ClusterToolDeposition, related_name="layers", verbose_name=_("deposition"))

    class Meta(samples.models.depositions.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("cluster tool layer")
        verbose_name_plural = _("cluster tool layers")

    def __str__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)


cluster_tool_wire_material_choices = (
    ("unknown", _("unknown")),
    ("rhenium", _("rhenium")),
    ("tantalum", _("tantalum")),
    ("tungsten", _("tungsten")),
)
class ClusterToolHotWireLayer(ClusterToolLayer, ClusterToolHotWireAndPECVDGases):
    """Model for a hot-wire layer in the cluster tool.  We have no
    “chamber” field here because there is only one hot-wire chamber anyway.
    """
    time = models.CharField(_("deposition time"), max_length=9, help_text=_("format HH:MM:SS"), blank=True)
    comments = models.TextField(_("comments"), blank=True)
    wire_material = models.CharField(_("wire material"), max_length=20, choices=cluster_tool_wire_material_choices)
    base_pressure = models.FloatField(_("base pressure"), help_text=in_("mbar"), null=True, blank=True)

    class Meta(ClusterToolLayer.Meta):
        verbose_name = _("cluster tool hot-wire layer")
        verbose_name_plural = _("cluster tool hot-wire layers")


    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = samples.models.depositions.Layer.get_data_for_table_export(self)
        data_node.items = [DataItem(_("time"), self.time),
                            DataItem(_("comments"), self.comments),
                            DataItem(_("wire material"), self.get_wire_material_display()),
                            DataItem(_("base pressure") + "/mbar", self.base_pressure)]
        data_node.items.extend(ClusterToolHotWireAndPECVDGases.get_data_items_for_table_export(self))
        return data_node


cluster_tool_pecvd_chamber_choices = (
    ("#1", "#1"),
    ("#2", "#2"),
    ("#3", "#3"),
)
class ClusterToolPECVDLayer(ClusterToolLayer, ClusterToolHotWireAndPECVDGases):
    """Model for a PECDV layer in the cluster tool.
    """
    chamber = models.CharField(_("chamber"), max_length=5, choices=cluster_tool_pecvd_chamber_choices)
    time = models.CharField(_("deposition time"), max_length=9, help_text=_("format HH:MM:SS"), blank=True)
    comments = models.TextField(_("comments"), blank=True)
    plasma_start_with_shutter = models.BooleanField(_("plasma start with shutter"), default=False)
    deposition_power = models.DecimalField(_("deposition power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text=in_("W"))


    class Meta(ClusterToolLayer.Meta):
        verbose_name = _("cluster tool PECVD layer")
        verbose_name_plural = _("cluster tool PECVD layers")


    def get_data_for_table_export(self):
        _ = ugettext
        # See `Layer.get_data_for_table_export` for the documentation.
        data_node = samples.models.depositions.Layer.get_data_for_table_export(self)
        data_node.items = [DataItem(_("chamber"), self.get_chamber_display()),
                            DataItem(_("time"), self.time),
                            DataItem(_("comments"), self.comments),
                            DataItem(_("plasma start with shutter"), _("yes") if self.plasma_start_with_shutter else _("no")),
                            DataItem(_("deposition power") + "/W", self.deposition_power), ]
        data_node.items.extend(ClusterToolHotWireAndPECVDGases.get_data_items_for_table_export(self))
        return data_node



class FiveChamberDeposition(samples.models.depositions.Deposition):
    """5-chamber depositions.
    """
    class Meta(samples.models.depositions.Deposition.Meta):
        verbose_name = _("5-chamber deposition")
        verbose_name_plural = _("5-chamber depositions")
        _ = lambda x: x
        permissions = (("add_five_chamber_deposition", _("Can add 5-chamber depositions")),
                       # Translators: Don't abbreviate "perms" in translation
                       # (not even to English)
                       ("edit_permissions_for_five_chamber_deposition", _("Can edit perms for 5-chamber depositions")),
                       ("view_every_five_chamber_deposition", _("Can view all 5-chamber depositions")),
                       ("edit_every_five_chamber_deposition", _("Can edit all 5-chamber depositions")))

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.core.urlresolvers.reverse("add_five_chamber_deposition"), urlquote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super(FiveChamberDeposition, self).get_context_for_user(user, context)


samples.models.depositions.default_location_of_deposited_samples[FiveChamberDeposition] = _("5-chamber deposition lab")


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

@python_2_unicode_compatible
class FiveChamberLayer(samples.models.depositions.Layer):
    """One layer in a 5-chamber deposition.
    """
    deposition = models.ForeignKey(FiveChamberDeposition, related_name="layers", verbose_name=_("deposition"))
    layer_type = models.CharField(_("layer type"), max_length=2, choices=five_chamber_layer_type_choices, blank=True)
    chamber = models.CharField(_("chamber"), max_length=2, choices=five_chamber_chamber_choices)
    sih4 = models.DecimalField("SiH₄", max_digits=7, decimal_places=3, help_text=in_("sccm"), null=True, blank=True)
    h2 = models.DecimalField("H₂", max_digits=7, decimal_places=3, help_text=in_("sccm"), null=True, blank=True)
    temperature_1 = models.DecimalField(_("temperature 1"), max_digits=7, decimal_places=3, help_text=in_("℃"), null=True, blank=True)
    temperature_2 = models.DecimalField(_("temperature 2"), max_digits=7, decimal_places=3, help_text=in_("℃"), null=True, blank=True)

    class Meta(samples.models.depositions.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("5-chamber layer")
        verbose_name_plural = _("5-chamber layers")

    def __str__(self):
        _ = ugettext
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(FiveChamberLayer, self).get_data_for_table_export()
        if self.sih4 and self.h2:
            silane_normalized = 0.6 * float(self.sih4)
            silane_concentration = silane_normalized / (silane_normalized + float(self.h2)) * 100
        else:
            silane_concentration = 0
        data_node.items.extend([DataItem(_("layer type"), self.get_layer_type_display()),
                                DataItem(_("chamber"), self.get_chamber_display()),
                                DataItem("SiH₄/sccm", self.sih4),
                                DataItem("H₂/sccm", self.h2),
                                DataItem("SC/%", "{0:5.2f}".format(silane_concentration)),
                                DataItem("T/℃ (1)", self.temperature_1),
                                DataItem("T/℃ (2)", self.temperature_2)])
        return data_node
