#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

from django.contrib import admin
from chantal_common.models import UserDetails, Project

admin.site.register(UserDetails)
admin.site.register(Project)
