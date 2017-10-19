#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
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


"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “jb_common”, which provides core functionality and
core views for all JuliaBase apps.

:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/

"""

from django.conf.urls import url, include
from django.conf import settings
from django.views.decorators.cache import cache_page
from django.views.i18n import JavaScriptCatalog
from django.utils.http import urlquote_plus
from django.contrib.auth import views as auth_views
from jb_common.views import show_user, markdown_sandbox, switch_language, show_error_page


jb_common_patterns = ([
    url(r"^users/(?P<login_name>.+)", show_user, name="show_user"),
    url(r"^markdown$", markdown_sandbox, name="markdown_sandbox"),
    url(r"^switch_language$", switch_language, name="switch_language"),
    url(r"^error_pages/(?P<hash_value>.+)", show_error_page, name="show_error_page"),

    url(r"^jsi18n/$", cache_page(3600)(JavaScriptCatalog.as_view(packages=settings.JAVASCRIPT_I18N_APPS)), name="jsi18n"),
], "jb_common")

# Unfortunately, the ``PasswordChangeView`` view expects the
# ``PasswordChangeDoneView`` URL name to live in the global namespace,
# therefore, I have to define these separately.
login_related_patterns = [
    url(r"^change_password$", auth_views.PasswordChangeView.as_view(template_name="jb_common/change_password.html"),
        name="password_change"),
    url(r"^change_password/done/$", auth_views.PasswordChangeDoneView.as_view(
        template_name="jb_common/password_changed.html"), name="password_change_done"),
    url(r"^login$", auth_views.LoginView.as_view(template_name="jb_common/login.html"), name="login"),
    url(r"^logout$", auth_views.LogoutView.as_view(template_name="jb_common/logout.html"), name="logout"),
]

urlpatterns = [
    url(r"", include(login_related_patterns)),
    url(r"", include(jb_common_patterns)),
]
