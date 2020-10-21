# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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

from django.urls import re_path
from kicker.views import edit_match, cancel_match, set_start_kicker_number, edit_user_details, get_player, summary, plot


app_name = "kicker"

urlpatterns = [
    re_path(r"^matches/(?P<id_>\d+)/edit/$", edit_match),
    re_path(r"^matches/add/$", edit_match, {"id_": None}),
    re_path(r"^matches/(?P<id_>\d+)/cancel/$", cancel_match),
    re_path(r"^starting_numbers/(?P<username>.+)/add/$", set_start_kicker_number),
    re_path(r"^details/(?P<username>.+)", edit_user_details, name="edit_user_details"),
    re_path(r"^kicker\.(?P<image_format>png|pdf)$", plot, name="plot"),
    re_path(r"^player", get_player),
    re_path(r"^$", summary, name="summary"),
]
