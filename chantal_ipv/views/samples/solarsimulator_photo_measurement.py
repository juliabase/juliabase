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
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django import forms
from django.utils.translation import ugettext
from samples.views import utils, feed_utils
from chantal_ipv.views import form_utils
from samples import permissions
import chantal_ipv.models as ipv_models
import chantal_ipv.views.solarsimulator_measurement_utils as solarsimulator_utils

_ = ugettext

class SolarsimulatorMeasurementForm(solarsimulator_utils.SolarsimulatorMeasurementForm):
    class Meta:
        model = ipv_models.SolarsimulatorPhotoMeasurement


class SolarsimulatorPhotoCellForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(SolarsimulatorPhotoCellForm, self).__init__(*args, **kwargs)
        self.type = "photo"

    def validate_unique(self):
        pass

    class Meta:
        model = ipv_models.SolarsimulatorPhotoCellMeasurement
        exclude = ("measurement")


def cell_statistics(solarsimulator_measurement):
    eighty_per_cent_from_best_cell = None
    cells_in_yield = []
    five_best = []
    for index, cell in enumerate(solarsimulator_measurement.photo_cells.order_by("-eta")):
        if index < 5:
            five_best.append(cell)
        if index == 0:
            eighty_per_cent_from_best_cell = cell.eta * 0.8
        if cell.eta > eighty_per_cent_from_best_cell:
            cells_in_yield.append(cell)
        elif index > 4:
            break
    return cells_in_yield, five_best


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
    solarsimulator_measurement = get_object_or_404(ipv_models.SolarsimulatorPhotoMeasurement, id=process_id)\
        if process_id is not None else None
    permissions.assert_can_add_edit_physical_process(request.user, solarsimulator_measurement,
                                                     ipv_models.SolarsimulatorPhotoMeasurement)
    preset_sample = utils.extract_preset_sample(request) if not solarsimulator_measurement else None
    if request.method == "POST":
        sample_form = form_utils.SampleForm(request.user, solarsimulator_measurement, preset_sample, request.POST)
        samples = solarsimulator_measurement.samples.all() if solarsimulator_measurement else None
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not solarsimulator_measurement \
            else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if solarsimulator_measurement else None
        solarsimulator_cell_forms = solarsimulator_utils.solarsimulator_cell_forms_from_post(request.POST,
                                                                                             SolarsimulatorPhotoCellForm)
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
            solarsimulator_measurement.photo_cells.all().delete()
            for solarsimulator_cell_form in solarsimulator_cell_forms:
                solarsimulator_cell_measurement = solarsimulator_cell_form.save(commit=False)
                solarsimulator_cell_measurement.measurement = solarsimulator_measurement
                solarsimulator_cell_measurement.save()
            if solarsimulator_measurement.irradiance == "AM1.5":
                cells_in_yield, five_best = cell_statistics(solarsimulator_measurement)
                solarsimulator_measurement.best_cell_eta = five_best[0].eta
                solarsimulator_measurement.best_cell_voc = five_best[0].voc
                solarsimulator_measurement.best_cell_isc = five_best[0].isc
                solarsimulator_measurement.best_cell_ff = five_best[0].ff
                solarsimulator_measurement.best_cell_rsh = five_best[0].rsh
                solarsimulator_measurement.best_cell_rs = five_best[0].rs
                solarsimulator_measurement.cell_yield = len(cells_in_yield)
                solarsimulator_measurement.median_eta = utils.median([cell.eta for cell in cells_in_yield])
                solarsimulator_measurement.median_voc = utils.median([cell.voc for cell in cells_in_yield])
                solarsimulator_measurement.median_isc = utils.median([cell.isc for cell in cells_in_yield if cell.isc])
                solarsimulator_measurement.median_ff = utils.median([cell.ff for cell in cells_in_yield])
                solarsimulator_measurement.median_rsh = utils.median([cell.rsh for cell in cells_in_yield])
                solarsimulator_measurement.median_rs = utils.median([cell.rs for cell in cells_in_yield])
                solarsimulator_measurement.average_five_best_eta = utils.average([cell.eta for cell in five_best])
                solarsimulator_measurement.average_five_best_voc = utils.average([cell.voc for cell in five_best])
                solarsimulator_measurement.average_five_best_isc = utils.average([cell.isc for cell in five_best if cell.isc])
                solarsimulator_measurement.average_five_best_ff = utils.average([cell.ff for cell in five_best])
                solarsimulator_measurement.average_five_best_rsh = utils.average([cell.rsh for cell in five_best])
                solarsimulator_measurement.average_five_best_rs = utils.average([cell.rs for cell in five_best])
                solarsimulator_measurement.save()
            else:
                wihte_measurement = solarsimulator_utils.get_previous_white_measurement(samples[0],
                                                    solarsimulator_measurement.timestamp, solarsimulator_measurement.irradiance)
                if wihte_measurement:
                    if solarsimulator_measurement.irradiance == "OG590":
                        cells_in_yield, five_best = cell_statistics(solarsimulator_measurement)
                        wihte_measurement.best_cell_isc_r = five_best[0].isc
                        wihte_measurement.best_cell_ff_r = five_best[0].ff
                        wihte_measurement.median_isc_r = utils.median([cell.isc for cell in cells_in_yield if cell.isc])
                        wihte_measurement.median_ff_r = utils.median([cell.ff for cell in cells_in_yield])
                        wihte_measurement.average_five_best_isc_r = utils.average([cell.isc for cell in five_best if cell.isc])
                        wihte_measurement.average_five_best_ff_r = utils.average([cell.ff for cell in five_best])
                    elif solarsimulator_measurement.irradiance == "BG7":
                        cells_in_yield, five_best = cell_statistics(solarsimulator_measurement)
                        wihte_measurement.best_cell_isc_b = five_best[0].isc
                        wihte_measurement.best_cell_ff_b = five_best[0].ff
                        wihte_measurement.median_isc_b = utils.median([cell.isc for cell in cells_in_yield if cell.isc])
                        wihte_measurement.median_ff_b = utils.median([cell.ff for cell in cells_in_yield])
                        wihte_measurement.average_five_best_isc_b = utils.average([cell.isc for cell in five_best if cell.isc])
                        wihte_measurement.average_five_best_ff_b = utils.average([cell.ff for cell in five_best])
                    wihte_measurement.save()
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
                [SolarsimulatorPhotoCellForm(prefix=str(index), instance=solarsimulator_photo_cell)
                 for index, solarsimulator_photo_cell in enumerate(solarsimulator_measurement.photo_cells.all())]
        sample_form = form_utils.SampleForm(request.user, solarsimulator_measurement, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not solarsimulator_measurement else None
        edit_description_form = form_utils.EditDescriptionForm() if solarsimulator_measurement else None
    title = _(u"{name} of {sample}").format(name=ipv_models.SolarsimulatorPhotoMeasurement._meta.verbose_name,
                                                        sample=samples[0]) if solarsimulator_measurement \
        else _(u"Add {name}").format(name=ipv_models.SolarsimulatorPhotoMeasurement._meta.verbose_name)
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
    """Show an existing ssolarsimulator photo measurement.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the id of the solarsimulator photo measurement

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return solarsimulator_utils.show_solarsimulator_measurement(request, process_id, ipv_models.SolarsimulatorPhotoMeasurement)
