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

app_dirs = ("/home/marvin/probendatenbank/chantal_common/current",
            "/home/marvin/probendatenbank/chantal_samples/current",
            "/home/marvin/probendatenbank/chantal_ipv/current")
sys.path.extend(app_dirs)

DEFAULT_FROM_EMAIL = "m.goblet@fz-juelich.de"
SERVER_EMAIL = DEFAULT_FROM_EMAIL
ADMINS = (
    ("Marvin Goblet", "m.goblet@fz-juelich.de"),
)
DEBUG_EMAIL_REDIRECT_USERNAME = ""

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

TEMPLATE_DIRS = app_dirs
TEMPLATE_LOADERS = ("django.template.loaders.app_directories.Loader", "django.template.loaders.filesystem.Loader")

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.admin",
    "django.contrib.markup",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "chantal_ipv",
    "chantal_common",
    "samples",
    "south"
)

DOMAIN_NAME = "127.0.0.1:8000"

LOGIN_URL = "http://{0}/login".format(DOMAIN_NAME)
LOGIN_REDIRECT_URL = "/"

CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

CACHE_MIDDLEWARE_SECONDS = 60 * 60 * 24
CACHE_MIDDLEWARE_KEY_PREFIX = ""

def _scan_version(package):
    dpgk = subprocess.Popen(["rpm", "-q", package], stdout=subprocess.PIPE)
    match = re.match(re.escape(package) + r"\t(?P<version>.+?)-", dpgk.communicate()[0].strip())
    return match.group("version") if match else None
APACHE_VERSION = _scan_version("httpd")
APACHE_STARTUP_TIME = 0
POSTGRESQL_VERSION = _scan_version("postgresql")
POSTGRESQL_STARTUP_TIME = 0
PYTHON_VERSION = _scan_version("python")
MATPLOTLIB_VERSION = _scan_version("python-matplotlib")



#REFDB_ROOT_USERNAME = CREDENTIALS["refdb_user"]
#REFDB_ROOT_PASSWORD = CREDENTIALS["refdb_password"]
#REFDB_PATH_TO_INDEXER = "/home/bronger/src/django-refdb/current/index_pdfs.py"


AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)
LADA_MFC_CALIBRATION_FILE_PATH = b"/home/marvin/Dokumente/LADA/lada_mfc_calibrations.txt"
SOLARSIMULATOR_1_ROOT_DIR = b"/mnt/user_public/LABOR USER/maike_user/ascii files/"
ERMES_OPTICAL_DATA_ROOT_DIR = b"/mnt/user_public/USER/m.ermes/optical_data/"
DSR_ROOT_DIR = b"/mnt/user_public/USER/w.reetz/DSR/Messwerte/"
