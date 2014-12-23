#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
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
