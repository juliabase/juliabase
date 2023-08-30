#!/bin/sh

# init_db.sh initialises a locally running PostgreSQL database with test data.
# After that, you can start developing using the Django testserver.

./manage.py migrate
if [ $? != 0 ]
then
    echo
    echo "First, call PostgreSQL with"
    echo "docker run --rm --name postgres -e POSTGRES_USER=juliabase -e POSTGRES_PASSWORD=12345 -p 5432:5432 postgres"
    exit 10
fi
./manage.py loaddata institute/fixtures/demo_accounts.yaml || exit 10
cd remote_client/examples || exit 10
./run-crawlers.sh synchronous || exit 10
