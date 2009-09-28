.. Django-RefDB documentation master file, created by sphinx-quickstart on Mon Jan 12 16:20:00 2009.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. highlight:: python
   :linenothreshold: 10

Django-RefDB
===================

Django-RefDB is a browser-based frontend to RefDB.  It is built on top of the
Django web framework.


.. toctree::
   :maxdepth: 2


Settings
------------

.. data:: REFDB_USERNAME_PREFIX

    RefDB usernames are constructed by appending the user's ID (in Django's
    tables) to this prefix.

.. data:: REFDB_USER

    Username of the main RefDB user, which must be allowed to create new users.

.. data:: REFDB_PASSWORD

    Password of the main RefDB user.

.. data:: REFDB_CACHE_PREFIX

    Prefix used for keys in Django's cache.  This way, a namespace is created
    so that different apps don't use colliding keys.  Its value is
    insignificant as long as it's unique.


Middleware
----------------

Django-RefDB provides its own middleware class,

    refdb.middleware.transaction.TransactionMiddleware

which must be activated if you want to use Django-RefDB.
