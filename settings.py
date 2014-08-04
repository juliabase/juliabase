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


"""Django settings for a generic Chantal installation.
"""

from __future__ import absolute_import, unicode_literals
import sys, ConfigParser, os.path, copy
from django.conf.global_settings import LOGGING as OLD_LOGGING


ALLOWED_HOSTS = ["chantal.ipv.kfa-juelich.de"]
DEBUG = False
TEMPLATE_DEBUG = DEBUG
TESTING = len(sys.argv) >= 2 and sys.argv[0].endswith("manage.py") and sys.argv[1] == "test"

IS_TESTSERVER = "runserver" in sys.argv
WITH_EPYDOC = "epydoc" in sys.modules


DEFAULT_FROM_EMAIL = ""
EMAIL_HOST = ""
SERVER_EMAIL = DEFAULT_FROM_EMAIL
ADMINS = (
    ("Chantal-Admins", "chantal-admins@googlegroups.com"),
)
# If DEBUG == True, all outgoing email is redirected to this account.  If
# empty, don't send any email at all.
DEBUG_EMAIL_REDIRECT_USERNAME = "t.bronger"

MANAGERS = ADMINS

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "chantal",
        "USER": "bronger",
        "PASSWORD": "topsecret",   # This is a dummy password that the world is allowed to know
        "ATOMIC_REQUESTS": True
        }
    }

TIME_ZONE = "Europe/Berlin"

LANGUAGE_CODE = "en-us"

SITE_ID = 1

USE_I18N = True
USE_L10N = False
DATETIME_FORMAT = "D, j. N Y, H:i:s"
DATE_FORMAT = "D, j. N Y"


STATIC_ROOT = b"/var/www/chantal/media/"
MEDIA_ROOT = b"/var/www/chantal/uploads"
CACHE_ROOT = b"/var/cache/chantal"

USE_X_SENDFILE = True


# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
STATIC_URL = b"/media/"

ADMIN_MEDIA_PREFIX = STATIC_URL + b"admin/"

SECRET_KEY = "fdsfdsjdfsjlofsldj"

# The reason why we use ``django.template.loaders.filesystem.Loader`` and
# ``TEMPLATE_DIRS`` is that we want to be able to extend the overridden
# template.  This is used in chantal_institute's "sample claim" views, for example.
TEMPLATE_DIRS = (os.path.dirname(os.path.abspath(__file__)),)
TEMPLATE_LOADERS = (
    ("django.template.loaders.cached.Loader", ("django.template.loaders.app_directories.Loader",
                                               "django.template.loaders.filesystem.Loader")),)

MIDDLEWARE_CLASSES = (
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "chantal_common.middleware.MessageMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "chantal_common.middleware.LocaleMiddleware",
    "samples.middleware.chantal.ExceptionsMiddleware",
    "chantal_common.middleware.JSONClientMiddleware",
)
APPEND_SLASH = False

ROOT_URLCONF = b"urls"

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "chantal_institute",
    "samples",
    "south",
    "chantal_common"
)

TEMPLATE_CONTEXT_PROCESSORS = ("django.contrib.auth.context_processors.auth",
                               "django.core.context_processors.debug",
                               "django.core.context_processors.i18n",
                               "django.core.context_processors.media",
                               "django.contrib.messages.context_processors.messages",
                               "chantal_common.context_processors.default",
                               "django.core.context_processors.static")

# FixMe: Maybe too many?
JAVASCRIPT_I18N_APPS = INSTALLED_APPS

DOMAIN_NAME = "chantal.ipv.kfa-juelich.de"
PROTOCOL = "https"

LOGIN_URL = "{0}://{1}/login".format(PROTOCOL, DOMAIN_NAME)
LOGIN_REDIRECT_URL = "/"

# FixMe: LOCALES_DICT should be generated from
# /var/lib/locales/supported.d/local
LOCALES_DICT = {"en": ("en_US", "UTF8"), "de": ("de_DE", "UTF8")}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": ["192.168.XX.XX:11211"],
        "TIMEOUT": 3600 * 24 * 28
        }
    }
# CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

CACHE_MIDDLEWARE_SECONDS = 60 * 60 * 24
CACHE_MIDDLEWARE_KEY_PREFIX = ""


import subprocess, re, time, glob
def _scan_version(package):
    try:
        dpgk = subprocess.Popen(["dpkg-query", "--show", package], stdout=subprocess.PIPE)
        match = re.match(re.escape(package) + r"\t(?P<version>.+?)[-+]", dpgk.communicate()[0].strip())
        return match.group("version") if match else None
    except OSError:
        return 0
APACHE_VERSION = _scan_version("apache2")
APACHE_STARTUP_TIME = 0
POSTGRESQL_VERSION = _scan_version("postgresql")
POSTGRESQL_STARTUP_TIME = 0
PYTHON_VERSION = _scan_version("python")
MATPLOTLIB_VERSION = _scan_version("python-matplotlib")
try:
    CHANTAL_REVNO = open("/tmp/chantal_revision").read()
except IOError:
    CHANTAL_REVNO = 0


THUMBNAIL_WIDTH = 400


# LDAP binding
AD_DNS_NAMES = ["dc-e01.ad.fz-juelich.de", "dc-e02.ad.fz-juelich.de"]
AD_LDAP_PORT = 636
AD_SEARCH_DN = "DC=ad,DC=fz-juelich,DC=de"
# This is the NT4/Samba domain name
AD_NT4_DOMAIN = "fzj"
AD_SEARCH_FIELDS = [b"mail", b"givenName", b"sn", b"department", b"telephoneNumber", b"msExchUserCulture",
                    b"generationQualifier", b"physicalDeliveryOfficeName", b"memberOf"]
AD_LDAP_URLS = ["ldaps://{0}:{1}".format(AD_DNS_NAME, AD_LDAP_PORT) for AD_DNS_NAME in AD_DNS_NAMES]
AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend", "chantal_common.auth.ActiveDirectoryBackend")

# Dictionary mapping LDAP group names to sets of Django permission names.  Use
# the ``codename`` of the permission, in particular, without any app label.
PERMISSIONS_OF_AD_GROUPS = {"TG_IEF-5_Gruppenleiter": set(["view_all_samples", "adopt_samples",
                                                           "edit_permissions_for_all_physical_processes",
                                                           "add_external_operator",
                                                           "view_all_external_operators", "can_edit_all_topics"])}

# Permission names which are managed by the Active Directory.  This means that
# a user get these permissions only if he is a member of a group in
# ``PERMISSIONS_OF_AD_GROUPS`` which grants the respective permission.  All
# permissions *not* mentioned here can be set via Django's admin interface.
AD_MANAGED_PERMISSIONS = set(["view_all_samples", "adopt_samples", "edit_permissions_for_all_physical_processes",
                              "view_all_external_operators", "can_edit_all_topics"])

# Set of usernames of LDAP users which should be allowed to log in (as long as
# they exist in the LDAP directory).  This comes in handy for members of
# neighbour instituts who need to use the IEK-PV database, too.  The
# alternative would be a full-fledged Django account with locally stored
# password, which means bigger maintenance work for the Chantal administrator.

ADDITIONAL_LDAP_USERS = set([])

# The cryptic ``!(userAccountControl...)`` filters out all inactive
# accounts (i.e. former institute members).
AD_LDAP_ACCOUNT_FILTER = "(!(userAccountControl:1.2.840.113556.1.4.803:=2))"

CHANTAL_DEPARTMENTS = ["Institute"]

MAP_DEPARTMENTS_TO_APP_LABELS = {"Institute": "chantal_institute"}

ADD_SAMPLE_VIEW = "chantal_institute.views.samples.sample.add"

MEASUREMENT_DATA_ROOT_DIR = b""
PDS_ROOT_DIR = os.path.join(MEASUREMENT_DATA_ROOT_DIR, b"pds")

PHYSICAL_PROCESS_BLACKLIST = [("chantal_institute", "substrate"),
                              ("chantal_institute", "layerthicknessmeasurement")]
SOLARSIMULATOR_1_ROOT_DIR = b""
MERGE_CLEANUP_FUNCTION = "chantal_institute.utils.clean_up_after_merging"

CRAWLER_LOGS_ROOT = b""
CRAWLER_LOGS_WHITELIST = set([])
