#!/usr/bin/env python
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2022 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


import sys, os
from django.core.management import execute_from_command_line


root = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(root, "mysite")):
    sys.path.append(os.path.join(root, "juliabase"))
if sys.argv[1:2] == ["test"]:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_test")
elif os.path.isdir(os.path.join(root, "mysite")):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")


import django.contrib.auth.management
django.contrib.auth.management._get_builtin_permissions = lambda opts: []

execute_from_command_line(sys.argv)
