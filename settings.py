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


"""Django settings for a generic JuliaBase installation.
"""

from __future__ import absolute_import, unicode_literals
# Python3 note: Below, there are some str() calls that should be removed with
# Python3.

import os
from django.utils.translation import ugettext_lazy as _
from jb_common.settings_defaults import *
from samples.settings_defaults import *


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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


STATIC_ROOT = str("/var/www/juliabase/media/")
MEDIA_ROOT = str("/var/www/juliabase/uploads")


# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
STATIC_URL = str("/media/")

ADMIN_MEDIA_PREFIX = STATIC_URL + str("admin/")

SECRET_KEY = "vew7ooes7bt7aetrb77wuhwe95zislisdfo8z"

# The reason why we use ``django.template.loaders.filesystem.Loader`` and
# ``TEMPLATE_DIRS`` is that we want to be able to extend the overridden
# template.  This is used in jb_institute's "sample claim" views, for example.
TEMPLATE_DIRS = (os.path.dirname(os.path.abspath(__file__)),)
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
    "jb_institute",
    "samples",
    "jb_common"
)

TEMPLATE_CONTEXT_PROCESSORS = ("django.contrib.auth.context_processors.auth",
                               "django.core.context_processors.debug",
                               "django.core.context_processors.i18n",
                               "django.core.context_processors.media",
                               "django.contrib.messages.context_processors.messages",
                               "jb_common.context_processors.default",
                               "jb_institute.context_processors.default",
                               "django.core.context_processors.static")

JAVASCRIPT_I18N_APPS += ("jb_institute",)

DOMAIN_NAME = "0.0.0.0:8000"
PROTOCOL = "http"

LOGIN_URL = "{0}://{1}/login".format(PROTOCOL, DOMAIN_NAME)
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

DEPARTMENTS_TO_APP_LABELS = {"Institute": "jb_institute"}

ADD_SAMPLES_VIEW = "jb_institute.views.samples.sample.add"

MEASUREMENT_DATA_ROOT_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), str("remote_client"), str("examples"))
PDS_ROOT_DIR = os.path.join(MEASUREMENT_DATA_ROOT_DIR, str("pds_raw_data"))
SOLARSIMULATOR_1_ROOT_DIR = os.path.join(MEASUREMENT_DATA_ROOT_DIR, str("solarsimulator_raw_data"))

PHYSICAL_PROCESSES_BLACKLIST = [("jb_institute", "substrate")]
MERGE_CLEANUP_FUNCTION = "jb_institute.utils.clean_up_after_merging"

SAMPLE_NAME_FORMATS = {
    "provisional": {"possible renames": {"new"}},
    "old":         {"pattern": r"{short_year}[A-Z]-\d{{3,4}}([-A-Za-z_/][-A-Za-z_/0-9#()]*)?",
                    "possible renames": {"new"},
                    "verbose name": _("old-style")},
    "new":         {"pattern": r"({short_year}-{user_initials}|{external_contact_initials})-[-A-Za-z_/0-9#()]+",
                    "verbose name": _("new-style")}
}

NAME_PREFIX_TEMPLATES = ("{short_year}-{user_initials}-", "{external_contact_initials}-")
