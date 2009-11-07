#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.
#
#     Django-RefDB is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public
#     License as published by the Free Software Foundation, either
#     version 3 of the License, or (at your option) any later
#     version.
#
#     Django-RefDB is distributed in the hope that it will be
#     useful, but WITHOUT ANY WARRANTY; without even the implied
#     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#     PURPOSE.  See the GNU Affero General Public License for more
#     details.
#
#     You should have received a copy of the GNU Affero General
#     Public License along with Django-RefDB.  If not, see
#     <http://www.gnu.org/licenses/>.


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

db_prefix = "^(?P<database>[-a-zA-Z0-9_]+)/"

urlpatterns = patterns("refdb.views",
                       (db_prefix + r"change_list/$", "main.change_list"),
                       (db_prefix + r"export/$", "export.export"),
                       (db_prefix + r"add/$", "reference.edit", {"citation_key": None}),
                       (db_prefix + r"search/$", "bulk.search"),
                       (db_prefix + r"bulk/$", "bulk.bulk"),
                       (db_prefix + r"(?P<citation_key>.+)/edit/$", "reference.edit"),
                       (db_prefix + r"(?P<citation_key>.+)/(?P<username>.+)/pdf", "reference.pdf"),
                       (db_prefix + r"(?P<citation_key>.+)/pdf", "reference.pdf", {"username": None}),
                       (db_prefix + r"(?P<citation_key>.+)", "reference.view"),
                       (db_prefix + r"$", "main.main_menu"),
                       (r"^$", "main.main_menu", {"database": None}),
                       )
