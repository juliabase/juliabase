# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2021 Forschungszentrum Jülich GmbH, Jülich, Germany
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

"""Django model field classes for generating RDF graphs.  The triples created
for the graph have the following structure:

subject
  The URI to the model instance.  Mostly, it will be the URL to the view of the
  instance, i.e. where you can get all the data of it.

predicate
  The URI to the field of that model.  It does not resolve.  It is not a
  working URL.  It has the format ``ClassURI/fieldName``.

object
  The value literal for the field, or the URI of the graph containing the value
  (e.g. in case of compound data structures)

Example triple::

    <http://inm.example.com/substrates/34>
    <http://inm.example.com/Substrate/wafer_type>
    "Si"

"""

import datetime
import rdflib
from django.db import models
from .base import underscores_to_camel_case


class GraphField:

    def uri(self):
        """Returns the URI of this field, in this class.  It is supposed to be used as
        an RDF property.

        :returns:
          The URI of this field in its class.  Thus, the result does not point
          to a concrete model instance but to one of its fields per se.

        :rtype: `rdflib.term.URIRef`
        """
        return self.model.uri_namespace()[self.model.__name__ + "/" +
                                          underscores_to_camel_case(self.name, force_lower=True)]

    def add_to_graph(self, graph, instance):
        """Adds triples for the field to the given graph.

        :param rdflib.Graph graph: graph to add triples to; this is modifield
          in place
        :param django.db.models.Model instance: model instance this field
          belongs to
        """
        value = getattr(instance, self.name)
        assert isinstance(value, (int, float, str, bool, datetime.datetime))
        graph.add((instance.uri(), self.uri(), rdflib.term.Literal(value)))


class CharField(GraphField, models.CharField):
    pass

class DateTimeField(GraphField, models.DateTimeField):
    pass
