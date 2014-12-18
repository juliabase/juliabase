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


urlpatterns = [
    url(r"^matches/(?P<id_>\d+)/edit/$", "kicker.views.edit_match"),
    url(r"^matches/add/$", "kicker.views.edit_match", {"id_": None}),
    url(r"^matches/(?P<id_>\d+)/cancel/$", "kicker.views.cancel_match"),
    url(r"^starting_numbers/(?P<username>.+)/add/$", "kicker.views.set_start_kicker_number"),
    url(r"^details/(?P<username>[^/]+)$", "kicker.views.edit_user_details"),
    url(r"^player$", "kicker.views.get_player"),
    url(r"^$", "kicker.views.summary"),
]
