#!/usr/bin/env python3
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

import os

settings = {"ADDITIONAL_LDAP_USERS": "LDAP_ADDITIONAL_USERS",
            "AD_LDAP_ACCOUNT_FILTER": "LDAP_ACCOUNT_FILTER",
            "AD_LDAP_DEPARTMENTS": "LDAP_DEPARTMENTS",
            "AD_LDAP_URLS": "LDAP_URLS",
            "AD_SEARCH_DN": "LDAP_SEARCH_DN",
            "AD_USERNAME_TEMPLATE": "LDAP_LOGIN_TEMPLATE",
            "LDAP_ADDITIONAL_ATTRIBUTES": "LDAP_ADDITIONAL_ATTRIBUTES",
            "PERMISSIONS_OF_AD_GROUPS": "LDAP_GROUPS_TO_PERMISSIONS",
            "MAP_DEPARTMENTS_TO_APP_LABELS": "DEPARTMENTS_TO_APP_LABELS",
            "ADD_SAMPLE_VIEW": "ADD_SAMPLES_VIEW"}


for root, __, filenames in os.walk("."):
    if ".git" not in root:
        for filename in filenames:
            if filename != "rename_settings.py" and os.path.splitext(filename)[1] not in [".pyc", ".mo", ".png", ".ico", ".doctree",
                                                                                          ".pickle", ".gif", ".inv"]:
                filepath = os.path.join(root, filename)
                try:
                    content = raw_content = open(filepath).read()
                except UnicodeDecodeError:
                    continue
                for setting, replacement in settings.items():
                    content = content.replace(setting, replacement)
                if content != raw_content:
                    if os.path.splitext(filename)[1] in [".py", ".txt"]:
                        open(filepath, "w").write(content)
                        print(filepath, "changed.")
                    else:
                        print(filepath, "not changed.")
