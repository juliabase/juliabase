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


"""All the views for the PDS measurements.  This is significantly simpler than
the views for deposition systems (mostly because the rearrangement of layers
doesn't happen here).
"""

import datetime, os.path
from django.conf import settings
import django.contrib.auth.models
from django import forms
from django.utils.translation import ugettext_lazy as _, ugettext
import django.utils.timezone
from jb_common.utils.base import check_filepath
import samples.utils.views as utils
from samples import models
import institute.models as institute_models

def get_data_from_file(number):
    """Find the datafiles for a given PDS number, and return all data found in
    them.  The resulting dictionary may contain the following keys:
    ``"raw_datafile"``, ``"timestamp"``, ``"apparatus"``, ``"number"``,
    ``"sample"``, ``"operator"``, and ``"comments"``.  This is ready to be used
    as the ``initial`` keyword parameter of a `PDSMeasurementForm`.  Moreover,
    it looks for the sample that was measured in the database, and if it finds
    it, returns it, too.

    :param number: the PDS number of the PDS measurement

    :type number: int

    :return:
      a dictionary with all data found in the datafile including the filenames
      for this measurement, and the sample connected with deposition if any.
      If no sample in the database fits, ``None`` is returned as the sample.

    :rtype: dict mapping str to ``object``, `samples.models.Sample`
    """
    result = {"number": str(number)}
    sample = None
    result["raw_datafile"] = "measurement-{}.dat".format(number)
    try:
        for i, line in enumerate(open(os.path.join(settings.PDS_ROOT_DIR, result["raw_datafile"]))):
            if i > 5:
                break
            key, __, value = line[1:].partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "timestamp":
                result["timestamp"] = django.utils.timezone.make_aware(datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S"))
            elif key == "apparatus":
                result["apparatus"] = "pds" + value
            elif key == "comments":
                result["comments"] = value
            elif key == "operator":
                try:
                    operator = django.contrib.auth.models.User.objects.get(username=value)
                except django.contrib.auth.models.User.DoesNotExist:
                    pass
                else:
                    result["operator"] = result["combined_operator"] = operator.pk
            elif key == "sample":
                try:
                    sample = models.Sample.objects.get(name=value)
                    result["sample"] = sample.pk
                except models.Sample.DoesNotExist:
                    pass
    except IOError:
        del result["raw_datafile"]
    return result, sample


class PDSMeasurementForm(utils.ProcessForm):

    class Meta:
        model = institute_models.PDSMeasurement
        fields = "__all__"
        error_messages = {
            "number": {
                "unique": _("This PDS number exists already.")
                }
            }
        widgets = {"number": forms.TextInput(attrs={"size": 10}),
                   "raw_datafile": forms.TextInput(attrs={"size": 50})}

    def clean_raw_datafile(self):
        """Check whether the raw datafile name points to a readable file.
        """
        filename = self.cleaned_data["raw_datafile"]
        return check_filepath(filename, settings.PDS_ROOT_DIR)


class OverwriteForm(forms.Form):
    """Form for the checkbox whether the form data should be taken from the
    datafile.
    """
    overwrite_from_file = forms.BooleanField(label=_("Overwrite with file data"), required=False)


class EditView(utils.RemoveFromMySamplesMixin, utils.ProcessView):
    form_class = PDSMeasurementForm

    def build_forms(self):
        self.forms["overwrite"] = OverwriteForm(self.data)
        if self.forms["overwrite"].is_valid() and self.forms["overwrite"].cleaned_data["overwrite_from_file"]:
            try:
                number = int(self.request.POST["number"])
            except (ValueError, KeyError):
                pass
            else:
                initial, sample = get_data_from_file(number)
                if sample:
                    self.request.user.my_samples.add(sample)
                self.forms["process"] = self.form_class(self.request.user, instance=self.process, initial=initial)
                self.forms["sample"] = utils.SampleSelectForm(self.request.user, self.process, self.preset_sample,
                                                              initial=initial)
                self.forms["overwrite"] = OverwriteForm()
        super().build_forms()


_ = ugettext
