#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


from __future__ import absolute_import, unicode_literals

import sys, os
from django.core.management import execute_from_command_line


root = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(root, "mysite")):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
    sys.path.append(os.path.join(root, "juliabase"))
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")


import django.contrib.auth.management
def _get_only_custom_permissions(opts, ctype):
    return list(opts.permissions)
django.contrib.auth.management._get_all_permissions = _get_only_custom_permissions

execute_from_command_line(sys.argv)
