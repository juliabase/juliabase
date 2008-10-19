#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.utils.translation import ugettext as _

class PermissionDeniedError(Exception):
    def __init__(self, description):
        super(PermissionDeniedError, self).__init__(_(u"Permission missing: ") + description)
        self.description = description
