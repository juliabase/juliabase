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

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django import forms
from django.utils.translation import ugettext
from samples.views import utils, feed_utils
from chantal_institute.views import form_utils
import chantal_institute.models as ipv_models
import chantal_institute.views.solarsimulator_measurement_utils as solarsimulator_utils
from samples import permissions

_ = ugettext

class SolarsimulatorMeasurementForm(solarsimulator_utils.SolarsimulatorMeasurementForm):

    def __init__(self, user, *args, **kwargs):
        super(SolarsimulatorMeasurementForm, self).__init__(user, *args, **kwargs)
        self.fields["irradiance"].widget.attrs.update({"size": "5", "readonly": "readonly"})

    class Meta:
        model = ipv_models.SolarsimulatorDarkMeasurement


class SolarsimulatorDarkCellForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(SolarsimulatorDarkCellForm, self).__init__(*args, **kwargs)
        self.type = "dark"

    def validate_unique(self):
        pass

    class Meta:
        model = ipv_models.SolarsimulatorDarkCellMeasurement
        exclude = ("measurement")


@login_required
def edit(request, process_id):
    """Create or edit an existing solarsimulator measurement.

    If you pass "only_single_cell_added=true" in the query string *and* you
    have a staff account, no feed entries are generated.  This is to make the
    MAIKE crawler less noisy if non-standard-Jülich cell layout is used and a
    whole substrate is split over many single files which have to be imported
    one by one.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the id of the solarsimulator measurement; if ``None``, a
        new measurement is created

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    solarsimulator_measurement = get_object_or_404(ipv_models.SolarsimulatorDarkMeasurement, id=process_id)\
        if process_id is not None else None
    permissions.assert_can_add_edit_physical_process(request.user, solarsimulator_measurement,
                                                     ipv_models.SolarsimulatorDarkMeasurement)
    preset_sample = utils.extract_preset_sample(request) if not solarsimulator_measurement else None
    if request.method == "POST":
        sample_form = form_utils.SampleForm(request.user, solarsimulator_measurement, preset_sample, request.POST)
        samples = solarsimulator_measurement.samples.all() if solarsimulator_measurement else None
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not solarsimulator_measurement \
            else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if solarsimulator_measurement else None
        solarsimulator_cell_forms = solarsimulator_utils.solarsimulator_cell_forms_from_post(request.POST,
                                                                                             SolarsimulatorDarkCellForm)
        solarsimulator_measurement_form = SolarsimulatorMeasurementForm(request.user, request.POST,
                                                                        instance=solarsimulator_measurement)
        all_valid = solarsimulator_utils.is_all_valid(solarsimulator_measurement_form, sample_form, remove_from_my_samples_form,
                                 edit_description_form, solarsimulator_cell_forms)
        referentially_valid = solarsimulator_utils.is_referentially_valid(solarsimulator_measurement_form,
                                                                          solarsimulator_cell_forms, sample_form, process_id)
        if all_valid and referentially_valid:
            solarsimulator_measurement = solarsimulator_measurement_form.save()
            samples = [sample_form.cleaned_data["sample"]]
            solarsimulator_measurement.samples = samples
            solarsimulator_measurement.dark_cells.all().delete()
            for solarsimulator_cell_form in solarsimulator_cell_forms:
                solarsimulator_cell_measurement = solarsimulator_cell_form.save(commit=False)
                solarsimulator_cell_measurement.measurement = solarsimulator_measurement
                solarsimulator_cell_measurement.save()
            if not request.user.is_staff or request.GET.get("only_single_cell_added") != "true":
                reporter = request.user if not request.user.is_staff \
                    else solarsimulator_measurement_form.cleaned_data["operator"]
                feed_utils.Reporter(reporter).report_physical_process(
                    solarsimulator_measurement, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            success_report = _(u"{process} was successfully changed in the database."). \
                format(process=solarsimulator_measurement) \
                if process_id else _(u"{process} was successfully added to the database."). \
                format(process=solarsimulator_measurement)
            return utils.successful_response(request, success_report, json_response=solarsimulator_measurement.pk)
    else:
        solarsimulator_measurement_form = SolarsimulatorMeasurementForm(request.user, instance=solarsimulator_measurement)
        initial = {}
        solarsimulator_cell_forms = []
        if solarsimulator_measurement:
            samples = solarsimulator_measurement.samples.all()
            if samples:
                initial["sample"] = samples[0].pk
            solarsimulator_cell_forms = \
                [SolarsimulatorDarkCellForm(prefix=str(index), instance=solarsimulator_dark_cell)
                 for index, solarsimulator_dark_cell in enumerate(solarsimulator_measurement.dark_cells.all())]
        sample_form = form_utils.SampleForm(request.user, solarsimulator_measurement, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not solarsimulator_measurement else None
        edit_description_form = form_utils.EditDescriptionForm() if solarsimulator_measurement else None
    title = _(u"{name} of {sample}").format(name=ipv_models.SolarsimulatorDarkMeasurement._meta.verbose_name,
                                                        sample=samples[0]) if solarsimulator_measurement \
        else _(u"Add {name}").format(name=ipv_models.SolarsimulatorDarkMeasurement._meta.verbose_name)
    return render_to_response("samples/edit_solarsimulator_measurement.html",
                              {"title": title,
                               "solarsimulator_measurement": solarsimulator_measurement_form,
                               "solarsimulator_cell_measurements": solarsimulator_cell_forms,
                               "sample": sample_form,
                               "remove_from_my_samples": remove_from_my_samples_form,
                               "edit_description": edit_description_form},
                              context_instance=RequestContext(request))

@login_required
def show(request, process_id):
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
    return solarsimulator_utils. show_solarsimulator_measurement(request, process_id, ipv_models.SolarsimulatorDarkMeasurement)

