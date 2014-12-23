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


import os
import sys

sys.path.append("/home/username/myproject")
sys.path.append("/home/username/myproject/juliabase")

os.environ["DJANGO_SETTINGS_MODULE"] = "mysite.settings"

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
