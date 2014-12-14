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


"""Models for depositions.  This includes the deposition models themselves as
well as models for layers.

:type default_location_of_deposited_samples: dict mapping `Deposition` to
  string.
"""

from __future__ import absolute_import, unicode_literals
from django.utils.encoding import python_2_unicode_compatible

from django.utils.translation import ugettext_lazy as _, ugettext
import django.core.urlresolvers
from django.db import models
from samples.models.common import PhysicalProcess
from samples.data_tree import DataNode, DataItem
from jb_common import search

default_location_of_deposited_samples = {}
"""Dictionary mapping process classes to strings which contain the default
location where samples can be found after this process has been performed.
This is used in
`samples.views.split_after_deposition.GlobalNewDataForm.__init__`.
"""


@python_2_unicode_compatible
class Deposition(PhysicalProcess):
    """The base class for deposition processes.  Note that, like `Process`,
    this must never be instantiated.  Instead, derive the concrete deposition
    class from it.  (By the way, this is the reason why this class needn't
    define a ``get_add_link`` method.)

    It is only sensible to use this class if your institution has
    institution-wide unique deposition numbers.  Else, make distict model
    classes for each deposition system which are not derived from `Deposition`,
    and don't use the `Layer` class below then either.

    Every derived class, if it has sub-objects which resemble layers, must
    implement them as a class derived from `Layer`, with a ``ForeignKey`` field
    pointing to the deposition class with ``relative_name="layers"``.  In other
    words, ``instance.layers.all()`` must work if ``instance`` is an instance
    of your deposition class.
    """
    number = models.CharField(_("deposition number"), max_length=15, unique=True, db_index=True)
    split_done = models.BooleanField(_("split after deposition done"), default=False)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("deposition")
        verbose_name_plural = _("depositions")

    class JBMeta:
        identifying_field = "number"

    def get_absolute_url(self):
        return django.core.urlresolvers.reverse("samples.views.main.show_deposition", args=(self.number,))

    def __str__(self):
        _ = ugettext
        return _("deposition {number}").format(number=self.number)

    def get_data(self):
        """Extract the data of the deposition as a dictionary, ready to be used for
        general data export.  In contrast to `get_data_for_table_export`, I
        export all fields automatically of the instance, including foreign
        keys.  The layers, together with their data, is included in the keys
        ``"layer {number}"``.  Typically, this data is used when a non-browser
        client retrieves a single resource and expects JSON output.

        You will rarely need to override this method.

        :Return:
          the content of all fields of this deposition

        :rtype: `dict`
        """
        data = super(Deposition, self).get_data()
        del data["deposition_ptr"]
        for layer in self.layers.all():
            try:
                # For deposition systems with polymorphic layers
                layer = layer.actual_instance
            except AttributeError:
                pass
            layer_data = layer.get_data()
            for key in list(layer_data):
                if key in {"deposition", "actual_object_id"} or key.endswith("_ptr"):
                    del layer_data[key]
            data["layer {}".format(layer.number)] = layer_data
        return data

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = super(Deposition, self).get_data_for_table_export()
        data_node.items.append(DataItem(_("number"), self.number, "deposition"))
        data_node.children = [layer.get_data_for_table_export() for layer in self.layers.all()]
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :Return:
          the tree node for this model instance

        :rtype: ``jb_common.search.SearchTreeNode``
        """
        if cls == Deposition:
            # So that only derived classes get included into the searchable
            # models in the advanced search
            raise NotImplementedError
        model_field = super(Deposition, cls).get_search_tree_node()
        return model_field


class Layer(models.Model):
    """This is an abstract base model for deposition layers.  Now, this is the
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
    number = models.PositiveIntegerField(_("layer number"))

    class Meta:
        abstract = True
        ordering = ["number"]
        verbose_name = _("layer")
        verbose_name_plural = _("layers")

    def get_data(self):
        """Extract the data of this layer as a dictionary, ready to be used for general
        data export.  In contrast to `get_data_for_table_export`, I export all
        fields automatically of the layer, including foreign keys.  It does
        not, however, include reverse relations.  This method is only called
        from the ``get_data()`` method of the respective deposition, which in
        turn mostly is `Deposition.get_data` (i.e., not overridden).

        You will rarely need to override this method in derived layer classes.

        :Return:
          the content of all fields of this layer

        :rtype: `dict`
        """
        return {field.name: getattr(self, field.name) for field in self._meta.fields}

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        _ = ugettext
        data_node = DataNode(self, _("layer {number}").format(number=self.number))
        data_node.items = [DataItem(_("number"), self.number, "layer")]
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :Return:
          the tree node for this model instance

        :rtype: ``jb_common.search.SearchTreeNode``
        """
        search_fields = search.convert_fields_to_search_fields(cls)
        return search.SearchTreeNode(cls, {}, search_fields)
