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


u"""Models for depositions.  This includes the deposition models themselves as
well as models for layers.

:type default_location_of_deposited_samples: dict mapping `Deposition` to
  string.
"""

from __future__ import absolute_import

from django.utils.translation import ugettext_lazy as _, ugettext
import django.core.urlresolvers
from django.utils.http import urlquote, urlquote_plus
from django.db import models
from samples.models_common import PhysicalProcess
from samples.data_tree import DataNode, DataItem
from chantal_common import search

default_location_of_deposited_samples = {}
u"""Dictionary mapping process classes to strings which contain the default
location where samples can be found after this process has been performed.
This is used in
`samples.views.split_after_deposition.GlobalNewDataForm.__init__`.
"""


class Deposition(PhysicalProcess):
    u"""The base class for deposition processes.  Note that, like `Process`,
    this must never be instantiated.  Instead, derive the concrete deposition
    class from it.  (By the way, this is the reason why this class needn't
    define a ``get_add_link`` method.)

    Every derived class, if it has sub-objects which resemble layers, must
    implement them as a class derived from `Layer`, with a ``ForeignKey`` field
    pointing to the deposition class with ``relative_name="layers"``.  In other
    words, ``instance.layers.all()`` must work if ``instance`` is an instance
    of your deposition class.

    The ``sample_positions`` field may be used by derived models for storing
    where the samples were mounted during the deposition.  Sometimes it is
    interesting to know that because the deposition device may not work
    homogeneously.  It is placed here in order to be able to extend the
    split-after-deposition view so that it offers input fields for it if it is
    applicable.  (For example, this can be given in the query string.)
    """
    number = models.CharField(_(u"deposition number"), max_length=15, unique=True, db_index=True)
    sample_positions = models.TextField(_(u"sample positions"), blank=True)
    """In JSON format, mapping sample IDs to positions.  Positions can be
    numbers or strings."""

    class Meta(PhysicalProcess.Meta):
        verbose_name = _(u"deposition")
        verbose_name_plural = _(u"depositions")

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.main.show_deposition", [urlquote(self.number, safe="")])

    def __unicode__(self):
        _ = ugettext
        return _(u"deposition {number}").format(number=self.number)

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(Deposition, self).get_data()
        data_node.items.append(DataItem(u"number", self.number, "deposition"))
        data_node.children = [layer.get_data() for layer in self.layers.all()]
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(Deposition, self).get_data_for_table_export()
        data_node.items.append(DataItem(_(u"number"), self.number, "deposition"))
        data_node.children = [layer.get_data_for_table_export() for layer in self.layers.all()]
        return data_node


class Layer(models.Model):
    u"""This is an abstract base model for deposition layers.  Now, this is the
    first *real* abstract model here.  It is abstract because it can never
    occur in a model relationship.  It just ensures that every layer has a
    number, because at least the MyLayers infrastructure relies on this.  (See
    for example `views.six_chamber_deposition.FormSet.__change_structure`,
    after ``if my_layer:``.)

    Note that the above is slightly untrue for cluster tool layers because they
    must be polymorphic.  There, I need a *concret* base class for all layer
    models, derived from this one.  However, I consider this a rim case.  But
    this is debatable: Maybe it's cleaner to make this class concrete.  The
    only drawback would be that in order to access the layer attributes, one
    would have to visit the layer instance explicitly with e.g.

    ::

        six_chamber_deposition.layers.all()[0].six_chamber_layer.temperature

    Every class derived from this model must point to their deposition with
    ``related_name="layers"``.  See also `Deposition`.  Additionally, the
    ``Meta`` class should contain::

        class Meta(Layer.Meta):
            unique_together = ("deposition", "number")
    """
    number = models.PositiveIntegerField(_(u"layer number"))

    class Meta:
        abstract = True
        ordering = ["number"]
        verbose_name = _(u"layer")
        verbose_name_plural = _(u"layers")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = DataNode(u"layer {0}".format(self.number))
        data_node.items = [DataItem(u"number", self.number, "layer")]
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = DataNode(self, _(u"layer {number}").format(number=self.number))
        data_node.items = [DataItem(_(u"number"), self.number, "layer")]
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        search_fields = search.convert_fields_to_search_fields(cls)
        return search.SearchTreeNode(cls, {}, search_fields)
