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


from __future__ import unicode_literals
from os import path
import datetime
from django import forms
from django.template import RequestContext
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.forms.util import ValidationError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from samples.views import utils, feed_utils
from institute.views import form_utils
from samples import permissions
from institute.models import LayerThicknessMeasurement
from django.conf import settings


class LayerThicknessForm(form_utils.ProcessForm):
    """Form for the layer thickness measurement.
    """
    class Meta:
        model = LayerThicknessMeasurement
        fields = "__all__"


def is_all_valid(sample_form, layer_thickness_form, edit_description_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `sample_form`: a bound sample selection form
      - `layer_thickness_form`: a bound layer thickness form
      - `edit_description_form`: a bound edit-description form

    :type sample_form: `SampleForm`
    :type layer_thickness_form: `LayerThicknessForm`
    :type edit_description_form: `form_utils.EditDescriptionForm`


    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = layer_thickness_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid


def is_referentially_valid(layer_thickness_form, sample_form, process_id):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `layer_thickness_form`: a bound layer thickness form
      - `sample_form`: a bound sample selection form
      - `process_id`: The number of the Layer Thickness Measurement to
        be edited.  If it is ``None``, a new measurement is added to the
        database.

    :type layer_thickness_form: `LayerThicknessForm`
    :type sample_form: `SampleForm`
    :type process_id: unicode

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    return form_utils.measurement_is_referentially_valid(layer_thickness_form, sample_form, process_id,
                                                         LayerThicknessMeasurement)


@login_required
def edit(request, layer_thickness_measurement_id):
    """Edit and create view for Layer Thickness Measurements.

    :Parameters:
      - `request`: the current HTTP Request object
      - `layer_thickness_measurement_id`: The number of the Layer Thickness Measurement to
        be edited.  If it is ``None``, a new measurement is added to the
        database.

    :type request: ``HttpRequest``
    :type layer_thickness_measurement_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    layer_thickness_measurement = \
        get_object_or_404(LayerThicknessMeasurement, id=utils.convert_id_to_int(layer_thickness_measurement_id)) \
        if layer_thickness_measurement_id is not None else None
    old_sample = layer_thickness_measurement.samples.get() if layer_thickness_measurement else None
    permissions.assert_can_add_edit_physical_process(request.user, layer_thickness_measurement,
                                                     LayerThicknessMeasurement)
    preset_sample = utils.extract_preset_sample(request) if not layer_thickness_measurement else None
    if request.method == "POST":
        layer_thickness_form = LayerThicknessForm(request.user, request.POST, instance=layer_thickness_measurement)
        sample_form = form_utils.SampleForm(request.user, layer_thickness_measurement, preset_sample, request.POST)
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if layer_thickness_measurement else None
        all_valid = is_all_valid(sample_form, layer_thickness_form, edit_description_form)
        referentially_valid = is_referentially_valid(layer_thickness_form, sample_form, layer_thickness_measurement_id)
        if all_valid and referentially_valid:
            layer_thickness_measurement = layer_thickness_form.save()
            layer_thickness_measurement.samples = [sample_form.cleaned_data["sample"]]
            feed_utils.Reporter(request.user).report_physical_process(
                layer_thickness_measurement, edit_description_form.cleaned_data if edit_description_form else None)
            success_report = _("{measurement} was successfully changed in the database."). \
                format(measurement=layer_thickness_measurement) if layer_thickness_measurement_id else \
                _("{measurement} was successfully added to the database.").format(measurement=layer_thickness_measurement)
            return utils.successful_response(request, success_report, json_response=layer_thickness_measurement.pk)
    else:
        initial = {}
        if layer_thickness_measurement_id is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
        if layer_thickness_measurement:
            initial["thickness"] = LayerThicknessMeasurement.convert_thickness(layer_thickness_measurement.thickness,
                                                                               "nm", layer_thickness_measurement.unit)
        layer_thickness_form = LayerThicknessForm(request.user, instance=layer_thickness_measurement, initial=initial)
        initial = {}
        if old_sample:
            initial["sample"] = old_sample.pk
        sample_form = form_utils.SampleForm(request.user, layer_thickness_measurement, preset_sample, initial=initial)
        edit_description_form = form_utils.EditDescriptionForm() if layer_thickness_measurement else None
    title = _("Thickness of {sample}").format(sample=old_sample) if layer_thickness_measurement else _("Add thickness")
    return render_to_response("samples/edit_layer_thickness_measurement.html",
                              {"title": title,
                               "measurement": layer_thickness_form,
                               "sample": sample_form,
                               "edit_description": edit_description_form},
                              context_instance=RequestContext(request))
