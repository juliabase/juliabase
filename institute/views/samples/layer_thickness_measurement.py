#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
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


from __future__ import unicode_literals
from os import path
import datetime
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.forms.util import ValidationError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
import samples.utils.views as utils
import institute.utils.views as form_utils
from samples import permissions
from institute.models import LayerThicknessMeasurement
from django.conf import settings


class LayerThicknessForm(utils.ProcessForm):
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

    :type sample_form: `samples.view.form_utils.SampleSelectForm`
    :type layer_thickness_form: `LayerThicknessForm`
    :type edit_description_form: `samples.views.form_utils.EditDescriptionForm`


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


def is_referentially_valid(layer_thickness_form, sample_form):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `layer_thickness_form`: a bound layer thickness form
      - `sample_form`: a bound sample selection form

    :type layer_thickness_form: `LayerThicknessForm`
    :type sample_form: `samples.views.form_utils.SampleSelectForm`

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    return layer_thickness_form.measurement_is_referentially_valid(sample_form)


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
        sample_form = utils.SampleSelectForm(request.user, layer_thickness_measurement, preset_sample, request.POST)
        edit_description_form = utils.EditDescriptionForm(request.POST) if layer_thickness_measurement else None
        all_valid = is_all_valid(sample_form, layer_thickness_form, edit_description_form)
        referentially_valid = is_referentially_valid(layer_thickness_form, sample_form)
        if all_valid and referentially_valid:
            layer_thickness_measurement = layer_thickness_form.save()
            layer_thickness_measurement.samples = [sample_form.cleaned_data["sample"]]
            utils.Reporter(request.user).report_physical_process(
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
        sample_form = utils.SampleSelectForm(request.user, layer_thickness_measurement, preset_sample, initial=initial)
        edit_description_form = utils.EditDescriptionForm() if layer_thickness_measurement else None
    title = _("Thickness of {sample}").format(sample=old_sample) if layer_thickness_measurement else _("Add thickness")
    return render(request, "samples/edit_layer_thickness_measurement.html",
                  {"title": title, "measurement": layer_thickness_form, "sample": sample_form,
                   "edit_description": edit_description_form})
