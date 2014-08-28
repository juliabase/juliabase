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


from __future__ import absolute_import, unicode_literals
import sys, os, socket
from django.core.management import execute_from_command_line

hostname = socket.gethostname()
if hostname == "my_server":
    os.environ["DJANGO_SETTINGS_MODULE"] = "other_settings.my_settings"
else:
    os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

import django.contrib.auth.management
def _get_only_custom_permissions(opts, ctype):
    return list(opts.permissions)
django.contrib.auth.management._get_all_permissions = _get_only_custom_permissions

execute_from_command_line(sys.argv)
