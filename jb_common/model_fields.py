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

import datetime, decimal
import rdflib
from django.db import models
from django.utils.translation import gettext_lazy as _, gettext
from jb_common.utils.base import underscores_to_camel_case
from samples import ontology_symbols


class GraphField:
    """Mixin class for generating RDF graphs.  The triples created for the graph
    have the following structure:

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
        if value is not None:
            assert isinstance(value, (int, float, str, bool, datetime.datetime, decimal.Decimal)), type(value)
            graph.add((instance.uri(), self.uri(), rdflib.term.Literal(value)))


class CharField(GraphField, models.CharField):
    pass

class DateField(GraphField, models.DateField):
    pass

class DateTimeField(GraphField, models.DateTimeField):
    pass

class EmailField(GraphField, models.EmailField):
    pass

class BooleanField(GraphField, models.BooleanField):
    pass

class JSONField(GraphField, models.JSONField):
    pass

class TextField(GraphField, models.TextField):
    pass

class URLField(GraphField, models.URLField):
    pass

class FloatField(GraphField, models.FloatField):
    pass

class IntegerField(GraphField, models.IntegerField):
    pass

class DecimalField(GraphField, models.DecimalField):
    pass

class PositiveIntegerField(GraphField, models.PositiveIntegerField):
    pass

class PositiveSmallIntegerField(GraphField, models.PositiveSmallIntegerField):
    pass

class SmallIntegerField(GraphField, models.SmallIntegerField):
    pass


UN_CEFACT_common_code = {
    "kg/m²": "28",
    "dB": "2N",
    "µm": "4H",
    "mA": "4K",
    "N/m": "4P",
    "cd/m²": "A24",
    "GHz": "A86",
    "g/mol": "A94",
    "kA": "B22",
    "kg • m2": "B32",
    "kJ/(kg.K)": "B43",
    "kΩ": "B49",
    "lm/W": "B61",
    "bar": "BAR",
    "mm/s": "C16",
    "mPa.s": "C24",
    "ms": "C26",
    "nm": "C45",
    "1": "C62",
    "Pa.s": "C65",
    "1/K": "C91",
    "min-1": "C94",
    "cd": "CDL",
    "°C": "CEL",
    "℃": "CEL",
    "cm³": "CMQ",
    "cm": "CMT",
    "T": "D33",
    "W/K": "D52",
    "kg/mol": "D74",
    "d": "DAY",
    "°": "DD",
    "N/cm²": "E01",
    "l/h": "E32",
    "F": "FAR",
    "g/m²": "GM",
    "g": "GRM",
    "Hz": "HTZ",
    "h": "HUR",
    "K": "KEL",
    "kg": "KGM",
    "kg/s": "KGS",
    "kHz": "KHZ",
    "kg/m": "KL",
    "kg/m³": "KMQ",
    "kV": "KVT",
    "kW": "KWT",
    "l/min": "L2",
    "l": "LTR",
    "lm": "LUM",
    "lx": "LUX",
    "mbar": "MBR",
    "MHz": "MHZ",
    "min": "MIN",
    "mm²": "MMK",
    "mm³": "MMQ",
    "mm": "MMT",
    "MPa": "MPA",
    "m3/h": "MQH",
    "m³/s": "MQS",
    "m²": "MTK",
    "m³": "MTQ",
    "m": "MTR",
    "m/s": "MTS",
    "N": "NEW",
    "N • m": "NU",
    "N.m": "NU",
    "Ω": "OHM",
    "%": "P1",
    "Pa": "PAL",
    "s": "SEC",
    "V": "VLT",
    "W": "WTT",
}


class _QuantityGraphField(GraphField):

    def __init__(self, *args, **kwargs):
        self.unit = kwargs.pop("unit", None)
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        result = super().formfield(**kwargs)
        result.unit = self.unit
        return result

    def add_to_graph(self, graph, instance):
        value = getattr(instance, self.name)
        quantitative_value = rdflib.BNode()
        graph.add((instance.uri(), self.uri(), quantitative_value))
        graph.add((quantitative_value, ontology_symbols.RDF.type, ontology_symbols.schema_org.QuantitativeValue))
        assert isinstance(value, (int, float, str, bool, datetime.datetime, decimal.Decimal)), type(value)
        graph.add((quantitative_value, ontology_symbols.schema_org.value, rdflib.term.Literal(value)))
        graph.add((quantitative_value, ontology_symbols.schema_org.unitText, rdflib.term.Literal(self.unit)))
        unit_code = UN_CEFACT_common_code.get(self.unit)
        if unit_code:
            graph.add((quantitative_value, ontology_symbols.schema_org.unitCode, rdflib.term.Literal(unit_code)))

class DecimalQuantityField(_QuantityGraphField, models.DecimalField):
    description = _("Fixed-point number in the unit of %(unit)s")

class FloatQuantityField(_QuantityGraphField, models.FloatField):
    description = _("Floating-Point number in the unit of %(unit)s")

class IntegerQuantityField(_QuantityGraphField, models.IntegerField):
    description = _("Integer in the unit of %(unit)s")

class PositiveIntegerQuantityField(_QuantityGraphField, models.PositiveIntegerField):
    description = _("Positive integer in the unit of %(unit)s")

class SmallIntegerQuantityField(_QuantityGraphField, models.SmallIntegerField):
    description = _("Small integer in the unit of %(unit)s")

class PositiveSmallIntegerQuantityField(_QuantityGraphField, models.PositiveSmallIntegerField):
    description = _("Positive small integer in the unit of %(unit)s")

_ = gettext
