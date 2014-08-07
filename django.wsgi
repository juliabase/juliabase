# -*- mode: python -*-

import os
import sys

sys.path.append("/home/bronger/src/chantal_institute")
sys.stdout = sys.stderr

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ['MPLCONFIGDIR'] = '/home/bronger/.config/matplotlib'

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
