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

import os, re
from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _, ugettext
from django.core.urlresolvers import reverse
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
            add_menu = menu.get_or_create(_("add"))
            add_menu.add(_("samples"), reverse(settings.ADD_SAMPLES_VIEW), "stop")
            add_menu.add(_("sample series"), reverse("samples.views.sample_series.new"), "th")

_ = ugettext
