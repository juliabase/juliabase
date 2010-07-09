#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from samples.csv_common import CSVNode, CSVItem

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
    """
    number = models.CharField(_(u"deposition number"), max_length=15, unique=True, db_index=True)

    class Meta:
        verbose_name = _(u"deposition")
        verbose_name_plural = _(u"depositions")

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.main.show_deposition", [urlquote(self.number, safe="")])

    def __unicode__(self):
        _ = ugettext
        return _(u"deposition %s") % self.number

    def get_data(self):
        # See `Process.get_data` for the documentation.
        _ = ugettext
        csv_node = super(Deposition, self).get_data()
        csv_node.items.append(CSVItem(_(u"number"), self.number, "deposition"))
        csv_node.children = [layer.get_data() for layer in self.layers.all()]
        return csv_node


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
        u"""Extract the data of this layer as a CSV node with a list of
        key–value pairs, ready to be used for the CSV table export.  See the
        `samples.views.csv_export` module for all the glory details.

        :Return:
          a node for building a CSV tree

        :rtype: `samples.csv_common.CSVNode`
        """
        _ = ugettext
        csv_node = CSVNode(self, _(u"layer %d") % self.number)
        csv_node.items = [CSVItem(_(u"number"), unicode(self.number), "layer")]
        return csv_node
