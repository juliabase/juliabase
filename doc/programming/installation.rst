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

Basically, you only need he current version of the `Django web framework`_
together with its prerequisites.  Typically, this will be a computer with a
Linux operating system, and with Apache and PostgreSQL running on it.  However,
Django is flexible.  Is also runs on a Windows server, and it may be combined
with different webservers and database backends.  See `Django's own
installation guide`_ for more information.  Still, in this document, we assume
the default setup, which we also strongly recommend: Linux, Apache, PostgreSQL.

.. _`Django web framework`: https://www.djangoproject.com/
.. _`Django's own installation guide`: https://docs.djangoproject.com/en/1.7/topics/install/

By the way, the computer should be a `high-availability system`_, possibly
realised with virtual machines.  In our own installation, we manage a
three-nines system, i.e. 99.9% availability.  To set up such a beast, however,
is beyond the scope of this document.  Your IT department may turn out to be
very helpful with this.

.. _`high-availability system`: http://linux-ha.org/

Setting up the source code
===========================

Currently, Chantal is organised in `Git`_ repositories.  There are three of
them:

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

.. _`Git`: http://git-scm.com/
