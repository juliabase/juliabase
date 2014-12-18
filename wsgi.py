# -*- mode: python -*-

import os
import sys

sys.path.append("/home/username/myproject")
sys.path.append("/home/username/myproject/juliabase")
sys.stdout = sys.stderr

os.environ["DJANGO_SETTINGS_MODULE"] = "mysite.settings"

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
