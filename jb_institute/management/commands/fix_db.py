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


"""Module which defines the command ``fix_db``.  It is a template for use-once
code that manipulates the database, for example, to apply mass-fixes.  If it is
not in current use, and in particular in the main trunk, it must be a no-op.
"""

from __future__ import absolute_import, unicode_literals

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    args = ""
    help = "Internal command for mass-fixes in the database.  Call it only if you know exactly what it's doing because " \
        "its functionality changes."

    def handle(self, *args, **kwargs):
        pass
