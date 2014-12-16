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

from __future__ import absolute_import, unicode_literals

from django.db import models
from django.utils.translation import ugettext_lazy as _


class DecimalQuantityField(models.DecimalField):
    description = _("Fixed-point number in the unit of %(unit)s")

    def __init__(self, *args, **kwargs):
        self.unit = kwargs.pop("unit", None)
        super(DecimalQuantityField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        result = super(DecimalQuantityField, self).formfield(**kwargs)
        result.unit = self.unit
        return result


class FloatQuantityField(models.FloatField):
    description = _("Floating-Point number in the unit of %(unit)s")

    def __init__(self, *args, **kwargs):
        self.unit = kwargs.pop("unit", None)
        super(FloatQuantityField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        result = super(FloatQuantityField, self).formfield(**kwargs)
        result.unit = self.unit
        return result
