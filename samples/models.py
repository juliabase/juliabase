#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

:var physical_process_models: dictionary of all models that denote physical
  processes (i.e. depositions, measurements, etching processes etc).  It maps
  the name to the model class itself.  Such processes must have a permission of
  the form ``"add_edit_model_name"`` where the model name is in lowercase with
  underscores.  Additionally, they must have the method ``get_add_link`` (see
  `SixChamberDeposition.get_add_link`).  For the sake of performance, I don't
  want to enforce the latter by a common parent class.

:type physical_process_models: dict mapping ``str`` to ``class``.
"""

from __future__ import absolute_import

import copy, inspect
from django.db import models
from samples.models_common import *
from samples.models_depositions import *
from samples.models_feeds import *

u"""

:var clearance_sets: Dictionary mapping clearance codenames to Process
  subclasses.  This dictionary is used in the “edit MySamples“ view to offer
  pre-defined sets of Processes that should be allowed to see by the user to
  whom the samples are copied.  The dictionary may be left empty.  Otherwise,
  it may be injected here from the ``models.py`` of another app.

:type clearance_sets: dict mapping unicode to tuple of `Process`.
"""


clearance_sets = {}


# FixMe: In Python 3, this could be achieved with class decorators, I think.
physical_process_models = {}
def register_physical_process(cls):
    physical_process_models[cls.__name__] = cls
