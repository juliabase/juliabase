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

import datetime, os.path, re, codecs
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
from jb_common.utils import is_json_requested, respond_in_json, check_filepath
from samples.views import utils, feed_utils
from inm.views import form_utils, shared_utils
from samples import models, permissions
import inm.models as institute_models


def get_data_from_file(number):
    """Find the datafiles for a given PDS number, and return all data found in
    them.  The resulting dictionary may contain the following keys:
    ``"raw_datafile"``, ``"timestamp"``, ``"apparatus"``, ``"number"``,
    ``"sample"``, ``"operator"``, and ``"comments"``.  This is ready to be used
    as the ``initial`` keyword parameter of a `PDSMeasurementForm`.  Moreover,
    it looks for the sample that was measured in the database, and if it finds
    it, returns it, too.

    :Parameters:
      - `number`: the PDS number of the PDS measurement

    :type number: int

    :Return:
      a dictionary with all data found in the datafile including the filenames
      for this measurement, and the sample connected with deposition if any.
      If no sample in the database fits, ``None`` is returned as the sample.

    :rtype: dict mapping str to ``object``, `models.Sample`
    """
    result = {"number": six.text_type(number)}
    sample = None
    try:
        result["raw_datafile"] = os.path.join(settings.PDS_ROOT_DIR, "measurement-{}.dat".format(number))
        for i, line in open(result["raw_datafile"]):
            if i > 4:
                break
            key, value = line[1:].split(":")
            key, value = key.strip().lower(), value.strip()
            if key == "timestamp":
                result[key] = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            elif key == "apparatus":
                result[key] = "pds" + apparatus
            elif key in ["operator", "comments"]:
                result[key] = value
            elif key == "sample":
                try:
                    sample = models.Sample.objects.get(name=value)
                    key["sample"] = sample.pk
                except models.Sample.DoesNotExist:
                    pass
    except IOError:
        del result["raw_datafile"]
    return result, sample


class PDSMeasurementForm(form_utils.ProcessForm):
    """Model form for the core PDS measurement data.  I only redefine the
    ``operator`` field here in order to have the full names of the users.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, *args, **kwargs):
        super(PDSMeasurementForm, self).__init__(*args, **kwargs)
        self.fields["raw_datafile"].widget.attrs["size"] = "50"
        self.fields["number"].widget.attrs["size"] = "10"
        measurement = kwargs.get("instance")
        self.fields["operator"].set_operator(measurement.operator if measurement else user, user.is_staff)
        self.fields["operator"].initial = measurement.operator.pk if measurement else user.pk

    def clean_raw_datafile(self):
        """Check whether the raw datafile name points to a readable file.
        """
        filename = self.cleaned_data["raw_datafile"]
        return check_filepath(filename, settings.PDS_ROOT_DIR)

    def validate_unique(self):
        """Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `edit`.  I cannot use Django's built-in test anyway
        because it leads to an error message in wrong German (difficult to fix,
        even for the Django guys).
        """
        pass

    class Meta:
        model = institute_models.PDSMeasurement
        exclude = ("external_operator",)


class OverwriteForm(forms.Form):
    """Form for the checkbox whether the form data should be taken from the
    datafile.
    """
    _ = ugettext_lazy
    overwrite_from_file = forms.BooleanField(label=_("Overwrite with file data"), required=False)


def is_all_valid(pds_measurement_form, sample_form, overwrite_form, remove_from_my_samples_form, edit_description_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `pds_measurement_form`: a bound PDS measurement form
      - `sample_form`: a bound sample selection form
      - `overwrite_form`: a bound overwrite data form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form
      - `edit_description_form`: a bound edit-description form

    :type pds_measurement_form: `PDSMeasurementForm`
    :type sample_form: `SampleForm`
    :type overwrite_form: `OverwriteForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm`

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = pds_measurement_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    all_valid = overwrite_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid


def is_referentially_valid(pds_measurement_form, sample_form, number):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `pds_measurement_form`: a bound PDS measurement form
      - `sample_form`: a bound sample selection form
      - `number`: The PDS number of the PDS measurement to be edited.  If it is
        ``None``, a new measurement is added to the database.

    :type pds_measurement_form: `PDSMeasurementForm`
    :type sample_form: `SampleForm`
    :type number: unicode

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    return form_utils.measurement_is_referentially_valid(pds_measurement_form, sample_form, number, institute_models.PDSMeasurement)

@login_required
def edit(request, number):
    """Edit and create view for PDS measurements.

    :Parameters:
      - `request`: the current HTTP Request object
      - `number`: The PDS number of the PDS measurement to be edited.  If it is
        ``None``, a new measurement is added to the database.

    :type request: ``HttpRequest``
    :type number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    pds_measurement = get_object_or_404(institute_models.PDSMeasurement, number=utils.convert_id_to_int(number)) \
        if number is not None else None
    old_sample = pds_measurement.samples.get() if pds_measurement else None
    permissions.assert_can_add_edit_physical_process(request.user, pds_measurement, institute_models.PDSMeasurement)
    preset_sample = utils.extract_preset_sample(request) if not pds_measurement else None
    if request.method == "POST":
        pds_measurement_form = None
        sample_form = form_utils.SampleForm(request.user, pds_measurement, preset_sample, request.POST)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not pds_measurement else None
        overwrite_form = OverwriteForm(request.POST)
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if pds_measurement else None
        if overwrite_form.is_valid() and overwrite_form.cleaned_data["overwrite_from_file"]:
            try:
                number = int(request.POST["number"])
            except (ValueError, KeyError):
                pass
            else:
                initial, sample = get_data_from_file(number)
                if sample:
                    request.user.my_samples.add(sample)
                pds_measurement_form = PDSMeasurementForm(request.user, instance=pds_measurement, initial=initial)
                overwrite_form = OverwriteForm()
        if pds_measurement_form is None:
            pds_measurement_form = PDSMeasurementForm(request.user, request.POST, instance=pds_measurement)
        all_valid = is_all_valid(pds_measurement_form, sample_form, overwrite_form, remove_from_my_samples_form,
                                 edit_description_form)
        referentially_valid = is_referentially_valid(pds_measurement_form, sample_form, number)
        if all_valid and referentially_valid:
            pds_measurement = pds_measurement_form.save()
            samples = [sample_form.cleaned_data["sample"]]
            pds_measurement.samples = samples
            reporter = request.user if not request.user.is_staff else pds_measurement_form.cleaned_data["operator"]
            feed_utils.Reporter(reporter).report_physical_process(
                pds_measurement, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            success_report = _("{process} was successfully changed in the database.").format(process=pds_measurement) \
                if number else _("{process} was successfully added to the database.").format(process=pds_measurement)
            return utils.successful_response(request, success_report, json_response=pds_measurement.pk)
    else:
        initial = {}
        if number is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
            numbers = institute_models.PDSMeasurement.objects.values_list("number", flat=True)
            initial["number"] = max(numbers) + 1 if numbers else 1
        pds_measurement_form = PDSMeasurementForm(request.user, instance=pds_measurement, initial=initial)
        initial = {}
        if old_sample:
            initial["sample"] = old_sample.pk
        sample_form = form_utils.SampleForm(request.user, pds_measurement, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not pds_measurement else None
        overwrite_form = OverwriteForm()
        edit_description_form = form_utils.EditDescriptionForm() if pds_measurement else None
    title = _("Edit PDS measurement of {sample}").format(sample=old_sample) if pds_measurement else _("Add PDS measurement")
    return render(request, "samples/edit_pds_measurement.html",
                  {"title": title, "pds_measurement": pds_measurement_form, "overwrite": overwrite_form,
                   "sample": sample_form, "remove_from_my_samples": remove_from_my_samples_form,
                   "edit_description": edit_description_form})
