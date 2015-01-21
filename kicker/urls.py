#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Kicker
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “kicker”.
"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls import url
from kicker.views import edit_match, cancel_match, set_start_kicker_number, edit_user_details, get_player, summary


urlpatterns = [
    url(r"^matches/(?P<id_>\d+)/edit/$", edit_match),
    url(r"^matches/add/$", edit_match, {"id_": None}),
    url(r"^matches/(?P<id_>\d+)/cancel/$", cancel_match),
    url(r"^starting_numbers/(?P<username>.+)/add/$", set_start_kicker_number),
    url(r"^details/(?P<username>.+)", edit_user_details),
    url(r"^player", get_player),
    url(r"^$", summary),
]
