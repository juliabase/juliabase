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

from __future__ import absolute_import, division, unicode_literals
from chantal_common.models import Department
from django.contrib.contenttypes.models import ContentType
from chantal_common import utils
from django.conf import settings
from django.db.utils import DatabaseError
import sys

def register_to_department(process_cls, department_name):
    """Connects a process with a department.

    :Parameters:
      - `process_cls`: the process model class that should be added to a department
      - `department_name`: the name of the department to which the process belongs

    :type process_cls: ``samples.models.Process``
    :type department_name: str
    """
    if not "syncdb" in sys.argv:
        try:
            department = Department.objects.get(name=department_name)
            content_type = ContentType.objects.get_for_model(process_cls)
            if content_type not in department.processes.iterator():
                department.processes.add(content_type)
        except (DatabaseError, Department.DoesNotExist):
            pass


def register_all_models_to_department(department_name):
    """Connects all database models from an chantal app to the belonging department.

    :Parameter:
      - `department`: the name of the department to which the processes belongs

    :type department_name: str
    """
    for process_class in utils.get_all_models(settings.MAP_DEPARTMENTS_TO_APP_LABELS[department_name]).itervalues():
        if not process_class._meta.abstract == True:
            register_to_department(process_class, department_name)
