# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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
to ``settings.TEMPLATES``.  They add further data to the dictionary passed to
the templates.
"""

from django.conf import settings
from django.utils.translation import ugettext_lazy as _, ugettext


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
        return {"salutation": str(special_salutations[user.username]).format(user=user)}
    else:
        return {}


_ = ugettext
