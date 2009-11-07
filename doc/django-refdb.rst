.. Copyright (c) 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>

   This file is part of Django-RefDB.  Django-RefDB is published under the AGPL
   license.  A copy of this licence is shipped with Django-RefDB in the file
   LICENSE.


.. highlight:: python
   :linenothreshold: 10

Django-RefDB
===================

Django-RefDB is a browser-based frontend to RefDB.  It is built on top of the
Django Web framework.  It is published under the terms of the AGPL.


.. toctree::
   :maxdepth: 2


Motivation
-------------

In spring 2009, I looked for a references manager for all the books and papers
that I needed in my daily work.  Additionally, the tool should be able to be
used by all members of my institute so that we could share citations and PDFs.
To my big surprise, there was only a small number of such open-source projects
available.

Quite close to my needs came `Refbase`_, however, its PDF upload features are
limited, which was crucial for me.  Moreover, Refbase being a PHP application
is difficult to integrate with other applications.  In contrast, I consider
Django a superior platform for the creation of resuable Web applications and we
had already a Django site running in the institute.

Thus, following the not-invented-here syndrome, I decided to indulge in
creating such a tool of my own, using Django.

.. _Refbase: http://www.refbase.net


Goals
-------

Django-RefDB is supposed to become an open-source Django application for
managing scientific references.  It must useful for a single person as well as
for a big team.  It should scale reasonably well.  It must deal with PDFs as
first-class citizens (multiple PDFs per reference, full-text search).

Eventually, it should also help with getting closer to the paperless office,
i.e. it should be able to deal with non-scientific and private documents, too.


Current status
-----------------

Django-RefDB is still alpha because it is not feature-complete.  The features
that we have are usable, though.  I myself use it productively, but I still
discourage people from doing so because it's still not tested well enough.

Fortunately, it uses RefDB as its backend, so that you always have command-line
access to your references.  Additionally, RefDB assures a good degree of
database consistency.  In other words, even when Django-RefDB hits a bug, no
too bad things can happen.


Architecture
---------------

Django-RefDB uses `RefDB`_ as its backend.  This has the advantage of having a
solid, feature-rich references utility, in particular for searching and export
into various formats.  But it also has the disadvantage of being limited to the
data fields of RefDB.  Moreover, RefDB isn't a speed daemon, so intensive
caching is necessary.

Django-RefDB tries to store everything in the RefDB database.  It also keeps
RefDB's semantices, so that old RefDB databases can be used directly with
Django-RefDB, and the other way round.  Extra fields (e.g. whether a reference
is an institute's publication) are realised with so-called extended notes in
RefDB.

However, Django-RefDB also stores some things in an own database through
Django's ORM.  This data is not vital, so losing it causes inconveniences at
most.  For example, you lose information about who created a certain reference
originally and when.

Django-RefDB uses `pyrefdb`_ for connecting to the RefDB server.  The RefDB
server may run on a different machine, and it may serve multiple Django-RefDB
installations as well as command-line connections.  However, some access
restrictions are not enforced on the command-line level.  This means that some
things are deliberately forbidden in Django-RefDB, but you can easily do it on
the command line.  Thus, I recommend providing command-line access only for the
administrator.

For full-text search in PDFs, Django-RefDB uses `Xapian`_.  For making this
possible even for scanned documents, `Tesseract`_ is called.

.. _`RefDB`: http://refdb.sourceforge.net/
.. _`pyrefdb`: https://launchpad.net/pyrefdb
.. _`Xapian`: http://xapian.org/
.. _`Tesseract`: http://code.google.com/p/tesseract-ocr/wiki/FAQ


Installation for Developers
-------------------------------

Since there is no release yet and you shouldn't use it in production, I only
give a brief explanation on how to install Django-RefDB the hard way.

Prerequisites
................

First, you need:

* Python 2.5–2.7 and Django 1.0+

* `django-staticfiles`_

* a RefDB server (the latest SVN version!), running on localhost

* pyrefdb, see the previous section

* Tesseract, Xapian, pdfimage, pdftotext, pdfinfo and convert (ImageMagick) for
  PDF indexing

.. _`django-staticfiles`: http://pypi.python.org/pypi/django-staticfiles


settings.py
.............

Then, get Django-RefDB with

::

    bzr branch lp:django-refdb

Adjust the settings in ``settings.py``.  This is standard Django work, so I
just refer to the next section for the Django-RefDB-specific settings.

If you want to get updates of Django-RefDB by just pulling from the branch on
Launchpad, or if you'd like to contribute to Django-RefDB, it may be wise not
to change the original settings.py but to setup a new Django app with local
adjustments to Django-RefDB (different branding, other login/logout views), and
with its own settings.py.

I myself created a locale app with my local adjustments (templates, media) and
with the following manage.py::

    import os.path, imp
    from django.core.management import execute_manager

    fp, pathname, description = imp.find_module(
        "settings", [os.path.dirname(os.path.abspath(__file__))])
    settings = imp.load_module("settings", fp, pathname, description)

    execute_manager(settings)

manage.py and settings.py are one directory above the local app directory.
Note that both directories must contain an ``__init__.py``.


syncdb
.........

As said, Django-RefDB uses own database models besides RefDB's database.  You
initialise them as usual with

::

    ./manage.py syncdb

manage.py will ask you whether you want to reset all user-specific data in the
RefDB database.  If this RefDB database is used with Django-RefDB for the first
time, you must say “yes”.  This will create/recreate some extended notes in the
RefDB database that Django-RefDB uses for its own purposes.  It doesn't really
change the RefDB database.  This process is idempotent.


URLs
-------

Normally, the URL scheme doesn't matter as long as all links work.  However,
since Django-RefDB lacks some functionality, most notable a top-level database
selection, two features are only accessibly by entering the URL manually.

The most important thing is that the name of the RefDB database is the first
component of the path.  For example, the “biblio” database can be seen at
``http://127.0.0.1:8000/biblio/``.  If you want to search in this database,
visit ``http://127.0.0.1:8000/biblio/search/``.  Note that Django-RefDB
intentionally is very petty about trailing slashs.

The rest should be accessible by mouse clicks.


Getting involved
--------------------

Besides `reporting bugs`_ and adding `translations`_ you can also directly
contribute to Django-RefDB's code.

For this, you must have a `Launchpad`_ account.  Join the `Django-RefDB team`_
and subscribe to its `mailing list`_.  Then you can pull the Bazaar branch and
work on it.

For todo lists, have a look at the bugs and the `blueprints`_.  The blueprints
are only summaries so far and need to be fleshed out.  You may do so in the
`Django-Refdb wiki`_ on Wikia.

.. _`reporting bugs`: https://bugs.launchpad.net/django-refdb
.. _`translations`: https://translations.launchpad.net/django-refdb
.. _`Launchpad`: https://launchpad.net/
.. _`Django-RefDB team`: https://launchpad.net/~django-refdb
.. _`mailing list`: mailto:django-refdb@lists.launchpad.net
.. _`blueprints`: https://blueprints.launchpad.net/django-refdb
.. _`Django-RefDB wiki`: http://django-refdb.wikia.com/wiki/Django-RefDB_Wiki


Settings
-----------

.. data:: REFDB_USERNAME_PREFIX

    RefDB usernames are constructed by appending the user's ID (in Django's
    tables) to this prefix.

.. data:: REFDB_ROOT_USERNAME

    Username of the main RefDB user, which must be allowed to create new users.

.. data:: REFDB_ROOT_PASSWORD

    Password of the main RefDB user.

.. data:: REFDB_CACHE_PREFIX

    Prefix used for keys in Django's cache.  This way, a namespace is created
    so that different apps don't use colliding keys.  Its value is
    insignificant as long as it's unique.

.. data:: REFDB_PATH_TO_INDEXER

    Full path to the program ``index_pdfs.py`` which indexes the PDFs.  It is
    part of Django-RefDB.


Middleware
----------------

Django-RefDB provides its own middleware class,

    refdb.middleware.transaction.TransactionMiddleware

which must be activated if you want to use Django-RefDB.


Chantal
----------

People who take a closer look at the source code may have noticed the
“chantal_common” module in Django-RefDB's tree.  It is used by Django-RefDB and
contains code which may also be useful to other Django apps.  Moreover, it
provides default views for login/logout – which you can override of course.

However, the actual reason for this module is slightly bizarre.  In my
institute, we had started with a large Django app for managing our samples,
i.e. a samples database.  This project is on-going and closed source, and its
name is “Chantal”.  Django-RefDB is meant to reside next to Chantal someday.
Therefore, I wanted to have all shared code in an own app in order to avoid
code duplication.

But don't worry, this only affects my institute.  The only effect on
Django-RefDB is the funny name “chantal_common” for the shared code module.
