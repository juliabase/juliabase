#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


"""Django settings for a generic JuliaBase installation.
"""

from __future__ import absolute_import, unicode_literals
# Python3 note: Below, there are some str() calls that should be removed with
# Python3.

import os
from django.utils.translation import ugettext_lazy as _
from jb_common.settings_defaults import *
from samples.settings_defaults import *


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if not os.path.exists(os.path.join(BASE_DIR, "jb_common")) and os.path.exists(os.path.join(BASE_DIR, "..", "juliabase")):
    BASE_DIR = os.path.join(os.path.dirname(BASE_DIR), "juliabase")


ALLOWED_HOSTS = ["0.0.0.0"]
DEBUG = True
TEMPLATE_DEBUG = DEBUG


DEFAULT_FROM_EMAIL = ""
EMAIL_HOST = ""
SERVER_EMAIL = DEFAULT_FROM_EMAIL
ADMINS = (
    ("JuliaBase-Admins", "bronger@physik.rwth-aachen.de"),
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "juliabase",
        "USER": "juliabase",
        "PASSWORD": "12345",
        "ATOMIC_REQUESTS": True
        }
    }

TIME_ZONE = "Europe/Berlin"

LANGUAGE_CODE = "en-us"

USE_I18N = True
USE_L10N = False
DATETIME_FORMAT = "D, j. N Y, H:i:s"
DATE_FORMAT = "D, j. N Y"


STATIC_ROOT = str("/var/www/juliabase/static/")
MEDIA_ROOT = str("/var/www/juliabase/uploads")


# Make sure to use a trailing slash if there is a path component (optional in
# other cases).  Examples: "http://media.lawrence.com",
# "http://example.com/static/"
STATIC_URL = str("/static/")

ADMIN_MEDIA_PREFIX = STATIC_URL + str("admin/")

SECRET_KEY = get_secret_key_from_file("~/.juliabase_secret_key")

# The reason why we use ``django.template.loaders.filesystem.Loader`` and
# ``TEMPLATE_DIRS`` is that we want to be able to extend the overridden
# template.  This is used in institute's "sample claim" views, for example.
TEMPLATE_DIRS = (BASE_DIR,)
TEMPLATE_LOADERS = (
    ("django.template.loaders.cached.Loader", ("django.template.loaders.app_directories.Loader",
                                               "django.template.loaders.filesystem.Loader")),)

MIDDLEWARE_CLASSES = (
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "jb_common.middleware.MessageMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "jb_common.middleware.LocaleMiddleware",
    "samples.middleware.juliabase.ExceptionsMiddleware",
    "jb_common.middleware.JSONClientMiddleware",
)
APPEND_SLASH = False

ROOT_URLCONF = str("urls")

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "institute",
    "samples",
    "jb_common"
)

TEMPLATE_CONTEXT_PROCESSORS = ("django.contrib.auth.context_processors.auth",
                               "django.core.context_processors.debug",
                               "django.core.context_processors.i18n",
                               "django.core.context_processors.media",
                               "django.core.context_processors.static",
                               "django.core.context_processors.tz",
                               "django.contrib.messages.context_processors.messages",
                               "jb_common.context_processors.default",
                               "institute.context_processors.default")

JAVASCRIPT_I18N_APPS += ("institute",)

LOGIN_URL = "/login"
LOGIN_REDIRECT_URL = "/"

# This determines which flags are shown
LANGUAGES = (("en", _("English")), ("de", _("German")))

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": ["localhost"],
        "TIMEOUT": 3600 * 24 * 28
        }
    }
# CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

CACHE_MIDDLEWARE_SECONDS = 60 * 60 * 24
CACHE_MIDDLEWARE_KEY_PREFIX = ""

ADD_SAMPLES_VIEW = "institute.views.samples.sample.add"

MEASUREMENT_DATA_ROOT_DIR = os.path.join(BASE_DIR, str("remote_client"), str("examples"))
PDS_ROOT_DIR = os.path.join(MEASUREMENT_DATA_ROOT_DIR, str("pds_raw_data"))
SOLARSIMULATOR_1_ROOT_DIR = os.path.join(MEASUREMENT_DATA_ROOT_DIR, str("solarsimulator_raw_data"))

MERGE_CLEANUP_FUNCTION = "institute.utils.clean_up_after_merging"

SAMPLE_NAME_FORMATS = {
    "provisional": {"possible_renames": {"new"}},
    "old":         {"pattern": r"{short_year}[A-Z]-\d{{3,4}}([-A-Za-z_/][-A-Za-z_/0-9#()]*)?",
                    "possible_renames": {"new"},
                    "verbose_name": _("old-style")},
    "new":         {"pattern": r"({short_year}-{user_initials}|{external_contact_initials})-[-A-Za-z_/0-9#()]+",
                    "verbose_name": _("new-style")}
}

NAME_PREFIX_TEMPLATES = ("{short_year}-{user_initials}-", "{external_contact_initials}-")
