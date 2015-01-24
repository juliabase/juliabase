#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Additional context processors for JuliaBase.  These functions must be added
to ``settings.TEMPLATE_CONTEXT_PROCESSORS``.  They add further data to the
dictionary passed to the templates.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six

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
        return {"salutation": six.text_type(special_salutations[user.username]).format(user=user)}
    else:
        return {}


_ = ugettext
