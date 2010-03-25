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


# FixMe: In Python 3, this could be achieved with class decorators, I think.
physical_process_models = {}
def register_physical_process(cls):
    physical_process_models[cls.__name__] = cls


_globals = copy.copy(globals())
all_models = [cls for cls in _globals.values() if inspect.isclass(cls) and issubclass(cls, models.Model)]
class_hierarchy = inspect.getclasstree(all_models)
u"""Rather complicated list structure that represents the class hierarchy of
models in this module.  Nobody needs to understand it as long as the internal
`inject_direct_subclasses` is working."""
def find_actual_instance(self):
    u"""This is a module function but is is injected into ``Models.model`` to
    become a class method for all models of Chantal.  If you call this method
    on a database instance, you get the leaf class instance of this model.  For
    example, if you retrieved a `Process` from the database, you get the
    `SixChamberDeposition` (if it is one).  This way, polymorphism actually
    works with the relational database.

    :Return:
      an instance of the actual model class for this database entry.

    :rtype: ``models.Model``.
    """
    try:
        return self.__actual_instance
    except AttributeError:
        if not self.direct_subclasses:
            self.__actual_instance = self
        else:
            for cls in self.direct_subclasses:
                name = cls.__name__.lower()
                if hasattr(self, name):
                    instance = getattr(self, name)
                    self.__actual_instance = instance.find_actual_instance()
                    break
            else:
                raise Exception("internal error: instance not found")
        return self.__actual_instance

models.Model.find_actual_instance = find_actual_instance


def inject_direct_subclasses(parent, hierarchy):
    u"""This is a mere helper function which injects a list with all subclasses
    into the class itself, under the name ``direct_subclasses``.  It is only
    for use by `find_actual_instance`.

    This is basically a tree walker through the weird nested data structure
    returned by ``inspect.getclasstree`` and stored in `class_hierarchy`.

    :Parameters:
      - `parent`: the class to which the subclasses should be added
      - `hierarchy`: the remaining class inheritance hierarchy that has to be
        processed.

    :type parent: class, descendant of ``models.Model``
    :type hierarchy: list as returned by ``inspect.getclasstree``
    """
    i = 0
    while i < len(hierarchy):
        # May have already been initialised by another app
        if "direct_subclasses" not in hierarchy[i][0].__dict__:
            hierarchy[i][0].direct_subclasses = set()
        if parent:
            parent.direct_subclasses.add(hierarchy[i][0])
        if i + 1 < len(hierarchy) and isinstance(hierarchy[i+1], list):
            inject_direct_subclasses(hierarchy[i][0], hierarchy[i+1])
            i += 2
        else:
            i += 1

inject_direct_subclasses(None, class_hierarchy)
del _globals, cls
