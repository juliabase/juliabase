.. Remote-Client documentation master file, created by sphinx-quickstart on Mon Jan 12 16:20:00 2009.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. This file is part of Chantal, the samples database.
..
.. Copyright (C) 2011 Forschungszentrum Jülich, Germany,
..                    Marvin Goblet <m.goblet@fz-juelich.de>,
..                    Torsten Bronger <t.bronger@fz-juelich.de>
..
.. You must not use, install, pass on, offer, sell, analyse, modify, or
.. distribute this software without explicit permission of the copyright
.. holder.  If you have received a copy of this software without the explicit
.. permission of the copyright holder, you must destroy it immediately and
.. completely.


.. highlight:: python
   :linenothreshold: 10

Overview
=============

The Chantal remote client is a Python programming library which enables you to
communicate with the Chantal samples database.  You can read and write data of
the database, and you can do arbitrary things with it inbetween.  This allows
for a couple of very nice things:

#. So-called “crawlers“ can scan regularly for new measurement files and import
 them into the database.

#. Control programs at measurement setups can read sample names, layer
 thicknesses, sample material etc. from the database.  After the measurement,
 they can write it directly into the database.

#. You can extensively read data from the database and do statistics.

#. You can perform complex search queries that are not possible with the
 browser.

#. You can read data, process it by evaluating, combining, etc., and write back
 the result.

In general, everything that is possible with the browser is also possible with
the remote client.  However, everything that you cannot do with the browser
because your permissions are not sufficient, is also forbidden with the remote
client.

The remote client is written in Python, so the most convenient way to use it is
by writing a Python program.  Python is a wide-spread, easy-to-learn
general-purpose language.  It is perfect for small scripts, which are typical
if you query the database.

Of course, you will have much non-Python in your institution, in form of code
as well as competence.  Since the standard implementation of Python is an
interpreter, it is very easy to call Python code from within another
programming language.  While it is possible to talk to the Chantal server from
most programming languages directly, we recommend going via the Python remote
client because this is the easiest way.
