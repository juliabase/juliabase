#!/bin/sh

SCRIPT=`readlink -f "$0"`
SCRIPTPATH=`dirname "$SCRIPT"`
cd $SCRIPTPATH/..

docker stop postgresql
rm -Rf /tmp/postgresql
mkdir /tmp/postgresql || exit 1
until docker run -d --name postgresql --rm -p 5432:5432 -v /tmp/postgresql:/var/lib/postgresql postgres; do sleep 1; done
until docker exec postgresql pg_isready; do sleep 1; done
echo "CREATE USER juliabase WITH PASSWORD '12345' CREATEDB;" | docker exec -i postgresql psql -U postgres || exit 2
docker exec postgresql createdb -U juliabase juliabase || exit 3
./manage.py migrate || exit 4
./manage.py loaddata institute/fixtures/demo_accounts.yaml || exit 5
export JULIABASE_SERVER_URL=http://127.0.0.1:8000/
./manage.py runserver &
until wget -O - http://127.0.0.1:8000/ > /dev/null; do sleep 1; done
remote_client/examples/run-crawlers.sh || exit 6
kill `netstat -ntlp 2> /dev/null | grep 127.0.0.1:8000 | awk '{print $7}' | cut -d / -f 1` || exit 7
