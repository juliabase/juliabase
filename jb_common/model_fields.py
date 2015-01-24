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
from django.utils.translation import ugettext_lazy as _, ugettext


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


class IntegerQuantityField(models.IntegerField):
    description = _("Integer in the unit of %(unit)s")

    def __init__(self, *args, **kwargs):
        self.unit = kwargs.pop("unit", None)
        super(IntegerQuantityField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        result = super(IntegerQuantityField, self).formfield(**kwargs)
        result.unit = self.unit
        return result


class PositiveIntegerQuantityField(models.PositiveIntegerField):
    description = _("Positive integer in the unit of %(unit)s")

    def __init__(self, *args, **kwargs):
        self.unit = kwargs.pop("unit", None)
        super(PositiveIntegerQuantityField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        result = super(PositiveIntegerQuantityField, self).formfield(**kwargs)
        result.unit = self.unit
        return result


class SmallIntegerQuantityField(models.SmallIntegerField):
    description = _("Small integer in the unit of %(unit)s")

    def __init__(self, *args, **kwargs):
        self.unit = kwargs.pop("unit", None)
        super(SmallIntegerQuantityField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        result = super(SmallIntegerQuantityField, self).formfield(**kwargs)
        result.unit = self.unit
        return result


class PositiveSmallIntegerQuantityField(models.PositiveSmallIntegerField):
    description = _("Positive small integer in the unit of %(unit)s")

    def __init__(self, *args, **kwargs):
        self.unit = kwargs.pop("unit", None)
        super(PositiveSmallIntegerQuantityField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        result = super(PositiveSmallIntegerQuantityField, self).formfield(**kwargs)
        result.unit = self.unit
        return result


_ = ugettext
