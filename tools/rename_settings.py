# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


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
