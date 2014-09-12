#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""This module is the connection to the database.  It contains the *models*,
i.e. Python classes which represent the tables in the relational database.
Every class which inherits from ``models.Model`` is a PostgreSQL table at the
same time, unless it has ``abstract = True`` set in their ``Meta`` subclass.

If you add fields to models, and you have a PostgreSQL database running which
contains already valuable data, you have to add the fields manually with SQL
commands to the database, too, or use Django-South.

However, if you add new *classes*, you can just run ``./manage.py syncdb`` and
the new tables are automatically created.

Note that this module doesn't define any models itself.  It is only the
container where all models are finally brought together by module inclusion.
The number and complexity of JuliaBase's models is too big for one file.
Therefore, we have a few model modules, all starting with ``models_...`` and
residing in this directory.  With ``from samples.models_... import *`` I can
give the rest of JuliaBase's modules the illusion that all models are actually
here.
"""

from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _
from jb_institute.models_physical_processes import *
from jb_institute.models_depositions import *
from jb_institute.models_sample_details import *
import samples.models
from samples.utils import register_all_models_to_department

samples.models.clearance_sets.update({
        PDSMeasurement: (PDSMeasurement, Substrate),
        ClusterToolDeposition: (ClusterToolDeposition, Substrate),
        })

# Use this option when you want to set the related department to your
# processes automatically.
# You have to set a department in order to allow non-administrators the
# option to grand permissions to processes to other users.
#register_all_models_to_department("Institute")
