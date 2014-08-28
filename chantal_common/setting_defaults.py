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


"""Default values of chantal_common settings."""

from django.utils.translation import ugettext_lazy as _


# ==============================================================================
# Settings in chantal_common

CHANTAL_DEPARTMENTS =
DEBUG_EMAIL_REDIRECT_USERNAME =
JAVASCRIPT_I18N_APPS =
LOCALES_DICT =
TESTING =
USE_X_SENDFILE =

# LDAP-related settings

ADDITIONAL_LDAP_USERS =
AD_LDAP_ACCOUNT_FILTER =
AD_LDAP_URLS =
AD_MANAGED_PERMISSIONS =
AD_NT4_DOMAIN =
AD_SEARCH_DN =
AD_SEARCH_FIELDS =
PERMISSIONS_OF_AD_GROUPS =

# Django settings which are used in chantal_common

LANGUAGES = (("en", _("English")), ("de", _("German")))
DEBUG =
DEFAULT_FROM_EMAIL =
LOGIN_REDIRECT_URL =
TEMPLATE_CONTEXT_PROCESSORS =


# ==============================================================================
# Settings in samples

CACHE_ROOT =
MAP_DEPARTMENTS_TO_APP_LABELS =
THUMBNAIL_WIDTH =
CRAWLER_LOGS_WHITELIST =
CRAWLER_LOGS_ROOT =
PHYSICAL_PROCESS_BLACKLIST =
IS_TESTSERVER =
ADD_SAMPLE_VIEW =
MERGE_CLEANUP_FUNCTION =
PROTOCOL =
DOMAIN_NAME =

# Django settings which are used in samples

MEDIA_ROOT =
SECRET_KEY =
STATIC_ROOT =
STATIC_URL =
INSTALLED_APPS =
CACHES =


# ==============================================================================
# Settings in institute

PDS_ROOT_DIR =
SOLARSIMULATOR_1_ROOT_DIR =

# Django settings which are used in institute

DEBUG =
INSTALLED_APPS =
STATIC_ROOT =
INTERNAL_IPS =


# ==============================================================================
# Settings in ipv

SNOM_ROOT_DIR =
APACHE_VERSION =
DSR_ROOT_DIR =
LUMA_ROOT_DIR =
PDS_ROOT_DIR =
CHANTAL_REVNO =
SOLARSIMULATOR_1_ROOT_DIR =
POSTGRESQL_VERSION =
IR_ROOT_DIR =
PYTHON_VERSION =
MEASUREMENT_DATA_ROOT_DIR =
MATPLOTLIB_VERSION =
LADA_MFC_CALIBRATION_FILE_PATH =
SPECTROMETER_ROOT_DIR =
ERMES_OPTICAL_DATA_ROOT_DIR =

# Django settings which are used in ipv

DEBUG =
INTERNAL_IPS =
INSTALLED_APPS =
STATIC_ROOT =
CACHES =
SESSION_ENGINE =
