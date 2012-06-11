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

import datetime
from django.utils.translation import ugettext_lazy
from chantal_institute.views import form_utils
from django.utils.translation import ugettext
from chantal_institute.models import SolarsimulatorDarkMeasurement, SolarsimulatorPhotoMeasurement
from django.shortcuts import render_to_response, get_object_or_404
from samples import permissions
from samples.views import utils
from django.template import RequestContext
from chantal_common.utils import append_error, is_json_requested, respond_in_json

_ = ugettext

class SolarsimulatorMeasurementForm(form_utils.ProcessForm):
    _ = ugettext_lazy
    combined_operator = form_utils.OperatorField(label=_(u"Operator"))

    def __init__(self, user, *args, **kwargs):
        super(SolarsimulatorMeasurementForm, self).__init__(*args, **kwargs)
        old_instance = kwargs.get("instance")
        self.user = user
        self.fields["combined_operator"].set_choices(user, old_instance)
        if not user.is_staff:
            self.fields["external_operator"].choices = []
            self.fields["operator"].choices = []
            self.fields["operator"].required = False
        else:
            self.fields["combined_operator"].required = False
        self.fields["timestamp"].initial = datetime.datetime.now()
        self.fields["temperature"].widget.attrs.update({"size": "5"})

    def clean(self):
        cleaned_data = self.cleaned_data
        final_operator = cleaned_data.get("operator")
        final_external_operator = cleaned_data.get("external_operator")
        if cleaned_data.get("combined_operator"):
            operator, external_operator = cleaned_data["combined_operator"]
            if operator:
                if final_operator and final_operator != operator:
                    append_error(self, u"Your operator and combined operator didn't match.", "combined_operator")
                else:
                    final_operator = operator
            if external_operator:
                if final_external_operator and final_external_operator != external_operator:
                    append_error(self, u"Your external operator and combined external operator didn't match.",
                                 "combined_external_operator")
                else:
                    final_external_operator = external_operator
        if not final_operator:
            # Can only happen for non-staff.  I deliberately overwrite a
            # previous operator because this way, we can log who changed it.
            final_operator = self.user
        cleaned_data["operator"], cleaned_data["external_operator"] = final_operator, final_external_operator
        return cleaned_data

    class Meta:
        abstract = True



def solarsimulator_cell_forms_from_post(post, form_cls):
    """This function initializes the solarsimulator cell forms from the post data.
    It also decides which kind of cell forms is needed.

    :Parameters:
      - `post`: the post dictionary

    :type post: `request.POST`

    :Return:
     a list of bound solarsimulator photo cell forms or solarsimulator dark cell forms

    :rtype: list
    """
    indices = form_utils.collect_subform_indices(post)
    return [form_cls(post, prefix=str(measurement_index)) for measurement_index in indices]


def is_all_valid(solarsimulator_measurement_form, sample_form, remove_from_my_samples_form, edit_description_form,
                 solarsimulator_cell_forms):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `solarsimulator_measurement_form`: a bound solarsimulator measurement form
      - `sample_form`: a bound sample selection form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form
      - `edit_description_form`: a bound edit-description form
      - `solarsimulator_cell_forms`: a list of bound solarsimulator cell forms

    :type solarsimulator_measurement_form: `solarsimulator_utils.SolarsimulatorMeasurementForm`
    :type sample_form: `SampleForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm`
    :type solarsimulator_cell_forms: `SolarsimulatorPhotoCellForm` or
        `SolarsimulatorDarkCellForm`

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = solarsimulator_measurement_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    if solarsimulator_cell_forms:
        all_valid = all([solarsimulator_cell_form.is_valid()
                         for solarsimulator_cell_form in solarsimulator_cell_forms]) and all_valid
    return all_valid


def is_referentially_valid(solarsimulator_measurement_form, solarsimulator_cell_forms, samples_form, process_id=None):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement and whether the related data file exists.

    FixMe: It does not check for the case that the same datapath is used in two
    different solarsimulator measurements.  This should be added.  One may call
    `json_client._get_maike_by_filepath` and catch an exception about multiple
    search results for checking this.

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if not solarsimulator_cell_forms:
        append_error(samples_form, _(u"No measurenents given."))
        referentially_valid = False
    if solarsimulator_measurement_form and solarsimulator_measurement_form.is_valid():
        if samples_form.is_valid() and referentially_valid:
            sample = samples_form.cleaned_data["sample"]
            if form_utils.dead_samples([sample], solarsimulator_measurement_form.cleaned_data.get("timestamp")):
                append_error(solarsimulator_measurement_form, _(u"Sample is already dead at this time."),
                             "timestamp")
                referentially_valid = False
        positions = set()
        for measurement_form in solarsimulator_cell_forms:
            if measurement_form.is_valid():
                data_file = measurement_form.cleaned_data["data_file"]
                cell_index = measurement_form.cleaned_data["cell_index"]
                position = measurement_form.cleaned_data["position"]
                if position in positions:
                    append_error(measurement_form, _(u"This cell position is already given."))
                    referentially_valid = False
                else:
                    positions.add(position)
                cell_index = measurement_form.cleaned_data["cell_index"]
                query_set = measurement_form._meta.model.objects.filter(data_file=data_file, cell_index=cell_index)
                if process_id:
                    query_set = query_set.exclude(measurement__id=process_id)
                if query_set.exists():
                    append_error(measurement_form,
                                 _(u"A solarsimulator measurement with this cell index and data file already exists."))
                    referentially_valid = False
    else:
        referentially_valid = False
    return referentially_valid


def show_solarsimulator_measurement(request, process_id, solarsimulator_measurement_model):
    """Show an existing solarsimulator measurement.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the id of the solarsimulator measurement

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    solarsimulator_measurement = get_object_or_404(solarsimulator_measurement_model, id=utils.convert_id_to_int(process_id))
    permissions.assert_can_view_physical_process(request.user, solarsimulator_measurement)
    if is_json_requested(request):
        return respond_in_json(solarsimulator_measurement.get_data().to_dict())
    template_context = {"title": _(u"Solarsimulator measurement #{number}").format(number=process_id),
                        "samples": solarsimulator_measurement.samples.all(), "process": solarsimulator_measurement,
                        "cells": solarsimulator_measurement.dark_cells.all()
                            if solarsimulator_measurement_model == SolarsimulatorDarkMeasurement
                            else solarsimulator_measurement.photo_cells.all()}
    template_context.update(utils.digest_process(solarsimulator_measurement, request.user))
    return render_to_response("samples/show_process.html", template_context, context_instance=RequestContext(request))


def get_previous_white_measurement(sample, timestamp, irradiance):
    for process in sample.processes.filter(timestamp__lt=timestamp).order_by("-timestamp").iterator():
        try:
            measurement = process.solarsimulatorphotomeasurement
        except SolarsimulatorPhotoMeasurement.DoesNotExist:
            break
        else:
            if measurement.irradiance == irradiance:
                break
            elif measurement.irradiance == "AM1.5":
                return measurement
