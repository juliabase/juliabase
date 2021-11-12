# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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

from rdflib.namespace import Namespace, DCAT, FOAF, OWL, PROV, RDF, RDFS
from rdflib import URIRef, BNode, Literal


BFO = Namespace("http://purl.obolibrary.org/obo/")
OBI = Namespace("http://purl.obolibrary.org/obo/")
OMIT = Namespace("http://purl.obolibrary.org/obo/")
TI = Namespace("https://www.w3.org/TR/owl-time/#")
JB = Namespace("http://juliabase.org/jb#")
JB_sample = Namespace("http://juliabase.org/jb/Sample#")

planned_process = OBI.OBI_0000011
has_specified_input = OBI.OBI_0000293
has_specified_output = OBI.OBI_0000299
is_specified_input_of = OBI.OBI_0000295
is_specified_output_of = OBI.OBI_0000312
realizes = BFO.BFO_0000055
realized_in = BFO.BFO_0000054
