#!/bin/sh
set -e

SCRIPT=$(realpath -e "$0")
SCRIPTPATH=$(dirname "$SCRIPT")
cd "$SCRIPTPATH"/..

trap 'handle_term' TERM INT

handle_term()
{
    if [ "$runserver_pid" ]
    then
        kill $runserver_pid
    fi
}

update() {
    ./manage.py runserver &
    runserver_pid=$!
    while ! wget -O /tmp/sample.rdf.temp --header "Accept: text/turtle" localhost:8000/samples/14S-005
    do
        sleep 1
    done
    kill $runserver_pid
    unset runserver_pid
    wait $runserver_pid
    wait $runserver_pid
    if [ -e /tmp/sample.rdf ]
    then
        diff -u /tmp/sample.rdf /tmp/sample.rdf.temp > /tmp/sample.rdf.diff.temp || true
        mv /tmp/sample.rdf.diff.temp /tmp/sample.rdf.diff
    fi
    mv /tmp/sample.rdf.temp /tmp/sample.rdf
    play --no-show-progress --null --channels 1 synth 0.2 sine 1000
}

export DJANGO_SETTINGS_MODULE=settings_test \
       JULIABASE_DB_FILENAME=juliabase-test-db-1

if [ ! -e /tmp/"$JULIABASE_DB_FILENAME" ]
then
    ./manage.py migrate
    ./manage.py loaddata test_main_1
fi

update
while :
do
    inotifywait --event modify --exclude '^\.#' -q .
    update
done
