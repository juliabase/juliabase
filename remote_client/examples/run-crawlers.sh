#!/bin/sh
if [ "$JULIABASE_ACCESS_MODE" = "synchronous" ]
then
    ./five_chamber.py
    ./cluster_tool.py
    ./pds.py
else
    ./five_chamber.py & ./cluster_tool.py
    ./pds.py & ./solarsimulator.py
fi
