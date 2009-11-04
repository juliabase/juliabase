#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “chantal_common”, which provides core functionality and
core views for all Chantal apps.


:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/

"""

from __future__ import absolute_import

from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns("chantal_common.views",
                       (r"^markdown$", "markdown_sandbox"),
                       (r"^switch_language$", "switch_language"),
                       )
