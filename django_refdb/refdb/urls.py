#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “refdb”.

It takes the URL that the user chose, and converts it to a function call –
possibly with parameters.

Note that although this is only an “application”, it contains views for
authentication (login/logout), too.  You may override them in the global URL
configuration file, though.


:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/

"""

from django.conf.urls.defaults import *

urlpatterns = patterns("refdb.views",
                       (r"^$", "main.main_menu"),
                       (r"^change_list/$", "main.change_list"),
                       (r"^view/add/$", "reference.edit", {"citation_key": None}),
                       (r"^view/search$", "reference.search"),
                       (r"^view/bulk$", "reference.bulk"),
                       (r"^view/(?P<citation_key>.+)/edit/$", "reference.edit"),
                       (r"^view/(?P<citation_key>.+)/add_to_list/$", "reference.add_to_list"),
                       (r"^view/(?P<citation_key>.+)", "reference.view"),
                       )
