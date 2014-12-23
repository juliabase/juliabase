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


"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “kicker”.
"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls import url


urlpatterns = [
    url(r"^matches/(?P<id_>\d+)/edit/$", "kicker.views.edit_match"),
    url(r"^matches/add/$", "kicker.views.edit_match", {"id_": None}),
    url(r"^matches/(?P<id_>\d+)/cancel/$", "kicker.views.cancel_match"),
    url(r"^starting_numbers/(?P<username>.+)/add/$", "kicker.views.set_start_kicker_number"),
    url(r"^details/(?P<username>.+)", "kicker.views.edit_user_details"),
    url(r"^player", "kicker.views.get_player"),
    url(r"^$", "kicker.views.summary"),
]
