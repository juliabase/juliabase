#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2019 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""Module which defines the command ``dataverse_export``.
"""

from django.core.management.base import BaseCommand
from jb_common.signals import maintain
from samples import models


class Command(BaseCommand):
    args = ""
    help = "Exports JuliaBase data to a Dataverse instance."

    def handle(self, *args, **kwargs):
        for process in models.Process.objects.all():
            process = process.actual_instance
            print(process.get_data())
