#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Module which defines the command ``maintenance``.  It should be called
nightly as a cronjob.  For example, one line in the crontab may read::

    0 3 * * * /home/juliabase/juliabase/manage.py maintenance
"""

from __future__ import absolute_import, unicode_literals

from django.core.management.base import BaseCommand
from jb_common.signals import maintain


class Command(BaseCommand):
    args = ""
    help = "Does database maintenance work.  It should be called nightly as a cronjob."

    def handle(self, *args, **kwargs):
        maintain.send(sender=Command)
