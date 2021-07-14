How to export RDF
=================

The following describes how to get the RDF representation of a sample in a test
environment.  All following action takes place relative to the repository’s
root directory.

First, activate the ``settings_test.py`` settings file, which in particular
enables a local SQLite database for persistence.  This database will be written
to the file ``juliabase``.  You activate the settings for the local shell
session with::

  export DJANGO_SETTINGS_MODULE=settings_test

Then, initialise the SQLite database with::

  ./manage.py migrate

Fill it with initial data::

  ./manage.py loaddata test_main

Run the local web server::

  ./manage.py runserver

Now, open another shell and run::

  wget -O sample.rdf --header "Accept: text/turtle" \
      localhost:8000/samples/14S-005

This will write a turtle representation of the sample “14S-005” to the file
``sample.rdf``.
