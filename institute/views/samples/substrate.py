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


"""Views to add and edit substrates.
"""

from django.db.models import Max
from django.forms.utils import ValidationError
from django.utils.translation import ugettext_lazy as _, ugettext, ugettext
from institute import models as institute_models
import samples.utils.views as utils


class SubstrateForm(utils.ProcessForm):

    class Meta:
        model = institute_models.Substrate
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("material") == "custom" and not cleaned_data.get("comments"):
            self.add_error("comments", ValidationError(_("For a custom substrate, you must give substrate comments."),
                                                       code="required"))
        return cleaned_data


class EditView(utils.ProcessMultipleSamplesView):
    form_class = SubstrateForm

    def is_referentially_valid(self):
        """Test whether a sample has more than one substrate or whether the substrate
        is not the very first process.

        :return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = super().is_referentially_valid()
        if self.forms["samples"].is_valid() and self.forms["process"].is_valid():
            for sample in self.forms["samples"].cleaned_data["sample_list"]:
                processes = sample.processes
                if processes.exists():
                    earliest_timestamp = processes.aggregate(Max("timestamp"))["timestamp__max"]
                    if earliest_timestamp < self.forms["process"].cleaned_data["timestamp"]:
                        self.forms["samples"].add_error(
                            "sample_list", _("Sample {0} has already processes before the timestamp of this substrate, "
                                             "namely from {1}.").format(sample, earliest_timestamp))
                        referentially_valid = False
                    for process in processes.all():
                        if process.content_type.model_class() == institute_models.Substrate:
                            self.forms["samples"].add_error(
                                "sample_list", _("Sample {0} has already a substrate.").format(sample))
                            referentially_valid = False
                            break
        return referentially_valid


_ = ugettext
