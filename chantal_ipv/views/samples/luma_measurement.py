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


"""All the views for the Luma measurements.
"""

from __future__ import absolute_import, division, unicode_literals

import datetime
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal_common.utils import check_filepath
from samples.views import utils, feed_utils
from chantal_ipv.views import form_utils
from samples import permissions
import chantal_ipv.models as ipv_models


class LumaMeasurementForm(form_utils.ProcessForm):
    """Model form for the core Luma measurement data.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, *args, **kwargs):
        """Form constructor.
        """
        super(LumaMeasurementForm, self).__init__(*args, **kwargs)
        measurement = kwargs.get("instance")
        self.fields["operator"].set_operator(measurement.operator if measurement else user, user.is_staff)
        self.fields["operator"].initial = measurement.operator.pk if measurement else user.pk

    def clean_filepath(self):
        """Check whether the datafile name points to a readable file.
        """
        filename = self.cleaned_data["filepath"]
        return check_filepath(filename, settings.LUMA_ROOT_DIR)

    class Meta:
        model = ipv_models.LumaMeasurement
        exclude = ("external_operator",)


def is_all_valid(luma_measurement_form, sample_form, remove_from_my_samples_form, edit_description_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `luma_measurement_form`: a bound Luma measurement form
      - `sample_form`: a bound sample selection form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form
      - `edit_description_form`: a bound edit-description form

    :type luma_measurement_form: `LumaMeasurementForm`
    :type sample_form: `SampleForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm`

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = luma_measurement_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid


def is_referentially_valid(luma_measurement_form, sample_form, process_id):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `luma_measurement_form`: a bound Luma measurement form
      - `sample_form`: a bound sample selection form
      - `process_id`: The ID of the Luma measurement to be edited.  If it is
        ``None``, a new measurement is added to the database.

    :type luma_measurement_form: `LumaMeasurementForm`
    :type sample_form: `SampleForm`
    :type process_id: unicode

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    return form_utils.measurement_is_referentially_valid(luma_measurement_form, sample_form, process_id,
                                                         ipv_models.LumaMeasurement)

@login_required
def edit(request, process_id):
    """Edit and create view for Luma measurements.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: The ID of the Luma measurement to be edited.  If it is
        ``None``, a new measurement is added to the database.  

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    luma_measurement = get_object_or_404(ipv_models.LumaMeasurement, id=utils.convert_id_to_int(process_id)) \
        if process_id is not None else None
    permissions.assert_can_add_edit_physical_process(request.user, luma_measurement, ipv_models.LumaMeasurement)
    preset_sample = utils.extract_preset_sample(request) if not luma_measurement else None
    if request.method == "POST":
        sample_form = form_utils.SampleForm(request.user, luma_measurement, preset_sample, request.POST)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not luma_measurement else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if luma_measurement else None
        luma_measurement_form = LumaMeasurementForm(request.user, request.POST, instance=luma_measurement)
        all_valid = is_all_valid(luma_measurement_form, sample_form, remove_from_my_samples_form, edit_description_form)
        referentially_valid = is_referentially_valid(luma_measurement_form, sample_form, process_id)
        if all_valid and referentially_valid:
            luma_measurement = luma_measurement_form.save()
            samples = [sample_form.cleaned_data["sample"]]
            luma_measurement.samples = samples
            feed_utils.Reporter(request.user).report_physical_process(
                luma_measurement, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            success_report = _("{process} was successfully changed in the database.").format(process=luma_measurement) \
                if process_id else _("{process} was successfully added to the database."). \
                format(process=luma_measurement)
            return utils.successful_response(request, success_report, json_response=luma_measurement.pk)
    else:
        initial = {}
        if process_id is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
        luma_measurement_form = LumaMeasurementForm(request.user, instance=luma_measurement, initial=initial)
        initial = {}
        if luma_measurement:
            samples = luma_measurement.samples.all()
            if samples:
                initial["sample"] = samples[0].pk
        sample_form = form_utils.SampleForm(request.user, luma_measurement, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not luma_measurement else None
        edit_description_form = form_utils.EditDescriptionForm() if luma_measurement else None
    title = _("Luma measurement of {sample}").format(sample=samples[0]) if luma_measurement \
        else _("Add Luma measurement")
    return render_to_response("samples/edit_luma_measurement.html",
                              {"title": title,
                               "luma_measurement": luma_measurement_form,
                               "sample": sample_form,
                               "remove_from_my_samples": remove_from_my_samples_form,
                               "edit_description": edit_description_form},
                              context_instance=RequestContext(request))
