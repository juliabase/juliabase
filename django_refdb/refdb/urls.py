#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.conf.urls.defaults import *

urlpatterns = patterns("refdb.views",
                       (r"^$", "main.main_menu"),
                       (r"^view/(?P<citation_key>.*)", "reference.view"),
                       )
