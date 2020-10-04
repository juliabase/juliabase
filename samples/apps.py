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

import re, importlib
from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _, ugettext, pgettext
from django.urls import reverse
from jb_common.nav_menu import MenuItem


class SamplesConfig(AppConfig):
    name = "samples"
    verbose_name = _("Samples database – core")

    def ready(self):
        import samples.signals

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
        """Contribute to the menu.  See :py:mod:`jb_common.nav_menu` for further
        information.
        """
        import jb_common.utils.base as utils

        if request.user.is_authenticated:
            user_menu = menu.get_or_create(MenuItem(utils.get_really_full_name(request.user), position="right"))
            user_menu.prepend(MenuItem(_("my topics and permissions"),
                                       reverse("samples:topics_and_permissions",
                                               kwargs={"login_name": request.user.username})))
            add_menu = menu.get_or_create(_("add"))
            add_menu.add(_("samples"), reverse(settings.ADD_SAMPLES_VIEW), "stop")
            add_menu.add(_("sample series"), reverse("samples:add_sample_series"), "th")
            add_menu.add(_("result"), reverse("samples:add_result"), "scale")
            add_menu.add_separator()
            permissions = importlib.import_module("samples.permissions")
            for physical_process in permissions.get_allowed_physical_processes(request.user):
                add_menu.add(physical_process["label"], physical_process["url"])
            explore_menu = menu.get_or_create(pgettext("top-level menu item", "explore"))
            explore_menu.add(_("advanced search"), reverse("samples:advanced_search"), "search")
            explore_menu.add(_("samples by name"), reverse("samples:sample_search"), "stop")
            explore_menu.add_separator()
            lab_notebooks = permissions.get_lab_notebooks(request.user)
            if lab_notebooks:
                explore_menu.add_heading(_("lab notebooks"))
                for lab_notebook in lab_notebooks:
                    explore_menu.add(lab_notebook["label"], lab_notebook["url"], "book")
            manage_menu = menu.get_or_create(_("manage"))
            manage_menu.add(_("manage “My Samples”"), reverse("samples:edit_my_samples",
                                                              kwargs={"username": request.user.username}))
            if request.user.has_perm("samples.rename_samples"):
                manage_menu.add(_("rename sample"), reverse("samples:rename_sample"))
            manage_menu.add(_("merge samples"), reverse("samples:merge_samples"))
            manage_menu.add(_("sample claims"), reverse("samples:list_claims", kwargs={"username": request.user.username}))
            manage_menu.add_separator()
            if permissions.has_permission_to_edit_users_topics(request.user):
                manage_menu.add(_("add new topic"), reverse("samples:add_topic"))
            if permissions.can_edit_any_topics(request.user):
                manage_menu.add(_("change topic memberships"), reverse("samples:list_topics"))
            manage_menu.add_separator()
            if permissions.has_permission_to_add_external_operator(request.user):
                manage_menu.add(_("add external operator"), reverse("samples:add_external_operator"))
            if permissions.can_edit_any_external_contacts(request.user):
                manage_menu.add(_("edit external operator"), reverse("samples:list_external_operators"))
            manage_menu.add_separator()
            manage_menu.add(_("permissions"), reverse("samples:list_permissions"))
            manage_menu.add(_("task lists"), reverse("samples:show_task_lists"))
            manage_menu.add(_("newsfeed"),
                            reverse("samples:show_feed", kwargs={"username": request.user,
                                                                 "user_hash": permissions.get_user_hash(request.user)}))
            manage_menu.add(_("status messages"), reverse("samples:show_status"))
            manage_menu.add(_("inspect crawler logs"), reverse("samples:list_log_viewers"))
            if request.user.is_superuser:
                manage_menu.add(_("administration"), reverse("admin:index"))


_ = ugettext
