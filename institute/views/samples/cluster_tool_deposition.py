# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


"""All views and helper routines directly connected with the cluster
tool deposition system.  This includes adding, editing, and viewing such
processes.
"""

from django import forms
from django.utils.translation import ugettext_lazy as _, ugettext
from django.forms.utils import ValidationError
import jb_common.utils.base
import samples.utils.views as utils
import institute.utils.views as form_utils
import institute.utils.base
import institute.models as institute_models


class DepositionForm(utils.DepositionForm):

    class Meta:
        model = institute_models.ClusterToolDeposition
        fields = "__all__"

    def clean_number(self):
        number = super().clean_number()
        return form_utils.clean_deposition_number_field(number, "C")

    def clean(self):
        cleaned_data = super().clean()
        if "number" in cleaned_data and "timestamp" in cleaned_data:
            if cleaned_data["number"][:2] != cleaned_data["timestamp"].strftime("%y"):
                self.add_error("number", ValidationError(_("The first two digits must match the year of the deposition."),
                                                         code="invalid"))
        return cleaned_data


class ClusterToolLayerForm(utils.SubprocessMultipleTypesForm):
    """Abstract model form for both layer types in the cluster tool.
    """

    class Meta:
        exclude = ("deposition",)

    def clean_time(self):
        return utils.clean_time_field(self.cleaned_data["time"])

    def clean_comments(self):
        """Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        jb_common.utils.base.check_markdown(comments)
        return comments


class HotWireLayerForm(ClusterToolLayerForm):

    class Meta(ClusterToolLayerForm.Meta):
        model = institute_models.ClusterToolHotWireLayer
        widgets = {
            "number": forms.TextInput(attrs={"readonly": "readonly", "size": 2,
                                            "style": "text-align: center; font-size: xx-large"}),
            "comments": forms.Textarea(attrs={"cols": 40, "rows": 8}),
            "time": forms.TextInput(attrs={"size": 10}),
            "base_pressure": forms.TextInput(attrs={"size": 10}),
            "h2": forms.TextInput(attrs={"size": 15}),
            "sih4": forms.TextInput(attrs={"size": 15}),
            }

    def __init__(self, view, data=None, **kwargs):
        super().__init__(view, data, **kwargs)
        if not view.request.user.is_superuser:
            self.fields["wire_material"].choices = \
                [choice for choice in self.fields["wire_material"].choices if choice[0] != "unknown"]


class PECVDLayerForm(ClusterToolLayerForm):

    class Meta(ClusterToolLayerForm.Meta):
        model = institute_models.ClusterToolPECVDLayer
        widgets = {"number": forms.TextInput(attrs={"readonly": "readonly" , "size": 2,
                                                    "style": "text-align: center; font-size: xx-large"}),
                   "comments": forms.Textarea(attrs={"cols": 40, "rows": 8}),
                   "time": forms.TextInput(attrs={"size": 10}),
                   "deposition_power": forms.TextInput(attrs={"size": 10}),
                   "h2": forms.TextInput(attrs={"size": 15}),
                   "sih4": forms.TextInput(attrs={"size": 15})}


class EditView(utils.RemoveFromMySamplesMixin, utils.DepositionMultipleTypeView):
    form_class = DepositionForm
    step_form_classes = (HotWireLayerForm, PECVDLayerForm)
    short_labels = {HotWireLayerForm: _("hot-wire"), PECVDLayerForm: _("PECVD")}

    def get_next_id(self):
        return institute.utils.base.get_next_deposition_number("C")


_ = ugettext
