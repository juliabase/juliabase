#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
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


"""Additional context processors for JuliaBase.  These functions must be added
to ``settings.TEMPLATE_CONTEXT_PROCESSORS``.  They add further data to the
dictionary passed to the templates.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six

from django.conf import settings
from django.utils.translation import ugettext_lazy as _


special_salutations = {"j.silverton": _("Mrs {user.last_name}"), "s.renard": _("Mr. {user.last_name}")}

def default(request):
    """Injects an amended salutation string into the request context without
    polluting user details.  This realises a T–V distinction for some fixed
    users.  Don't take this function too seriously.  ☺

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the (additional) context dictionary

    :rtype: dict mapping str to session data
    """
    user = request.user
    if user.username in special_salutations:
        return {"salutation": six.text_type(special_salutations[user.username]).format(user=user)}
    else:
        return {}
