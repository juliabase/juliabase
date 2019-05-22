#!/bin/bash
set -e

SCRIPT=`readlink -f "$0"`
SCRIPTPATH=`dirname "$SCRIPT"`
cd $SCRIPTPATH

if [ "$1" = "build_test_main" ]
then
    ./five_chamber.py
    ./cluster_tool.py
    ./pds.py
elif [ "$1" = "synchronous" ]
then
    ./five_chamber.py
    ./cluster_tool.py
    ./pds.py
    ./solarsimulator.py
else
    ./five_chamber.py &
    ./cluster_tool.py
    wait
    ./pds.py &
    ./solarsimulator.py
    wait
fi
