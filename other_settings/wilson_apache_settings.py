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

from other_settings.wilson_settings import *

DATABASES["default"]["NAME"] = "chantal_apache"

MIDDLEWARE_CLASSES = (
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "chantal_common.middleware.MessageMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.transaction.TransactionMiddleware",
    "chantal_common.middleware.LocaleMiddleware",
    "refdb.middleware.TransactionMiddleware",
    "refdb.middleware.ConditionalViewMiddleware",
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
    "south",
    "refdb",
    "samples",
    "kicker",
    "chantal_common",
)

TEMPLATE_CONTEXT_PROCESSORS = ("django.contrib.auth.context_processors.auth",
                               "django.core.context_processors.debug",
                               "django.core.context_processors.i18n",
                               "django.core.context_processors.media",
                               "django.contrib.messages.context_processors.messages",
                               "refdb.context_processors.default",
                               "chantal_common.context_processors.default",
                               "django.core.context_processors.static")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": "127.0.0.1:11211",
        "TIMEOUT": 3600 * 24 * 28
        }
    }

REFDB_PATH_TO_INDEXER = "/home/bronger/src/django-refdb/current/index_pdfs.py"
