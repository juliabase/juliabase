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

from django import forms
from django.utils.translation import ugettext_lazy as _, ugettext
import samples.utils.views as utils
from institute.models import SolarsimulatorMeasurement, SolarsimulatorCellMeasurement


class SolarsimulatorMeasurementForm(utils.ProcessForm):

    class Meta:
        model = SolarsimulatorMeasurement
        fields = "__all__"

    def __init__(self, user, *args, **kwargs):
        super(SolarsimulatorMeasurementForm, self).__init__(user, *args, **kwargs)
        self.fields["temperature"].widget.attrs.update({"size": "5"})


class SolarsimulatorCellForm(forms.ModelForm):

    class Meta:
        model = SolarsimulatorCellMeasurement
        exclude = ("measurement",)

    def __init__(self, *args, **kwargs):
        super(SolarsimulatorCellForm, self).__init__(*args, **kwargs)


class SolarsimulatorMeasurementView(utils.SubprocessesMixin, utils.ProcessView):
    model = SolarsimulatorMeasurement
    sub_model = SolarsimulatorCellMeasurement
    form_class = SolarsimulatorMeasurementForm
    subform_class = SolarsimulatorCellForm
    process_field, subprocess_field = "measurement", "cells"

    def is_referentially_valid(self):
        referentially_valid = super(SolarsimulatorMeasurementView, self).is_referentially_valid()
        if not self.forms["subprocesses"]:
            self.forms["process"].add_error(None, _("No measurenents given."))
            referentially_valid = False
        return referentially_valid


_ = ugettext
