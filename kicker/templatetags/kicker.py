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


"""Collection of tags and filters that I found useful for ther Kicker app of
JuliaBase.
"""


from django import template
import jb_common.utils.base as utils

register = template.Library()


@register.filter
def nickname(user):
    return user.kicker_user_details.nickname or utils.get_really_full_name(user)


@register.filter
def pretty_print_win_points(win_points):
    if win_points is None:
        return None
    else:
        return "{:+0.1f}".format(win_points).replace("-", "−")
