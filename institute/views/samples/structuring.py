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

from django.utils.translation import ugettext_lazy as _, ugettext
import samples.utils.views as utils
import institute.models as institute_models


class StructuringForm(utils.ProcessForm):

    class Meta:
        model = institute_models.Structuring
        fields = "__all__"


class EditView(utils.RemoveFromMySamplesMixin, utils.ProcessView):
    model = institute_models.Structuring
    form_class = StructuringForm


_ = ugettext
