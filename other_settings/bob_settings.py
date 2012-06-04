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

import sys
sys.path.extend(["/home/chantal/repos/chantal_common/bob_online",
                 "/home/chantal/repos/chantal_samples/bob_online",
                 "/home/chantal/repos/businesscards/bob_online",
                 "/home/chantal/repos/chantal_kicker/bob_online"])

DEFAULT_FROM_EMAIL = "bronger@physik.rwth-aachen.de"
SERVER_EMAIL = DEFAULT_FROM_EMAIL
ADMINS = (
    ("Torsten Bronger", "bronger@physik.rwth-aachen.de"),
)

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

TEMPLATE_DIRS = ("/home/chantal/repos/chantal_ipv/bob_online", "/home/chantal/repos/chantal_common/bob_online",
                 "/home/chantal/repos/chantal_samples/bob_online", "/home/chantal/repos/businesscards/bob_online")

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
    "visiting",
    "kicker",
    "chantal_common",
    "south"
)

DOMAIN_NAME = "bob.ipv.kfa-juelich.de"

LOGIN_URL = "http://{0}/login".format(DOMAIN_NAME)
LOGIN_REDIRECT_URL = "/"

# CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
# CACHES = {"default": {"BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
#                       "LOCATION": "/var/tmp/django_cache",
#                       "TIMEOUT": 3600 * 24 * 28}}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": "127.0.0.1:11211",
        "TIMEOUT": 3600 * 24 * 28
        }
    }

CACHE_MIDDLEWARE_SECONDS = 60 * 60 * 24
CACHE_MIDDLEWARE_KEY_PREFIX = ""


REFDB_ROOT_USERNAME = CREDENTIALS["refdb_user"]
REFDB_ROOT_PASSWORD = CREDENTIALS["refdb_password"]
REFDB_PATH_TO_INDEXER = "/home/bronger/src/django-refdb/current/index_pdfs.py"


#AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

MEASUREMENT_DATA_ROOT_DIR = b"/windows/T/Daten/"
PDS_ROOT_DIR = os.path.join(MEASUREMENT_DATA_ROOT_DIR, b"pds")
DSR_ROOT_DIR = b"/windows/user_public/USER/w.reetz/DSR/Messwerte/"
IR_ROOT_DIR = b"/windows/IR/"
SOLARSIMULATOR_1_ROOT_DIR = b"/windows/P/LABOR USER/maike_user/ascii files/"
