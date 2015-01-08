#!/bin/sh
if [ "$1" = "build_test_main" ]
then
    python five_chamber.py
    python cluster_tool.py
    python pds.py
else
    python five_chamber.py & python cluster_tool.py
    python pds.py & python solarsimulator.py
fi
