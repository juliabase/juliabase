# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2022 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Models for depositions.  This includes the deposition models themselves as
well as models for layers.

:type default_location_of_deposited_samples: dict mapping `Deposition` to
  string.
"""

from django.utils.translation import gettext_lazy as _, gettext
from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from jb_common import search, model_fields
from samples import ontology_symbols
from samples.models import PhysicalProcess, fields_to_data_items, remove_data_item
from samples.models.common import GraphEntity
from samples.data_tree import DataNode, DataItem


default_location_of_deposited_samples = {}
"""Dictionary mapping process classes to strings which contain the default
location where samples can be found after this process has been performed.
This is used in
:py:meth:`samples.views.split_after_deposition.GlobalNewDataForm.__init__`.
"""


class Deposition(PhysicalProcess):
    """The base class for deposition processes.  Note that, like
    `~samples.models.Process`, this must never be instantiated.  Instead,
    derive the concrete deposition class from it.

    It is only sensible to use this class if your institution has
    institution-wide unique deposition numbers.  Else, make distict model
    classes for each deposition system which are not derived from
    ``Deposition``, and don't use the `Layer` class below then either.

    Every derived class, if it has sub-objects which resemble layers, must
    implement them as a class derived from `Layer`, with a ``ForeignKey`` field
    pointing to the deposition class with ``relative_name="layers"``.  In other
    words, ``instance.layers.all()`` must work if ``instance`` is an instance
    of your deposition class.
    """
    number = model_fields.CharField(_("deposition number"), max_length=15, unique=True, db_index=True)
    split_done = model_fields.BooleanField(_("split after deposition done"), default=False)

    class Meta(PhysicalProcess.Meta):
        verbose_name = _("deposition")
        verbose_name_plural = _("depositions")

    class JBMeta:
        identifying_field = "number"

    def get_steps(self):
        """Returns all layers of this deposition as a query set.

        :return:
          all layers of this deposition

        :rtype: ``django.db.models.query.QuerySet``
        """
        return self.layers

    def _get_layers(self):
        """Retrieves all layers of this deposition.  This function can deal with
        polymorphic layer classes as well as with the possibility that the
        deposition class doesn't have an associated layer class at all.

        :return:
          all layers of this deposition

        :rtype: list of `Layer`.
        """
        layers = []
        try:
            all_layers = self.layers.all()
        except AttributeError:
            pass
        else:
            for layer in all_layers:
                try:
                    # For deposition systems with polymorphic layers
                    layer = layer.actual_instance
                except AttributeError:
                    pass
                layers.append(layer)
        return layers

    def get_data(self):
        """Extract the data of the deposition as a dictionary, ready to be used for
        general data export.  In contrast to `get_data_for_table_export`, I
        export all fields automatically of the instance, including foreign
        keys.  The layers, together with their data, is included in the keys
        ``"layer {number}"``.  Typically, this data is used when a non-browser
        client retrieves a single resource and expects JSON output.

        You will rarely need to override this method.

        :return:
          the content of all fields of this deposition

        :rtype: `dict`
        """
        data = super().get_data()
        del data["deposition_ptr"]
        for layer in self._get_layers():
            layer_data = layer.get_data()
            for key in list(layer_data):
                if key in {"deposition", "actual_object_id"} or key.endswith("_ptr"):
                    del layer_data[key]
            data["layer {}".format(layer.number)] = layer_data
        return data

    def add_merge_process_to_graph(self, graph, sample):
        """Additionally to the parent method, we create a “cause” relation from
        the merge process to the latest layer.  Moreover, we make sure that
        there is *always* a merge node, even if there is only one sample in
        this process, because be need it due to the concurrency between layers
        and the common process.

        :param rdflib.Graph graph: graph to which the process data should be
          added
        :param Sample sample: Names of fields that should not be added to the
          graph.  Typically, the more specialised caller has already dealt with
          them.

        :return:
          graph containing also the data of this process instance

        :rtype: rdflib.Graph
        """
        effect_node, cause_node = super().add_merge_process_to_graph(graph, sample)
        try:
            last_layer = self.layers.last()
        except AttributeError as error:
            # FixMe: Remove the following line from Python 3.10 onwards.
            return effect_node, cause_node
            if error.name == "layers":
                return effect_node, cause_node
            else:
                raise
        except ObjectDoesNotExist:
            return effect_node, cause_node
        else:
            try:
                last_layer = last_layer.actual_instance
            except AttributeError:
                pass
            process_uri = self.uri()
            if cause_node == process_uri:
                merge_node = process_uri + f"#sample-{sample.id}"
                graph.add((merge_node, ontology_symbols.RDF.type, ontology_symbols.scimesh.Process))
                graph.add((merge_node, ontology_symbols.RDF.type, ontology_symbols.scimesh.State))
                graph.add((merge_node, ontology_symbols.scimesh.cause, process_uri))
                cause_node = merge_node
            else:
                merge_node = cause_node
            graph.add((merge_node, ontology_symbols.scimesh.cause, last_layer.uri()))
        return effect_node, cause_node

    def add_to_graph(self, graph, excluded_fields=frozenset()):
        """Additionally to what is done in the parent method, we add the layers
        to the graph.

        :param rdflib.Graph graph: graph to which the process data should be
          added
        :param set[str] excluded_fields: Names of fields that should not be
          added to the graph.  Typically, the more specialised caller has
          already dealt with them.
        """
        super().add_to_graph(graph, excluded_fields)
        process_uri = self.uri()
        latest_layer = None
        for layer in self._get_layers():
            layer_uri = layer.uri()
            layer.add_to_graph(graph)
            graph.add((layer_uri, ontology_symbols.scimesh.cause, process_uri))
            if latest_layer is not None:
                graph.add((layer_uri, ontology_symbols.scimesh.cause, latest_layer))
            latest_layer = layer_uri

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        data_node = super().get_data_for_table_export()
        remove_data_item(self, data_node, "split_done")
        for layer in self._get_layers():
            data_node.children.append(layer.get_data_for_table_export())
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        if cls == Deposition:
            # So that only derived classes get included into the searchable
            # models in the advanced search
            raise NotImplementedError
        model_field = super().get_search_tree_node()
        return model_field


class Layer(models.Model, GraphEntity):
    """This is an abstract base model for deposition layers.  Now, this is the
    first *real* abstract model here.  It is abstract because it can never
    occur in a model relationship.  It just ensures that every layer has a
    number, because at least the MyLayers infrastructure relies on this.  (See
    for example
    :py:meth:`institute.views.five_chamber_deposition.FormSet.__change_structure`,
    after ``if my_layer:``.)

    Note that the above is slightly untrue for cluster tool layers because they
    must be polymorphic.  There, I need a *concret* base class for all layer
    models, derived from this one.

    Every class derived from this model must point to their deposition with
    ``related_name="layers"``.  See also `Deposition`.  Additionally, the
    ``Meta`` class should contain::

        class Meta(Layer.Meta):
            unique_together = ("deposition", "number")
    """
    number = model_fields.PositiveIntegerField(_("layer number"))

    class Meta:
        abstract = True
        ordering = ["number"]
        verbose_name = _("layer")
        verbose_name_plural = _("layers")

    def __str__(self):
        return _("layer {number} of {deposition}").format(number=self.number, deposition=self.deposition)

    def get_data(self):
        """Extract the data of this layer as a dictionary, ready to be used for general
        data export.  In contrast to `get_data_for_table_export`, I export all
        fields automatically of the layer, including foreign keys.  It does
        not, however, include reverse relations.  This method is only called
        from the ``get_data()`` method of the respective deposition, which in
        turn mostly is :py:meth:`Deposition.get_data` (i.e., not overridden).

        You will rarely need to override this method in derived layer classes.

        :return:
          the content of all fields of this layer

        :rtype: `dict`
        """
        return {field.name: getattr(self, field.name) for field in self._meta.fields}

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        data_node = DataNode(self, _("layer {number}").format(number=self.number))
        fields_to_data_items(self, data_node, {"deposition"})
        return data_node

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


_ = gettext
