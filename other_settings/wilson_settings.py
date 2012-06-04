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


from __future__ import absolute_import, unicode_literals

from settings import *

DEBUG = True
TEMPLATE_DEBUG = DEBUG

from django.contrib.messages import constants as message_constants
#MESSAGE_LEVEL = message_constants.DEBUG

import sys
if "/home/bronger/src/pyrefdb/main/" not in sys.path:
    sys.path.append("/home/bronger/src/pyrefdb/main/")
app_dirs = ("/home/bronger/src/django-refdb/current",
            "/home/bronger/src/chantal_common/current",
            "/home/bronger/src/chantal_samples/current",
            "/home/bronger/src/chantal_kicker/current")
sys.path.extend(app_dirs)

EMAIL_HOST = "relay.rwth-aachen.de"
DEFAULT_FROM_EMAIL = "bronger@physik.rwth-aachen.de"
SERVER_EMAIL = DEFAULT_FROM_EMAIL
ADMINS = (
    ("Torsten Bronger", "bronger@physik.rwth-aachen.de"),
)
DEBUG_EMAIL_REDIRECT_USERNAME = "bronger"

MANAGERS = ADMINS

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "chantal",
        "USER": CREDENTIALS["postgresql_user"],
        "PASSWORD": CREDENTIALS["postgresql_password"]
        }
    }

STATIC_ROOT = b"/tmp/chantal/media/"
MEDIA_ROOT = b"/tmp/chantal/uploads"
CACHE_ROOT = b"/tmp/chantal/cache"

USE_X_SENDFILE = False

TEMPLATE_DIRS = app_dirs
TEMPLATE_LOADERS = ("django.template.loaders.app_directories.Loader", "django.template.loaders.filesystem.Loader")

MIDDLEWARE_CLASSES = (
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "chantal_common.middleware.MessageMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.transaction.TransactionMiddleware",
    "chantal_common.middleware.LocaleMiddleware",
#    "refdb.middleware.TransactionMiddleware",
#    "refdb.middleware.ConditionalViewMiddleware",
    "samples.middleware.chantal.ExceptionsMiddleware",
    "chantal_common.middleware.JSONClientMiddleware",
)

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.admin",
    "django.contrib.markup",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "chantal_ipv",
#    "refdb",
    "samples",
    "kicker",
    "chantal_common",
)

DOMAIN_NAME = "127.0.0.1:8000"

LOGIN_URL = "/login".format(DOMAIN_NAME)
LOGIN_REDIRECT_URL = "/"

# CACHES = {"default": {"BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
#                       "LOCATION": "/var/tmp/django_cache",
#                       "TIMEOUT": 3600 * 24 * 28}}
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
#         "LOCATION": "127.0.0.1:11211",
#         "TIMEOUT": 3600 * 24 * 28
#         }
#     }
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

CACHE_MIDDLEWARE_SECONDS = 60 * 60 * 24
CACHE_MIDDLEWARE_KEY_PREFIX = ""


REFDB_ROOT_USERNAME = CREDENTIALS["refdb_user"]
REFDB_ROOT_PASSWORD = CREDENTIALS["refdb_password"]
REFDB_PATH_TO_INDEXER = "/home/bronger/src/django-refdb/current/index_pdfs.py"


AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

MEASUREMENT_DATA_ROOT_DIR = b"/tmp/Daten/"
