#!/usr/bin/env python

import sys, argparse
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent/"remote_client"))
from jb_remote_inm import *


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
        result = graph.serialize(format="json-ld", auto_compact=True)
    case _:
        result = graph.serialize(format=args.output_format)
print(result)
logout()
