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
import os, socket
from django.core.management import execute_manager

hostname = socket.gethostname()
if hostname == "wilson":
    os.environ["DJANGO_SETTINGS_MODULE"] = "other_settings.wilson_settings"
elif hostname == "ipv609" or hostname == "mars":
    os.environ["DJANGO_SETTINGS_MODULE"] = "other_settings.marvin_settings"
elif hostname == "bob":
    os.environ["DJANGO_SETTINGS_MODULE"] = "other_settings.bob_settings"
else:
    os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

settings = __import__(os.environ["DJANGO_SETTINGS_MODULE"])

import django.contrib.auth.management
def _get_only_custom_permissions(opts):
    return list(opts.permissions)
django.contrib.auth.management._get_all_permissions = _get_only_custom_permissions

execute_manager(settings)
