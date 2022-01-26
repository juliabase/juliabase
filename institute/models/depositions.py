# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


"""Models for INM-specific depositions.  This includes the deposition models
themselves as well as models for layers.
"""

import rdflib
from urllib.parse import quote_plus
from django.utils.translation import gettext_lazy as _, gettext
import django.urls
from django.db import models
from jb_common import models as jb_common_models, model_fields
from jb_common.utils.base import generate_permissions
import samples.models.depositions
from samples import permissions
from samples.data_tree import DataItem


class ClusterToolHotWireAndPECVDGases(models.Model):
    h2 = model_fields.DecimalQuantityField("H₂", max_digits=5, decimal_places=2, null=True, blank=True, unit="sccm")
    sih4 = model_fields.DecimalQuantityField("SiH₄", max_digits=5, decimal_places=2, null=True, blank=True, unit="sccm")

    class Meta:
        abstract = True


class ClusterToolDeposition(samples.models.Deposition):
    """cluster tool depositions..
    """
    carrier = model_fields.CharField(_("carrier"), max_length=10, blank=True)

    class Meta(samples.models.PhysicalProcess.Meta):
        verbose_name = _("cluster tool deposition")
        verbose_name_plural = _("cluster tool depositions")
        permissions = generate_permissions({"add", "change", "view_every", "edit_permissions"}, "ClusterToolDeposition")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.urls.reverse("institute:add_cluster_tool_deposition"), quote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super().get_context_for_user(user, context)

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.  I must override the inherited method because I want to offer
        the layer models directly instead of the proxy class
        `ClusterToolLayer`.

        :return:
          the tree node for this model instance

        :rtype: ``jb_common.search.SearchTreeNode``
        """
        model_field = super().get_search_tree_node()
        model_field.related_models.update({ClusterToolHotWireLayer: "layers", ClusterToolPECVDLayer: "layers"})
        del model_field.related_models[ClusterToolLayer]
        return model_field

samples.models.default_location_of_deposited_samples[ClusterToolDeposition] = _("cluster tool deposition lab")


class ClusterToolLayer(samples.models.Layer, jb_common_models.PolymorphicModel):
    """Model for a layer of the “cluster tool”.  Note that this is the common
    base class for the actual layer models `ClusterToolHotWireLayer` and
    `ClusterToolPECVDLayer`.  This is *not* an abstract model though because
    it needs to be back-referenced from the deposition.  I need inheritance and
    polymorphism here because cluster tools may have layers with very different
    fields.
    """
    deposition = models.ForeignKey(ClusterToolDeposition, models.CASCADE, related_name="layers", verbose_name=_("deposition"))

    class Meta(samples.models.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("cluster tool layer")
        verbose_name_plural = _("cluster tool layers")

    def __str__(self):
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)


class ClusterToolHotWireLayer(ClusterToolLayer, ClusterToolHotWireAndPECVDGases):
    """Model for a hot-wire layer in the cluster tool.  We have no
    “chamber” field here because there is only one hot-wire chamber anyway.
    """

    class ClusterToolWireMaterial(models.TextChoices):
        UNKNOWN = "unknown", _("unknown")
        RHENIUM = "rhenium", _("rhenium")
        TANTALUM = "tantalum", _("tantalum")
        TUNGSTEN = "tungsten", _("tungsten")

    time = model_fields.CharField(_("deposition time"), max_length=9, help_text=_("format HH:MM:SS"), blank=True)
    comments = model_fields.TextField(_("comments"), blank=True)
    wire_material = model_fields.CharField(_("wire material"), max_length=20, choices=ClusterToolWireMaterial.choices)
    base_pressure = model_fields.FloatQuantityField(_("base pressure"), unit="mbar", null=True, blank=True)

    class Meta(samples.models.Layer.Meta):
        verbose_name = _("cluster tool hot-wire layer")
        verbose_name_plural = _("cluster tool hot-wire layers")


class ClusterToolPECVDLayer(ClusterToolLayer, ClusterToolHotWireAndPECVDGases):
    """Model for a PECDV layer in the cluster tool.
    """

    class ClusterToolPECVDChamber(models.TextChoices):
        ONE = "#1", "#1"
        TWO = "#2", "#2"
        THREE = "#3", "#3"

    chamber = model_fields.CharField(_("chamber"), max_length=5, choices=ClusterToolPECVDChamber.choices)
    time = model_fields.CharField(_("deposition time"), max_length=9, help_text=_("format HH:MM:SS"), blank=True)
    comments = model_fields.TextField(_("comments"), blank=True)
    plasma_start_with_shutter = model_fields.BooleanField(_("plasma start with shutter"), default=False)
    deposition_power = model_fields.DecimalQuantityField(_("deposition power"), max_digits=6, decimal_places=2,
                                                         null=True, blank=True, unit="W")


    class Meta(samples.models.Layer.Meta):
        verbose_name = _("cluster tool PECVD layer")
        verbose_name_plural = _("cluster tool PECVD layers")


class FiveChamberDeposition(samples.models.Deposition):
    """5-chamber depositions.
    """
    class Meta(samples.models.PhysicalProcess.Meta):
        verbose_name = _("5-chamber deposition")
        verbose_name_plural = _("5-chamber depositions")
        permissions = generate_permissions({"add", "change", "view_every", "edit_permissions"}, "FiveChamberDeposition")

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if permissions.has_permission_to_add_physical_process(user, self.__class__):
            context["duplicate_url"] = "{0}?copy_from={1}".format(
                django.urls.reverse("institute:add_five_chamber_deposition"), quote_plus(self.number))
        else:
            context["duplicate_url"] = None
        return super().get_context_for_user(user, context)


samples.models.default_location_of_deposited_samples[FiveChamberDeposition] = _("5-chamber deposition lab")


class FiveChamberLayer(samples.models.Layer):
    """One layer in a 5-chamber deposition.
    """

    class LayerType(models.TextChoices):
        P = "p", "p"
        I = "i", "i"
        N = "n", "n"

    class Chamber(models.TextChoices):
        I1 = "i1", "i1"
        I2 = "i2", "i2"
        I3 = "i3", "i3"
        P = "p", "p"
        N = "n", "n"

    deposition = models.ForeignKey(FiveChamberDeposition, models.CASCADE, related_name="layers", verbose_name=_("deposition"))
    layer_type = model_fields.CharField(_("layer type"), max_length=2, choices=LayerType.choices, blank=True)
    chamber = model_fields.CharField(_("chamber"), max_length=2, choices=Chamber.choices)
    sih4 = model_fields.DecimalQuantityField("SiH₄", max_digits=7, decimal_places=3, unit="sccm", null=True, blank=True)
    h2 = model_fields.DecimalQuantityField("H₂", max_digits=7, decimal_places=3, unit="sccm", null=True, blank=True)
    temperature_1 = model_fields.DecimalQuantityField(_("temperature 1"), max_digits=7, decimal_places=3, unit="℃",
                                                      null=True, blank=True)
    temperature_2 = model_fields.DecimalQuantityField(_("temperature 2"), max_digits=7, decimal_places=3, unit="℃",
                                                      null=True, blank=True)

    class Meta(samples.models.Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _("5-chamber layer")
        verbose_name_plural = _("5-chamber layers")

    def __str__(self):
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def get_data_for_table_export(self):
        # See `Layer.get_data_for_table_export` for the documentation.  This is
        # a good example for adding an additional field to the table output
        # which is not a field but calculated from fields.
        data_node = super().get_data_for_table_export()
        if self.sih4 and self.h2:
            silane_normalized = 0.6 * float(self.sih4)
            silane_concentration = silane_normalized / (silane_normalized + float(self.h2)) * 100
        else:
            silane_concentration = 0
        data_node.items.append(DataItem("SC/%", "{0:5.2f}".format(silane_concentration)))
        return data_node


_ = gettext
