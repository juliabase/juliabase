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
import institute.utils.views as form_utils
import institute.utils.base
import institute.models as institute_models


class DepositionForm(utils.DepositionForm):
    """Model form for the basic deposition data.
    """
    class Meta:
        model = institute_models.FiveChamberDeposition
        fields = "__all__"

    def __init__(self, user, data=None, **kwargs):
        super(DepositionForm, self).__init__(user, data, **kwargs)

    def clean_number(self):
        number = super(DepositionForm, self).clean_number()
        return form_utils.clean_deposition_number_field(number, "S")

    def clean(self):
        cleaned_data = super(DepositionForm, self).clean()
        if "number" in cleaned_data and "timestamp" in cleaned_data:
            if cleaned_data["number"][:2] != cleaned_data["timestamp"].strftime("%y"):
                self.add_error("number", _("The first two digits must match the year of the deposition."))
        return cleaned_data


class LayerForm(forms.ModelForm):
    """Model form for a single layer.
    """
    class Meta:
        model = institute_models.FiveChamberLayer
        exclude = ("deposition",)

    def __init__(self, view, *args, **kwargs):
        """I only tweak the HTML layout slightly.
        """
        super(LayerForm, self).__init__(*args, **kwargs)
        self.fields["number"].widget.attrs.update({"readonly": "readonly", "size": "5", "style": "font-size: large"})
        for fieldname in ["sih4", "h2", ]:
            self.fields[fieldname].widget.attrs["size"] = "10"
        self.fields["temperature_1"].widget.attrs["size"] = "5"
        self.fields["temperature_2"].widget.attrs["size"] = "5"


class EditView(utils.RemoveFromMySamplesMixin, utils.DepositionView):
    model = institute_models.FiveChamberDeposition
    form_class = DepositionForm
    layer_form_class = LayerForm

    def get_next_id(self):
        return institute.utils.base.get_next_deposition_number("S")


_ = ugettext
