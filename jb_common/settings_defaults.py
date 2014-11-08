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


"""Default values of jb_common settings."""

import sys
from django.utils.translation import ugettext_lazy as _


DEBUG_EMAIL_REDIRECT_USERNAME = ""
JAVASCRIPT_I18N_APPS = ("django.contrib.auth", "samples", "jb_common")
USE_X_SENDFILE = False

# LDAP-related settings

LDAP_ACCOUNT_FILTER = "(!(userAccountControl:1.2.840.113556.1.4.803:=2))"
LDAP_ADDITIONAL_ATTRIBUTES = ()
LDAP_ADDITIONAL_USERS = {}
LDAP_DEPARTMENTS = {}
LDAP_GROUPS_TO_PERMISSIONS = {}
LDAP_LOGIN_TEMPLATE = "{username}"
LDAP_SEARCH_DN = ""
LDAP_URLS = ()

# Django settings which are used in jb_common

# LANGUAGES
# DEBUG
# DEFAULT_FROM_EMAIL
# LOGIN_REDIRECT_URL
# TEMPLATE_CONTEXT_PROCESSORS
