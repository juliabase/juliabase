.. -*- mode: rst; coding: utf-8; ispell-local-dictionary: "british" -*-
..
.. This file is part of Chantal, the samples database.
..
.. Copyright (C) 2014 Forschungszentrum Jülich, Germany,
..                    Marvin Goblet <m.goblet@fz-juelich.de>,
..                    Torsten Bronger <t.bronger@fz-juelich.de>
..
.. You must not use, install, pass on, offer, sell, analyse, modify, or
.. distribute this software without explicit permission of the copyright
.. holder.  If you have received a copy of this software without the explicit
.. permission of the copyright holder, you must destroy it immediately and
.. completely.

==============
Installation
==============

Prerequisites
===============

Basically, you only need the current version of the `Django web framework`_
together with its prerequisites.  Typically, this will be a computer with a
Linux operating system, and with Apache and PostgreSQL running on it.  However,
Django is flexible.  Is also runs on a Windows server, and it may be combined
with different webservers and database backends.  See `Django's own
installation guide`_ for more information.  Still, in this document, we assume
the default setup, which we also strongly recommend: Linux, Apache, PostgreSQL.
We deliberately avoid mentioning any particular Linux distribution because we
assume that at least their server flavours are similar enough.  For what it's
worth, the authors run Ubuntu Server.

.. _Django web framework: https://www.djangoproject.com/
.. _Django's own installation guide:
   https://docs.djangoproject.com/en/1.7/topics/install/

Mostly, no sophisticated finetuning of the components is necessary because
Chantal deployments will serve only a few (< 1000) people.  In particular,
PostgreSQL and Apache can run in default configuration by and large.  On the
other hand, the computer should be a `high-availability system`_, possibly
realised with virtual machines.  In our own installation, we manage a
three-nines system, i. e. 99.9 % availability.  Additionally, regular backups
are a must! To set up these things, however, is beyond the scope of this
document.  Your IT department may turn out to be very helpful with this.

.. _high-availability system: http://linux-ha.org/

In the following, we'll show you how to get Chantal up and running quickly.
While our way is already useful for a production system, you may wish or need
to do it in a different way.  Thus, consider the following a good starting
point for your own configuration.

Linux configuration
=======================

Additionally to the software that is running on any recent and decent Linux
operating system by default anyway, you must install:

- Apache2
- PostgreSQL (and the Python module “psycopg2” for it)
- memcached (and the Python module for it)
- matplotlib

PostgreSQL
==============

If you have PostgreSQL and Apache on the same computer, PostgreSQL's default
configuration should work for you.  The defaults are quite restrictive, so they
can be considered secure.  Otherwise, if you need to change something, it is
probably in pg_hba.conf (where the `user authentication`_ resides) or
postgresql.conf (where the `general configuration`_ resides), both of which are
typically found in /etc/postgresql/*version*/main/.

.. _user authentication:
   http://www.postgresql.org/docs/9.1/static/auth-methods.html
.. _general configuration:
   http://www.postgresql.org/docs/9.1/static/runtime-config.html

Anyway, you create a PostgreSQL user with this::

  $ sudo −u postgres psql
  psql (9.3.4)
  Type "help" for help.

  postgres=# CREATE USER username WITH PASSWORD ’topsecret’ CREATEDB;
  CREATE ROLE
  postgres=# \q

In this snippet, you have to replace ``username`` with your UNIX user name, and
``topsecret`` with a proper password, which shouldn't be your UNIX login
password.  Finally, create the database with::

  $ createdb chantal


Django and South
======================

A certain version of Chantal works only with a certain version of Django.
Currently, this is Django 1.6.5.  Install it according to `Django's own
instructions`_.  Not further configuration is necessary.  Moreover, you must
`install South`_.

.. _Django's own instructions: https://www.djangoproject.com/download/
.. _install South: http://south.readthedocs.org/en/latest/installation.html

Chantal
===========================

Currently, Chantal is organised in non-public `Git`_ repositories.  There are
three of them:

1. chantal_common
2. chantal_samples
3. chantal_institute

Each of these three repositories contains one Django app of the same name.
chantal_common implements the basic Chantal functionality.  On top of that,
chantal_samples implements the actual samples database.  And on top of that,
chantal_institute implements code that is specific to the specific institution
or department or work group that wants to use Chantal.  chantal_institute
implements a *generic* institute.  You will replace chantal_institute with your
own app and rename it accordingly.

.. _Git: http://git-scm.com/

Once you have arranged with the `Chantal maintainers`_ read access for the Git
repositories, you can check out the source code on your computer with::

  git clone git@bob.ipv.kfa-juelich.de:chantal_common
  git clone git@bob.ipv.kfa-juelich.de:chantal_samples
  git clone git@bob.ipv.kfa-juelich.de:chantal_institute

.. _Chantal maintainers: mailto:m.goblet@fz-juelich.de

It is important that you do this in the same common parent directory.  This
creates three subdirectories of the three repository names.  In the
subdirectory “chantal_institute” is the file `manage.py as known from Django`_,
which is the command-line administration tool for Chantal.

.. _manage.py as known from Django:
   https://docs.djangoproject.com/en/dev/ref/django-admin/


The settings.py file
--------------------

In the subdirectory “chantal_institute”, there is the file `settings.py
as known from Django`_.  It contains the global configuration of your
Chantal installation and needs to be adjusted by you.

.. _settings.py as known from Django:
   https://docs.djangoproject.com/en/dev/topics/settings/

TBD

Apache
==========

Add to your Apache configuration something like the following::

  <VirtualHost *:80>
    ServerName chantal.example.com
    WSGIScriptAlias / /home/username/src/chantal_institute/django.wsgi
    XSendFile on
    XSendFilePath /
    Alias /media /var/www/chantal/media
    <Location "/">
      Order allow,deny
      Allow from all
      Require all granted
    </Location>
  </VirtualHost>

This snippet contains several parts that highly probably need to be adjusted by
you, in particular ``chantal.example.com``, ``username``, and all paths in
general.  But this should be obvious.  The proper place for it depends on your
Linux variant.  It may be the (new) file ``/etc/apache2/httpd.conf``, or a new
file in ``/etc/apache2/conf.d``, or a new file in
``/etc/apache2/sites-available`` with a symlink in
``/etc/apache2/sites-enabled``.
