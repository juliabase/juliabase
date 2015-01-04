#!/bin/sh
if [ "$1" = "synchronous" ]
then
    python five_chamber.py & python cluster_tool.py
    python pds.py & python solarsimulator.py
else
    python five_chamber.py
    python cluster_tool.py
    python pds.py
    python solarsimulator.py
fi
