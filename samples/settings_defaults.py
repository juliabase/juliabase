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


"""Default values of settings of the app "samples"."""

from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _

CACHE_ROOT = str("/tmp/juliabase_cache")
MAP_DEPARTMENTS_TO_APP_LABELS = {}
THUMBNAIL_WIDTH = 400
CRAWLER_LOGS_WHITELIST = ()
CRAWLER_LOGS_ROOT = ""
PHYSICAL_PROCESS_BLACKLIST = ()
ADD_SAMPLE_VIEW = ""
MERGE_CLEANUP_FUNCTION = ""
INITIALS_FORMATS = {"user": {"pattern": r"[A-Z]{2,4}|[A-Z]{2,3}\d|[A-Z]{2}\d{2}",
                             "description": _("The initials start with two uppercase letters.  "
                                              "They contain uppercase letters and digits only.  Digits are at the end.")},
                    "external contact": {"pattern": r"[A-Z]{4}|[A-Z]{3}\d|[A-Z]{2}\d{2}",
                                         "description": _("The initials start with two uppercase letters.  "
                                                          "They contain uppercase letters and digits only.  "
                                                          "Digits are at the end.  "
                                                          "The length is exactly 4 characters.")}
                    }
SAMPLE_NAME_FORMATS = {"provisional": {"possible renames": {"default"}},
                       "default":     {"pattern": r"[-A-Za-z_/0-9#()]*$"}}
NAME_PREFIX_TEMPLATES = ()

# Django settings which are used in samples

# MEDIA_ROOT
# SECRET_KEY
# STATIC_ROOT
# STATIC_URL
# INSTALLED_APPS
# CACHES
