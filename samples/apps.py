#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
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

from __future__ import absolute_import, unicode_literals

import os, re, importlib
from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _, ugettext
from django.core.urlresolvers import reverse
import jb_common.utils.base as utils
from jb_common.nav_menu import MenuItem


class SamplesConfig(AppConfig):
    name = "samples"
    verbose_name = _("Samples database – core")

    def ready(self):
        import samples.signals

        if not os.path.exists(settings.CACHE_ROOT):
            os.makedirs(settings.CACHE_ROOT)

        initials_groups = {}
        for name, properties in settings.INITIALS_FORMATS.items():
            group_name = {"user": "user_initials", "external_contact": "external_contact_initials"}[name]
            initials_groups[name] = "(?P<{group_name}>{pattern})".format(group_name=group_name, pattern=properties["pattern"])
            properties["regex"] = re.compile(properties["pattern"] + r"\Z")
        initials_groups["combined"] = "(?P<combined_initials>(?:{user})|(?:{external_contact}))".format(
            user=settings.INITIALS_FORMATS["user"]["pattern"],
            external_contact=settings.INITIALS_FORMATS["external_contact"]["pattern"])
        settings.SAMPLE_NAME_FORMATS["provisional"]["pattern"] = r"\*(?P<id>\d{{5}})$"
        for properties in settings.SAMPLE_NAME_FORMATS.values():
            properties["pattern"] = properties["pattern"].format(
                year=r"(?P<year>\d{4})", short_year=r"(?P<short_year>\d{2})",
                user_initials=initials_groups["user"],
                external_contact_initials=initials_groups["external_contact"],
                combined_initials=initials_groups["combined"])
            properties["regex"] = re.compile(properties["pattern"] + r"\Z")
        settings.SAMPLE_NAME_FORMATS["provisional"].setdefault("verbose_name", _("provisional"))
        for name_format, properties in settings.SAMPLE_NAME_FORMATS.items():
            properties.setdefault("verbose_name", name_format)

    def build_menu(self, menu, request):
        if request.user.is_authenticated():
            user_menu = menu.get_or_create(MenuItem(utils.get_really_full_name(request.user), position="right"))
            user_menu.prepend(MenuItem(_("my topics and permissions"),
                                       reverse("samples.views.user_details.topics_and_permissions",
                                               kwargs={"login_name": request.user.username})))
            add_menu = menu.get_or_create(_("add"))
            add_menu.add(_("samples"), reverse(settings.ADD_SAMPLES_VIEW), "stop")
            add_menu.add(_("sample series"), reverse("samples.views.sample_series.new"), "th")
            add_menu.add(_("result"), reverse("add_result"), "scale")
            add_menu.add_separator()
            permissions = importlib.import_module("samples.permissions")
            for physical_process in permissions.get_allowed_physical_processes(request.user):
                add_menu.add(physical_process["label"], physical_process["url"])
            search_menu = menu.get_or_create(_("explore"))
            search_menu.add(_("advanced search"), reverse("samples.views.sample.advanced_search"), "search")
            search_menu.add(_("samples by name"), reverse("samples.views.sample.search"), "stop")
            search_menu.add_separator()
            lab_notebooks = permissions.get_lab_notebooks(request.user)
            if lab_notebooks:
                for lab_notebook in lab_notebooks:
                    search_menu.add(lab_notebook["label"], lab_notebook["url"], "book")
            manage_menu = menu.get_or_create(_("manage"))
            if request.user.has_perm("samples.rename_samples"):
                manage_menu.add(_("rename sample"), reverse("samples.views.sample.rename_sample"))
            manage_menu.add(_("merge samples"), reverse("samples.views.merge_samples.merge"))
            manage_menu.add(_("sample claims"), reverse("samples.views.claim.list_",
                                                        kwargs={"username": request.user.username}))
            manage_menu.add_separator()
            if permissions.has_permission_to_edit_users_topics(request.user):
                manage_menu.add(_("add new topic"), reverse("samples.views.topic.add"))
            if permissions.can_edit_any_topics(request.user):
                manage_menu.add(_("change topic memberships"), reverse("samples.views.topic.list_"))
            manage_menu.add_separator()
            if permissions.has_permission_to_add_external_operator(request.user):
                manage_menu.add(_("add external operator"), reverse("samples.views.external_operator.new"))
            if permissions.can_edit_any_external_contacts(request.user):
                manage_menu.add(_("edit external operator"), reverse("samples.views.external_operator.list_"))
            manage_menu.add_separator()
            manage_menu.add(_("permissions"), reverse("samples.views.permissions.list_"))
            manage_menu.add(_("task lists"), reverse("samples.views.task_lists.show"))
            manage_menu.add(_("newsfeed"),
                            reverse("samples.views.feed.show", kwargs={"username": request.user,
                                                                       "user_hash": permissions.get_user_hash(request.user)}))
            manage_menu.add(_("status messages"), reverse("samples.views.status.show"))
            manage_menu.add(_("inspect crawler logs"), reverse("samples.views.log_viewer.list"))
            if request.user.is_superuser:
                manage_menu.add(_("administration"), "admin/")


_ = ugettext
