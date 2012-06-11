#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""All the views for the Dektak measurements.
"""

from __future__ import absolute_import, unicode_literals

import datetime, os.path, re, codecs
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
import django.contrib.auth.models
from chantal_common.utils import append_error
from samples.views import utils, feed_utils
from chantal_institute.views import form_utils
from samples import models, permissions
import chantal_institute.models as institute_models



date_pattern = re.compile(r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})")

class DektakMeasurementForm(form_utils.ProcessForm):
    """Model form for the core Dektak measurement data.  I only redefine the
    ``operator`` field here in oder to have the full names of the users.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, *args, **kwargs):
        """Form constructor.  I just adjust layout here.
        """
        super(DektakMeasurementForm, self).__init__(*args, **kwargs)
        self.fields["number"].widget.attrs.update({"size": "10", "readonly": "readonly"})
        measurement = kwargs.get("instance")
        self.fields["thickness"].widget.attrs.update({"size": "10", "min": "0"})
        self.fields["operator"].set_operator(measurement.operator if measurement else user, user.is_staff)
        self.fields["operator"].initial = measurement.operator.pk if measurement else user.pk

    def validate_unique(self):
        """Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `edit`.  I cannot use Django's built-in test anyway
        because it leads to an error message in wrong German (difficult to fix,
        even for the Django guys).
        """
        pass

    class Meta:
        model = institute_models.DektakMeasurement
        exclude = ("external_operator",)


def is_all_valid(dektak_measurement_form, sample_form, remove_from_my_samples_form, edit_description_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `dektak_measurement_form`: a bound Dektak measurement form
      - `sample_form`: a bound sample selection form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form
      - `edit_description_form`: a bound edit-description form

    :type dektak_measurement_form: `DektakMeasurementForm`
    :type sample_form: `SampleForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm`

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = dektak_measurement_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid


def is_referentially_valid(dektak_measurement_form, sample_form, dektak_number):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `dektak_measurement_form`: a bound Dektak measurement form
      - `sample_form`: a bound sample selection form
      - `dektak_number`: The Dektak number of the Dektak measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.

    :type dektak_measurement_form: `DektakMeasurementForm`
    :type sample_form: `SampleForm`
    :type dektak_number: unicode

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    return form_utils.measurement_is_referentially_valid(dektak_measurement_form,
                                                         sample_form,
                                                         dektak_number,
                                                         institute_models.DektakMeasurement)

@login_required
def edit(request, dektak_number):
    """Edit and create view for Dektak measurements.

    :Parameters:
      - `request`: the current HTTP Request object
      - `dektak_number`: The Dektak number of the Dektak measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.

    :type request: ``HttpRequest``
    :type dektak_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    dektak_measurement = get_object_or_404(institute_models.DektakMeasurement, number=utils.convert_id_to_int(dektak_number)) \
        if dektak_number is not None else None
    permissions.assert_can_add_edit_physical_process(request.user, dektak_measurement, institute_models.DektakMeasurement)
    preset_sample = utils.extract_preset_sample(request) if not dektak_measurement else None
    if request.method == "POST":
        sample_form = form_utils.SampleForm(request.user, dektak_measurement, preset_sample, request.POST)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not dektak_measurement else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if dektak_measurement else None
        dektak_measurement_form = DektakMeasurementForm(request.user, request.POST, instance=dektak_measurement)
        all_valid = is_all_valid(dektak_measurement_form, sample_form, remove_from_my_samples_form, edit_description_form)
        referentially_valid = is_referentially_valid(dektak_measurement_form, sample_form, dektak_number)
        if all_valid and referentially_valid:
            dektak_measurement = dektak_measurement_form.save()
            samples = [sample_form.cleaned_data["sample"]]
            dektak_measurement.samples = samples
            feed_utils.Reporter(request.user).report_physical_process(
                dektak_measurement, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            success_report = _("{process} was successfully changed in the database.").format(process=dektak_measurement) \
                if dektak_number else _("{process} was successfully added to the database."). \
                format(process=dektak_measurement)
            return utils.successful_response(request, success_report, json_response=dektak_measurement.pk)
    else:
        initial = {}
        if dektak_number is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
            numbers = institute_models.DektakMeasurement.objects.values_list("number", flat=True)
            initial["number"] = max(numbers) + 1 if numbers else 1
        dektak_measurement_form = DektakMeasurementForm(request.user, instance=dektak_measurement, initial=initial)
        initial = {}
        if dektak_measurement:
            samples = dektak_measurement.samples.all()
            if samples:
                initial["sample"] = samples[0].pk
        sample_form = form_utils.SampleForm(request.user, dektak_measurement, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not dektak_measurement else None
        edit_description_form = form_utils.EditDescriptionForm() if dektak_measurement else None
    title = _("Dektak measurement of {sample}").format(sample=samples[0]) if dektak_measurement \
        else _("Add Dektak measurement")
    return render_to_response("samples/edit_dektak_measurement.html",
                              {"title": title,
                               "dektak_measurement": dektak_measurement_form,
                               "sample": sample_form,
                               "remove_from_my_samples": remove_from_my_samples_form,
                               "edit_description": edit_description_form},
                              context_instance=RequestContext(request))
