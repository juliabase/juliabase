#!/usr/bin/env python

from __future__ import absolute_import

from django.core.management import execute_manager
try:
    import settings # Assumed to be in the same directory.
except ImportError:
    import sys
    sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
    sys.exit(1)

import os
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"
import django.contrib.auth.management
def _get_only_custom_permissions(opts):
    return list(opts.permissions)
django.contrib.auth.management._get_all_permissions = _get_only_custom_permissions

if __name__ == "__main__":
    execute_manager(settings)
