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


"""Django settings for IEK-PV's Chantal installation.
"""

from __future__ import unicode_literals
import sys, ConfigParser, os.path, copy
from django.conf.global_settings import LOGGING as OLD_LOGGING


DEBUG = False
TEMPLATE_DEBUG = DEBUG
TESTING = len(sys.argv) >= 2 and sys.argv[0].endswith("manage.py") and sys.argv[1] == "test"

IS_TESTSERVER = "runserver" in sys.argv
WITH_EPYDOC = "epydoc" in sys.modules


credentials = ConfigParser.SafeConfigParser()
read_files = credentials.read(["/var/www/chantal.auth", os.path.expanduser("~/chantal.auth")])
assert read_files, Exception("file with authentication data not found")
CREDENTIALS = dict(credentials.items("DEFAULT"))


DEFAULT_FROM_EMAIL = "t.bronger@fz-juelich.de"
EMAIL_HOST = "mailrelay.fz-juelich.de"
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
        "USER": CREDENTIALS["postgresql_user"],
        "PASSWORD": CREDENTIALS["postgresql_password"],
        "HOST": "192.168.26.132"
        }
    }

TIME_ZONE = "Europe/Berlin"

LANGUAGE_CODE = "en-us"

SITE_ID = 1

# FixMe: When switching to Django 1.4 for good, remove this setting entirely.
PASSWORD_HASHERS = (
#    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
#    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
#    "django.contrib.auth.hashers.BCryptPasswordHasher",
    "django.contrib.auth.hashers.SHA1PasswordHasher",
#    "django.contrib.auth.hashers.MD5PasswordHasher",
#    "django.contrib.auth.hashers.CryptPasswordHasher",
)

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

SECRET_KEY = CREDENTIALS["salt"]

# The reason why we use ``django.template.loaders.filesystem.Loader`` and
# ``TEMPLATE_DIRS`` is that we want to be able to extend the overridden
# template.  This is used in chantal_ipv's "sample claim" views, for example.
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
    "django.middleware.transaction.TransactionMiddleware",
    "chantal_common.middleware.LocaleMiddleware",
#    "refdb.middleware.TransactionMiddleware",
#    "refdb.middleware.ConditionalViewMiddleware",
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
    "django.contrib.markup",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "chantal_ipv",
    "samples",
#    "refdb",
    "south",
    "kicker",
    "visiting",
    "chantal_common"
)

TEMPLATE_CONTEXT_PROCESSORS = ("django.contrib.auth.context_processors.auth",
                               "django.core.context_processors.debug",
                               "django.core.context_processors.i18n",
                               "django.core.context_processors.media",
                               "django.contrib.messages.context_processors.messages",
#                               "refdb.context_processors.default",
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
        "LOCATION": ["192.168.26.130:11211", "192.168.26.131:11211"],
        "TIMEOUT": 3600 * 24 * 28
        }
    }
# CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

CACHE_MIDDLEWARE_SECONDS = 60 * 60 * 24
CACHE_MIDDLEWARE_KEY_PREFIX = ""


LOGGING = copy.deepcopy(OLD_LOGGING)
LOGGING["handlers"]["mail_admins"]["class"] = "log.AdminEmailHandler"


REFDB_USERNAME_PREFIX = "drefdbuser"
REFDB_ROOT_USERNAME = CREDENTIALS["refdb_user"]
REFDB_ROOT_PASSWORD = CREDENTIALS["refdb_password"]
REFDB_CACHE_PREFIX = "refdb-reference-"
REFDB_PATH_TO_INDEXER = b"/home/chantal/refdb/index_pdfs.py"


import subprocess, re, time, glob
def _scan_version(package):
    try:
        dpgk = subprocess.Popen(["dpkg-query", "--show", package], stdout=subprocess.PIPE)
        match = re.match(re.escape(package) + r"\t(?P<version>.+?)-", dpgk.communicate()[0].strip())
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
AD_DNS_NAME = "dc-e01.ad.fz-juelich.de"
AD_LDAP_PORT = 636
AD_SEARCH_DN = "DC=ad,DC=fz-juelich,DC=de"
# This is the NT4/Samba domain name
AD_NT4_DOMAIN = "fzj"
AD_SEARCH_FIELDS = [b"mail", b"givenName", b"sn", b"department", b"telephoneNumber", b"msExchUserCulture",
                    b"generationQualifier", b"physicalDeliveryOfficeName", b"memberOf"]
AD_LDAP_URL = "ldaps://{0}:{1}".format(AD_DNS_NAME, AD_LDAP_PORT)
AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend", "chantal_ipv.auth.ActiveDirectoryBackend")

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

ADDITIONAL_LDAP_USERS = set(["r.imlau", "a.kuvacs", "m.luysberg"])

ADD_SAMPLE_VIEW = "chantal_ipv.views.samples.sample.add"

MEASUREMENT_DATA_ROOT_DIR = b"/mnt/T/Daten/"
PDS_ROOT_DIR = os.path.join(MEASUREMENT_DATA_ROOT_DIR, b"pds")
LUMA_ROOT_DIR = os.path.join(MEASUREMENT_DATA_ROOT_DIR, b"luma")
DSR_ROOT_DIR = b"/mnt/P/USER/w.reetz/DSR/Messwerte/"
IR_ROOT_DIR = b"/mnt/IR/"
PHYSICAL_PROCESS_BLACKLIST = [("chantal_ipv", "substrate"),
                              ("chantal_ipv", "layerthicknessmeasurement")]
SOLARSIMULATOR_1_ROOT_DIR = b"/mnt/P/LABOR USER/maike_user/ascii files/"
LADA_MFC_CALIBRATION_FILE_PATH = b"/mnt/modultechnologie/lada_mfc_calibrations.txt"
MERGE_CLEANUP_FUNCTION = "chantal_ipv.utils.clean_up_after_merging"
ERMES_OPTICAL_DATA_ROOT_DIR = b"/mnt/P/USER/m.ermes/optical_data/"

CRAWLER_LOGS_ROOT = b"/home/chantal/crawler_data"
CRAWLER_LOGS_WHITELIST = set(["ConductivityMeasurementSet", "SolarsimulatorPhotoMeasurement"])
