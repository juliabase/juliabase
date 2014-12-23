#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
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
the Django application “jb_common”, which provides core functionality and
core views for all JuliaBase apps.

:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/

"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls import url
from django.conf import settings


urlpatterns = [
    url(r"^change_password$", "django.contrib.auth.views.password_change", {"template_name": "jb_common/change_password.html"},
        name="password_change"),
    url(r"^change_password/done/$", "django.contrib.auth.views.password_change_done",
        {"template_name": "jb_common/password_changed.html"}, name="password_change_done"),
    url(r"^login$", "django.contrib.auth.views.login", {"template_name": "jb_common/login.html"}, name="login"),
    url(r"^logout$", "django.contrib.auth.views.logout", {"template_name": "jb_common/logout.html"}, name="logout"),

    url(r"^users/(?P<login_name>.+)", "jb_common.views.show_user"),
    url(r"^markdown$", "jb_common.views.markdown_sandbox"),
    url(r"^switch_language$", "jb_common.views.switch_language"),
    url(r"^error_pages/(?P<hash_value>.+)", "jb_common.views.show_error_page"),

    url(r"^jsi18n/$", "jb_common.views.cached_javascript_catalog", {"packages": settings.JAVASCRIPT_I18N_APPS}, name="jsi18n"),
]
