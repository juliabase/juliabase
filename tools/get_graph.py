#!/usr/bin/env python

import sys, argparse, json
from pathlib import Path
from rdflib import Graph, URIRef, BNode, Literal
sys.path.append(str(Path(__file__).parent.parent/"remote_client"))
from jb_remote_inm import *


vocabulary_url = "https://w3id.org/ro/crate/1.1/context/"
vocabulary = json.load(urllib.request.urlopen(vocabulary_url[:-1]))["@context"]
reverse_vocabulary = {value: key for key, value in vocabulary.items()}


def normalize_graph_for_ro_crate(local_prefix, graph):
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
                    uri = "http://" + path
                ro_crate_name = reverse_vocabulary.get(uri)
                uri = vocabulary_url + ro_crate_name if ro_crate_name else uri
            new_triple.append(URIRef(uri))
        result.add(tuple(new_triple))
    return result, {f"ns{i}": namespace for i, namespace in enumerate(namespaces)}

parser = argparse.ArgumentParser(description="Get serialised RDF graphs of a sample in a demo JuliaBase.")
parser.add_argument("username", help="login name of the user in JuliaBase")
parser.add_argument("sample", help="name of the sample to get the graph of")
parser.add_argument("--password", default="12345", help="login name of the user in JuliaBase")
parser.add_argument("--base-url", default="http://localhost:8000/", help="Base URL of the JuliaBase demo instance")
parser.add_argument("--output-format", choices=("turtle", "json-ld", "xml"), default="turtle", help="serialisation format")
args = parser.parse_args()


settings.ROOT_URL = settings.TESTSERVER_ROOT_URL = args.base_url

setup_logging("console")
login(args.username, args.password)
graph = connection.open_graph("samples/" + args.sample)
match args.output_format:
    case "json-ld":
        graph, namespaces = normalize_graph_for_ro_crate("http://inm.example.com/", graph)
        result = graph.serialize(format="json-ld", context={"@vocab": vocabulary_url,
                                                            "sm": "http://scimesh.org/SciMesh/",
                                                            "time": "http://www.w3.org/2006/time#",
                                                            "jb-s": "http://juliabase.org/jb/Sample#",
                                                            "jb-p": "http://juliabase.org/jb/Process#",
                                                            "xmls": "http://www.w3.org/2001/XMLSchema#"} | namespaces,
                                 auto_compact=True)
    case _:
        result = graph.serialize(format=args.output_format)
print(result)
logout()
