#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.utils.translation import ugettext as _

class PermissionError(Exception):
    def __init__(self, description):
        super(PermissionError, self).__init__(_(u"Permission missing: ") + description)
        self.description = description
