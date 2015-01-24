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

from __future__ import absolute_import, unicode_literals

import os, re
from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _, ugettext


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


_ = ugettext
