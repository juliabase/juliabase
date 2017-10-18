#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
