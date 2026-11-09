How to export RDF
=================

The following describes how to get the RDF representation of a sample in a test
environment.  All following action takes place relative to the repository’s
root directory.

First, activate the ``settings_test.py`` settings file, which in particular
enables a local SQLite database for persistence.  This database will be written
to the file ``juliabase``.  You activate the settings for the local shell
session with::

  export DJANGO_SETTINGS_MODULE=settings_test \
         JULIABASE_DB_FILENAME=juliabase-test-db-1

Then, initialise the SQLite database with::

  ./manage.py migrate

Fill it with initial data::

  ./manage.py loaddata test_main_1

Run the local web server::

  ./manage.py runserver

Now, open another shell and run::

  tools/get_graph.py r.calvert 14S-005 > sample.rdf

This will write a turtle representation of the sample “14S-005” to the file
``sample.rdf``.  Call ``get_graph.py --help`` for more options.


How to enrich a local JuliaBase instance with external data
-----------------------------------------------------------

Run the test server as above, then open another shell::


  $ export DJANGO_SETTINGS_MODULE=settings_test \
         JULIABASE_DB_FILENAME=juliabase-test-db-2
  $ ./manage.py migrate
  …
  $ ./manage.py loaddata test_main_2
  …
  $ ./manage.py runserver 8888

Then open http://localhost:8888/samples/14S-001 in the browser.  You will see
the Five-Chamber-deposition process from the instance listening on port 8000.
