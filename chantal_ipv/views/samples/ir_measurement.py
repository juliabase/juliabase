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


"""
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
from chantal_common.utils import append_error, check_filepath
from samples.views import utils, feed_utils
from chantal_ipv.views import form_utils
from samples import models, permissions
import chantal_ipv.models as ipv_models


class IRMeasurementForm(form_utils.ProcessForm):
    """Model form for the core IR measurement data.  I only redefine the
    ``operator`` field here in oder to have the full names of the users.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, *args, **kwargs):
        """Form constructor.  I just adjust layout here.
        """
        super(IRMeasurementForm, self).__init__(*args, **kwargs)
        self.fields["spa_datafile"].widget.attrs["size"] = self.fields["csv_datafile"].widget.attrs["size"] = "50"
        self.fields["number"].widget.attrs.update({"size": "10", "readonly": "readonly"})
        measurement = kwargs.get("instance")
        self.fields["operator"].set_operator(measurement.operator if measurement else user, user.is_staff)
        self.fields["operator"].initial = measurement.operator.pk if measurement else user.pk
        self.user = user

    def clean_spa_datafile(self):
        """Check whether the spa datafile name points to a readable file.
        """
        filename = self.cleaned_data["spa_datafile"]
        return check_filepath(filename, settings.IR_ROOT_DIR)

    def clean_csv_datafile(self):
        """Check whether the csv datafile name points to a readable
        file.
        """
        filename = self.cleaned_data["evaluated_datafile"]
        return check_filepath(filename, settings.IR_ROOT_DIR)

    def validate_unique(self):
        """Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `edit`.  I cannot use Django's built-in test anyway
        because it leads to an error message in wrong German (difficult to fix,
        even for the Django guys).
        """
        pass

    class Meta:
        model = ipv_models.IRMeasurement
        exclude = ("external_operator",)

def is_all_valid(ir_measurement_form, sample_form, remove_from_my_samples_form, edit_description_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `ir_measurement_form`: a bound IR measurement form
      - `sample_form`: a bound sample selection form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form
      - `edit_description_form`: a bound edit-description form

    :type ir_measurement_form: `IRMeasurementForm`
    :type sample_form: `SampleForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm`

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = ir_measurement_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid

def is_referentially_valid(ir_measurement_form, sample_form, ir_number):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `ir_measurement_form`: a bound IR measurement form
      - `sample_form`: a bound sample selection form
      - `ir_number`: The IR number of the IR measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.

    :type ir_measurement_form: `IRMeasurementForm`
    :type sample_form: `SampleForm`
    :type ir_number: unicode

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    return form_utils.measurement_is_referentially_valid(ir_measurement_form,
                                                         sample_form,
                                                         ir_number,
                                                         ipv_models.IRMeasurement)

@login_required
def edit(request, ir_number):
    """Edit and create view for IR measurements.

    :Parameters:
      - `request`: the current HTTP Request object
      - `ir_number`: The IR number of the IR measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.

    :type request: ``HttpRequest``
    :type ir_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    ir_measurement = get_object_or_404(ipv_models.IRMeasurement, number=utils.convert_id_to_int(ir_number)) \
        if ir_number is not None else None
    permissions.assert_can_add_edit_physical_process(request.user, ir_measurement, ipv_models.IRMeasurement)
    preset_sample = utils.extract_preset_sample(request) if not ir_measurement else None
    if request.method == "POST":
        ir_measurement_form = None
        sample_form = form_utils.SampleForm(request.user, ir_measurement, preset_sample, request.POST)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not ir_measurement else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if ir_measurement else None
        ir_measurement_form = IRMeasurementForm(request.user, request.POST, instance=ir_measurement)
        all_valid = is_all_valid(ir_measurement_form, sample_form, remove_from_my_samples_form, edit_description_form)
        referentially_valid = is_referentially_valid(ir_measurement_form, sample_form, ir_number)
        if all_valid and referentially_valid:
            ir_measurement = ir_measurement_form.save()
            samples = [sample_form.cleaned_data["sample"]]
            ir_measurement.samples = samples
            feed_utils.Reporter(request.user).report_physical_process(
                ir_measurement, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            success_report = _("{process} was successfully changed in the database.").format(process=ir_measurement) \
                if ir_number else _("{process} was successfully added to the database.").format(process=ir_measurement)
            return utils.successful_response(request, success_report, json_response=ir_measurement.pk)
    else:
        initial = {}
        if ir_number is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
            numbers = ipv_models.IRMeasurement.objects.values_list("number", flat=True)
            initial["number"] = max(numbers) + 1 if numbers else 1
        ir_measurement_form = IRMeasurementForm(request.user, instance=ir_measurement, initial=initial)
        initial = {}
        if ir_measurement:
            samples = ir_measurement.samples.all()
            if samples:
                initial["sample"] = samples[0].pk
        sample_form = form_utils.SampleForm(request.user, ir_measurement, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not ir_measurement else None
        edit_description_form = form_utils.EditDescriptionForm() if ir_measurement else None
    title = _("IR measurement of {sample}").format(sample=samples[0]) if ir_measurement else _("Add IR measurement")
    return render_to_response("samples/edit_ir_measurement.html", {"title": title,
                                                                   "ir_measurement": ir_measurement_form,
                                                                   "sample": sample_form,
                                                                   "remove_from_my_samples": remove_from_my_samples_form,
                                                                   "edit_description": edit_description_form},
                              context_instance=RequestContext(request))
