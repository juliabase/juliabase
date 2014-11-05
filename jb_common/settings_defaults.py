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

from django.utils.translation import ugettext_lazy as _


JB_DEPARTMENTS = ["Institute"]
DEBUG_EMAIL_REDIRECT_USERNAME = "t.bronger"
JAVASCRIPT_I18N_APPS =
LOCALES_DICT =
TESTING =
USE_X_SENDFILE =

# LDAP-related settings

ADDITIONAL_LDAP_USERS =
AD_LDAP_ACCOUNT_FILTER =
AD_LDAP_URLS =
AD_SEARCH_DN =
AD_SEARCH_FIELDS =
AD_USERNAME_TEMPLATE =
PERMISSIONS_OF_AD_GROUPS =

# Django settings which are used in jb_common

LANGUAGES = (("en", _("English")), ("de", _("German")))
DEBUG =
DEFAULT_FROM_EMAIL =
LOGIN_REDIRECT_URL =
TEMPLATE_CONTEXT_PROCESSORS =
