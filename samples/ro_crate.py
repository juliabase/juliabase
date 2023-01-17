# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2023 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""Auxiliary files for creating RO-Crates.  We write RO-Crates in a ZIP
container, in compliance with the recommendations of the `ELN Consortium`_.
Note that currently, only one sample per crate is allowed.  Neither can you
include more than one sample to a crate, now can you add only a single process
to it.

.. _ELN Consotium: https://github.com/TheELNConsortium/TheELNFileFormat/blob/master/SPECIFICATION.md
"""

import tempfile, subprocess, urllib.request, datetime, json
from pathlib import Path
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF
from django.http import StreamingHttpResponse
from django.conf import settings
from samples import ontology_symbols


vocabulary_url = "https://w3id.org/ro/crate/1.1/context/"
vocabulary = json.load(urllib.request.urlopen(vocabulary_url[:-1]))["@context"]
reverse_vocabulary = {value: key for key, value in vocabulary.items()}


def add_metadata_file_descriptor(graph):
    """Adds triples to `graph` that describe the top-level metadata file
    ``ro-crate-metadata.json`` itself.  This is kind of self-referencing since
    these triples will end up in ``ro-crate-metadata.json`` in the final ZIP
    but there we go.

    :param rdflib.Graph graph: graph to which the process data should be added
    """
    subject = URIRef("ro-crate-metadata.json")
    graph.add((subject, RDF.type, URIRef("http://schema.org/CreativeWork")))
    graph.add((subject, URIRef("http://schema.org/dateCreated"), Literal(datetime.datetime.now(datetime.timezone.utc))))
    graph.add((subject, URIRef("http://purl.org/dc/terms/conformsTo"), URIRef("https://w3id.org/ro/crate/1.1")))
    graph.add((subject, URIRef("http://schema.org/about"), URIRef("./")))


def add_license(graph, data_entity, uri, name, description):
    """Add licence infoemation to the given `graph`.  RO-Create needs the link
    to the licence’s URI but also the licence information in more detail as a
    seperate set of triples.

    :param rdflib.Graph graph: graph to which the licence data should be added
    :param rdflib.term.URIRef data_entity: the graph node of the data entity
       (in the RO-Crate sense) the licence should be applied to
    :param str uri: URI of the licence
    :param str name: concise name of the licence
    :param str description: short description of the licence, or longer name
    """
    uri = URIRef(uri)
    graph.add((data_entity, URIRef("http://schema.org/license"), uri))
    graph.add((uri, RDF.type, URIRef("http://schema.org/CreativeWork")))
    graph.add((uri, URIRef("http://schema.org/name"), Literal(name)))
    graph.add((uri, URIRef("http://schema.org/description"), Literal(description)))

def add_root_data_entity(graph, sample_node, sample_name):
    """Add the root data entity ``"./"`` to `graph`.  “Root data entity” is a
    term from RO-Crate.

    :param rdflib.Graph graph: graph to which the root data entity should be
       added
    :param rdflib.term.URIRef sample_node: the graph node of the sample the
       create is of
    :param str sample_name: the name of the sample the create is of
    """
    subject = URIRef("./")
    graph.add((subject, RDF.type, URIRef("http://schema.org/Dataset")))
    graph.add((subject, URIRef("http://schema.org/name"), Literal(sample_name)))
    graph.add((subject, URIRef("http://schema.org/description"), Literal(f"All data for the sample {sample_name}")))
    graph.add((subject, URIRef("http://schema.org/datePublished"),
               Literal(datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds"))))
    add_license(graph, subject, "https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0",
                "Creative Commons Attribution 4.0 International License")
    graph.add((subject, URIRef("http://schema.org/mainEntity"), sample_node))


def normalize_graph_for_ro_crate(local_prefix, graph):
    """Returns a graph equivalent to the given `graph` with the following
    properties:

    1. All URIs from the `RO-Crate context`_ are replaced by their short form.
    2. For all JuliaBase instance URIs, the prefixes are collected so that the
       resulting JSON-LD can be much shorter.

    .. _RO-Crate context: https://www.researchobject.org/ro-crate/1.1/context.jsonld

    :param str local_prefix: Common URI prefix of the current JuliaBase
       instance, ending in a slash.  This typically is
       `settings.GRAPH_NAMESPACE_PREFIX`.
    :param rdflib.Graph graph: graph which should be normalised; it is not
       changed

    :returns:
       new graph with the above-mentioned properties

    :rtype: rdflib.Graph graph
    """
    result = Graph()
    namespaces = set()
    for triple in graph:
        new_triple = []
        for item in triple:
            if not isinstance(item, URIRef):
                new_triple.append(item)
                continue
            uri = str(item)
            if uri.startswith(local_prefix):
                namespace, hash_, _ = uri.rpartition("#")
                if hash_:
                    namespaces.add(namespace + hash_)
                else:
                    namespace, slash, _ = uri.rpartition("/")
                    assert slash
                    namespaces.add(namespace + slash)
            else:
                prefix, schema, path = uri.partition("https://")
                if not prefix and schema:
                    normalized_uri = "http://" + path
                else:
                    normalized_uri = uri
                ro_crate_name = reverse_vocabulary.get(normalized_uri)
                uri = vocabulary_url + ro_crate_name if ro_crate_name else uri
            new_triple.append(URIRef(uri))
        result.add(tuple(new_triple))
    return result, {f"ns{i}": namespace for i, namespace in enumerate(namespaces)}


class ZipStream:
    """Iterator class that zips a temporary directory and iterates over the
    zipped byte stream.  After the iterating is done, the temporary directory
    is deleted.
    """

    def __init__(self, tempdir):
        """Class constructor.

        :param tempfile.TemporaryDirectory tempdir: directory with the files
           that are supposed to be zipped
        """
        self.tempdir = tempdir
        self.process = subprocess.Popen(["zip", "-r", "-", "."], cwd=tempdir.name,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def __iter__(self):
        return self

    def __next__(self):
        data = self.process.stdout.read(1024*1024)
        if not data:
            self.tempdir.cleanup()
            assert self.process.wait() == 0
            raise StopIteration
        return data


def respond_as_ro_crate(graph, raw_files):
    """Returns an HTTP response object serving the RO-Crate of the given sample
    `graph`.  Note that for efficiency reasons, this graph is changed in place,
    so the caller should not use the graph any more.

    :param rdflib.Graph graph: graph of the sample
    :param set[RawFile] raw_files: all raw files of the sample’s processes

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    state_triples = list(graph.triples((None, ontology_symbols.scimesh.state, None)))
    assert len(state_triples) == 1, len(state_triples)
    sample_node = state_triples[0][0]
    __, slash, sample_name_raw = sample_node.rpartition("/")
    assert slash and sample_name_raw, sample_node
    sample_name = urllib.parse.unquote(sample_name_raw)

    add_metadata_file_descriptor(graph)
    add_root_data_entity(graph, sample_node, sample_name)
    graph, namespaces = normalize_graph_for_ro_crate(settings.GRAPH_NAMESPACE_PREFIX, graph)

    tempdir = tempfile.TemporaryDirectory()
    tempdir_path = Path(tempdir.name)

    metadata = graph.serialize(format="json-ld", context={"@vocab": vocabulary_url,
                                                          "sm": "http://scimesh.org/SciMesh/",
                                                          "time": "http://www.w3.org/2006/time#",
                                                          "jb-s": "http://juliabase.org/jb/Sample#",
                                                          "jb-p": "http://juliabase.org/jb/Process#",
                                                          "xmls": "http://www.w3.org/2001/XMLSchema#"} | namespaces,
                               auto_compact=True)
    open(tempdir_path/"ro-crate-metadata.json", "w").write(metadata)

    for raw_file in raw_files:
        raw_file.prepare_destination(tempdir_path)

    zip_stream = ZipStream(tempdir)
    return StreamingHttpResponse(zip_stream, "application/rocrate+zip",
                                 headers={"Content-Disposition": f'attachment; filename="{sample_name}.eln"'})
