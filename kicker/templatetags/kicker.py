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


u"""Collection of tags and filters that I found useful for ther Kicker app of
JuliaBase.
"""

from __future__ import absolute_import

from django.template.defaultfilters import stringfilter
from django import template
from django.utils.safestring import mark_safe
# This *must* be absolute because otherwise, a Django module of the same name
# is imported.
from jb_common import utils

register = template.Library()


@register.filter
def nickname(user):
    return user.kicker_user_details.nickname or utils.get_really_full_name(user)
