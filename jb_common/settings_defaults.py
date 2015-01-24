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

import sys, os
from django.utils.translation import ugettext_lazy as _, ugettext
from django.utils.crypto import get_random_string


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

def get_secret_key_from_file(filepath):
    """Returns the secret key used for the Django setting ``SECRET_KEY`` in your
    ``settings.py``.  It reads it from the given file.  If this file doesn't
    exist, a new key is generated and stored in that file.  This has the
    benefit of not having the secret key in ``settings.py``, which may be part
    of your revisioned source code repository.  Besides, this function
    simplifies bootstrapping.

    :param filepath: path to the file that stores the secret key.  It may
        contain a tilde ``~``.

    :type filepath: str

    :return:
      The secret key.

    :rtype: str
    """
    filepath = os.path.abspath(os.path.expanduser(filepath))
    try:
        secret_key = open(filepath).read().strip()
    except IOError:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
        secret_key = get_random_string(50, chars)
        with open(filepath, "w") as outfile:
            outfile.write(secret_key)
        os.chmod(filepath, 0o600)
    return secret_key


_ = ugettext
