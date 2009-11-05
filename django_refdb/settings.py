#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.  Django-RefDB is published under the MIT
# license.  A copy of this licence is shipped with Django-RefDB in the file
# LICENSE.
#
# Django settings for django_refdb project.


DEBUG = True
TEMPLATE_DEBUG = DEBUG

import sys
if "/home/bronger/src/pyrefdb/main/" not in sys.path:
    sys.path.append("/home/bronger/src/pyrefdb/main/")
sys.path.append("/home/bronger/src/chantal_ipv/current/")

IS_TESTSERVER = len(sys.argv) >= 2
WITH_EPYDOC = 'epydoc' in sys.modules

import ConfigParser, os.path
credentials = ConfigParser.SafeConfigParser()
read_files = credentials.read(os.path.expanduser("~/django-refdb.auth"))
assert read_files, Exception("file with authentication data not found")
CREDENTIALS = dict(credentials.items("DEFAULT"))

ROOTDIR = os.path.dirname(os.path.abspath(__file__))

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASE_ENGINE = 'postgresql_psycopg2'  # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = 'django-refdb' # Or path to database file if using sqlite3.
DATABASE_USER = CREDENTIALS["postgresql_user"]            # Not used with sqlite3.
DATABASE_PASSWORD = CREDENTIALS["postgresql_password"]    # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(ROOTDIR, 'media/')
STATIC_ROOT = MEDIA_ROOT

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/admin/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = CREDENTIALS["salt"]

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.app_directories.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
    'chantal_common.middleware.LocaleMiddleware',
    'refdb.middleware.TransactionMiddleware',
    'refdb.middleware.ConditionalViewMiddleware',
)

ROOT_URLCONF = 'urls'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.admin',
    'django.contrib.markup',
    'chantal_ipv',
    'chantal_common',
    'refdb',
    'staticfiles'
)

TEMPLATE_CONTEXT_PROCESSORS = ("django.core.context_processors.auth",
                               "django.core.context_processors.debug",
                               "django.core.context_processors.i18n",
                               "django.core.context_processors.media",
                               "refdb.context_processors.default",
                               "chantal_common.context_processors.default",
                               )

URL_PREFIX = "/" if IS_TESTSERVER else "/chantal/"
LOGIN_URL = URL_PREFIX + "login"
LOGIN_REDIRECT_URL = URL_PREFIX

LOCALES_DICT = {"en": "en_US.utf8", "de": "de_DE.utf8"}

CACHE_BACKEND = 'dummy:///'
CACHE_BACKEND = 'locmem:///'
CACHE_BACKEND = 'file:///var/tmp/django_cache'
CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

CACHE_MIDDLEWARE_SECONDS = 60 * 60 * 24
CACHE_MIDDLEWARE_KEY_PREFIX = ""


REFDB_USERNAME_PREFIX = "drefdbuser"
REFDB_USER = CREDENTIALS["refdb_user"]
REFDB_PASSWORD = CREDENTIALS["refdb_password"]
REFDB_CACHE_PREFIX = "refdb-reference-"
REFDB_PATH_TO_INDEXER = "/home/bronger/src/django-refdb/current/index_pdfs.py"
