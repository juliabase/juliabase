#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal-Kicker
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


u"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “chantal_kicker”.
"""

from __future__ import absolute_import

from django.conf.urls import *
from django.conf import settings

urlpatterns = patterns("kicker.views",
                       (r"^matches/(?P<id_>\d+)/edit/$", "edit_match"),
                       url(r"^matches/add/$", "edit_match", {"id_": None}),
                       (r"^matches/(?P<id_>\d+)/cancel/$", "cancel_match"),
                       (r"^starting_numbers/(?P<username>.+)/add/$", "set_start_kicker_number"),
                       (r"^details/(?P<username>.+)", "edit_user_details"),
                       (r"^player", "get_player"),
                       (r"^$", "summary"),
                       )
