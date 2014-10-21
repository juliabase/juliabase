# -*- mode: python -*-

import os
import sys

sys.path.append("/home/bronger/src/jb_institute")
sys.stdout = sys.stderr

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ['MPLCONFIGDIR'] = '/home/bronger/.config/matplotlib'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
