#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
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
the Django application “chantal_common”, which provides core functionality and
core views for all Chantal apps.


:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/

"""

from __future__ import absolute_import

from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns("django.contrib.auth.views",
                       (r"^change_password$", "password_change", {"template_name": "chantal_common/change_password.html"}),
                       (r"^change_password/done/$", "password_change_done",
                        {"template_name": "chantal_common/password_changed.html"}),
                       (r"^login$", "login", {"template_name": "chantal_common/login.html"}),
                       (r"^logout$", "logout", {"template_name": "chantal_common/logout.html"}),
                       )

urlpatterns += patterns("chantal_common.views",
                        (r"^markdown$", "markdown_sandbox"),
                        (r"^switch_language$", "switch_language"),
                        (r"^error_pages/(?P<hash_value>.+)", "show_error_page"),
                        )
