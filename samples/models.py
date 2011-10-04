#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


u"""This module is the connection to the database.  It contains the *models*,
i.e. Python classes which represent the tables in the relational database.
Every class which inherits from ``models.Model`` is a PostgreSQL table at the
same time, unless it has ``abstract = True`` set in their ``Meta`` subclass.

If you add fields to models, and you have a PostgreSQL database running which
contains already valuable data, you have to add the fields manually with SQL
commands to the database, too.  (There is a project called `“Django
Evolution”`_ that tries to improve this situation.)

.. _“Django Evolution”: http://code.google.com/p/django-evolution/

However, if you add new *classes*, you can just run ``./manage.py syncdb`` and
the new tables are automatically created.

Note that this module doesn't define any models itself.  It is only the
container where all models are finally brought together by module inclusion.
The number and complexity of Chantal's models is too big for one file.
Therefore, we have a few model modules, all starting with ``models_...`` and
residing in this directory.  With ``from samples.models_... import *``
I can give the rest of Chantal's modules the illusion that all models are
actually here.
"""

from __future__ import absolute_import

import copy, inspect
from django.conf import settings
from samples.models_common import *
from samples.models_depositions import *
from samples.models_feeds import *
if settings.TESTING:
    from samples.models_test import *

u"""

:var clearance_sets: Dictionary of tupels mapping a ``Process`` subclass to tuples of
  ``Process`` subclasses.  This dictionary is used in the “get_sample_clearance“ method
  in the “Permissions“ modul to set the specific clearances for the operators
  who must allowed to see some informations about the sample.  The dictionary may be left empty.
  Otherwise, it may be injected here from the ``models.py`` of another app.

:type clearance_sets: dict mapping `Process` to tuple of `Process`
"""


clearance_sets = {}
