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


"""All the views for the PDS measurements.  This is significantly simpler than
the views for deposition systems (mostly because the rearrangement of layers
doesn't happen here).
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six

import datetime, os.path
from django.conf import settings
import django.contrib.auth.models
from django import forms
from django.utils.translation import ugettext_lazy as _, ugettext
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
    result = {"number": six.text_type(number)}
    sample = None
    try:
        result["raw_datafile"] = "measurement-{}.dat".format(number)
        for i, line in enumerate(open(os.path.join(settings.PDS_ROOT_DIR, result["raw_datafile"]))):
            if i > 5:
                break
            key, __, value = line[1:].partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "timestamp":
                result["timestamp"] = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
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
    """Model form for the core PDS measurement data.
    """
    class Meta:
        model = institute_models.PDSMeasurement
        fields = "__all__"
        error_messages = {
            "number": {
                "unique": _("This PDS number exists already.")
                }
            }

    def __init__(self, user, *args, **kwargs):
        super(PDSMeasurementForm, self).__init__(user, *args, **kwargs)
        self.fields["raw_datafile"].widget.attrs["size"] = "50"
        self.fields["number"].widget.attrs["size"] = "10"

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
    model = institute_models.PDSMeasurement
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
        super(EditView, self).build_forms()


_ = ugettext
