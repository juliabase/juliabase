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


from __future__ import division, unicode_literals

from os import path
import datetime
from django import forms
from django.template import RequestContext
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.forms.util import ValidationError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from samples.views import utils, feed_utils
from chantal_institute.views import form_utils
from samples import permissions
import chantal_institute.models as ipv_models
from django.conf import settings
from chantal_common.utils import append_error


class SputterCharacterizationForm(form_utils.ProcessForm):
    """Form for the sputter characterisation.
    """
    _ = ugettext_lazy
    combined_operator = form_utils.OperatorField(label=_("Operator"))

    def __init__(self, user, sample, *args, **kwargs):
        super(SputterCharacterizationForm, self).__init__(*args, **kwargs)
        self.user = user
        self.old_measurement = kwargs.get("instance")
        self.fields["combined_operator"].set_choices(user, self.old_measurement)
        if not user.is_staff:
            self.fields["external_operator"].choices = []
            self.fields["operator"].choices = []
            self.fields["operator"].required = False
        else:
            self.fields["combined_operator"].required = False
        self.fields["large_sputter_deposition"].queryset = ipv_models.LargeSputterDeposition.objects.filter(samples=sample)
        self.fields["new_cluster_tool_deposition"].queryset = \
            ipv_models.NewClusterToolDeposition.objects.filter(samples=sample)

    def clean_timestamp(self):
        if not self.user.is_staff and self.old_measurement:
            return self.old_measurement.timestamp
        return self.cleaned_data["timestamp"]

    def clean_timestamp_inaccuracy(self):
        if not self.user.is_staff and self.old_measurement:
            return self.old_measurement.timestamp_inaccuracy
        return self.cleaned_data["timestamp_inaccuracy"]

    def clean(self):
        _ = ugettext
        cleaned_data = self.cleaned_data
        # FixMe: The following could be done in ProcessForm.clean().
        final_operator = self.cleaned_data.get("operator")
        final_external_operator = self.cleaned_data.get("external_operator")
        if self.cleaned_data.get("combined_operator"):
            operator, external_operator = self.cleaned_data["combined_operator"]
            if operator:
                if final_operator and final_operator != operator:
                    append_error(self, "Your operator and combined operator didn't match.", "combined_operator")
                else:
                    final_operator = operator
            if external_operator:
                if final_external_operator and final_external_operator != external_operator:
                    append_error(self, "Your external operator and combined external operator didn't match.",
                                 "combined_external_operator")
                else:
                    final_external_operator = external_operator
        if not final_operator:
            # Can only happen for non-staff.  I deliberately overwrite a
            # previous operator because this way, we can log who changed it.
            final_operator = self.user
        self.cleaned_data["operator"], self.cleaned_data["external_operator"] = final_operator, final_external_operator
        if len(filter(None, [self.cleaned_data.get("large_sputter_deposition"),
                             self.cleaned_data.get("new_cluster_tool_deposition")])) > 1:
            append_error(self, _("You must not select more than one deposition."))
        return cleaned_data

    class Meta:
        model = ipv_models.SputterCharacterization


def is_all_valid(sample_form, sputter_characterization_form, remove_from_my_samples_form, edit_description_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `sample_form`: a bound sample selection form
      - `sputter_characterization_form`: a bound sputter characterisation form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form
      - `edit_description_form`: a bound edit-description form

    :type sample_form: `SampleForm`
    :type sputter_characterization_form: `SputterCharacterizationForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm`


    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = sputter_characterization_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid


def is_referentially_valid(sputter_characterization_form, sample_form, process_id):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `sputter_characterization_form`: a bound sputter characterisation form
      - `sample_form`: a bound sample selection form
      - `process_id`: The number of the sputter characterisation to
        be edited.  If it is ``None``, a new measurement is added to the
        database.

    :type sputter_characterization_form: `SputterCharacterizationForm`
    :type sample_form: `SampleForm`
    :type process_id: unicode

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    return form_utils.measurement_is_referentially_valid(sputter_characterization_form,
                                                         sample_form,
                                                         process_id,
                                                         ipv_models.SputterCharacterization)
@login_required
def edit(request, process_id):
    """Edit and create view for sputter characterisations.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: The number of the sputter characterisation to
        be edited.  If it is ``None``, a new measurement is added to the
        database.

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sputter_characterization = \
        get_object_or_404(ipv_models.SputterCharacterization, id=utils.convert_id_to_int(process_id)) \
        if process_id is not None else None
    old_sample = sputter_characterization.samples.get() if sputter_characterization else None
    permissions.assert_can_add_edit_physical_process(request.user, sputter_characterization,
                                                     ipv_models.SputterCharacterization)
    preset_sample = utils.extract_preset_sample(request) if not sputter_characterization else None
    if request.method == "POST":
        sample_form = form_utils.SampleForm(request.user, sputter_characterization, preset_sample, request.POST)
        sample = sample_form.is_valid() and sample_form.cleaned_data["sample"] or old_sample or preset_sample
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not sputter_characterization \
            else None
        sputter_characterization_form = SputterCharacterizationForm(request.user, sample, request.POST,
                                                                    instance=sputter_characterization)
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if sputter_characterization else None
        all_valid = is_all_valid(sample_form, sputter_characterization_form, remove_from_my_samples_form,
                                 edit_description_form)
        referentially_valid = is_referentially_valid(sputter_characterization_form, sample_form, process_id)
        if all_valid and referentially_valid:
            sputter_characterization = sputter_characterization_form.save(commit=False)
            if sputter_characterization.r_square and sputter_characterization.thickness:
                sputter_characterization.rho = \
                    float(sputter_characterization.r_square * sputter_characterization.thickness) * 1e-7
            if sputter_characterization.large_sputter_deposition and sputter_characterization.thickness and \
                    sputter_characterization.large_sputter_deposition.layers.count() == 1:
                layer = sputter_characterization.large_sputter_deposition.layers.all()[0]
                if layer.feed_rate and layer.steps:
                    sputter_characterization.deposition_rate = \
                        sputter_characterization.thickness * layer.feed_rate / layer.steps * 60 / 1000
                elif layer.static_time:
                    sputter_characterization.deposition_rate = sputter_characterization.thickness / layer.static_time
            elif sputter_characterization.new_cluster_tool_deposition and sputter_characterization.thickness:
                sputter_layers = [layer for layer in sputter_characterization.new_cluster_tool_deposition.layers.all()
                                  if layer.content_type.model_class() == ipv_models.NewClusterToolSputterLayer]
                if len(sputter_layers) == 1:
                    layer = sputter_layers[0].actual_instance
                    sputter_times = layer.slots.filter(number__in=[1, 3]).values_list("time", flat=True)
                    sputter_time = sputter_times[0] or sputter_times[1]
                    if sputter_time:
                        sputter_characterization.deposition_rate = sputter_characterization.thickness / sputter_time
            sputter_characterization.save()
            samples = [sample_form.cleaned_data["sample"]]
            sputter_characterization.samples = samples
            feed_utils.Reporter(request.user).report_physical_process(
                sputter_characterization, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            success_report = _("{measurement} was successfully changed in the database."). \
                format(measurement=sputter_characterization) if process_id else \
                _("{measurement} was successfully added to the database.").format(measurement=sputter_characterization)
            return utils.successful_response(request, success_report, json_response=sputter_characterization.pk)
    else:
        initial = {}
        if process_id is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
        sputter_characterization_form = SputterCharacterizationForm(request.user, old_sample or preset_sample,
                                                                    instance=sputter_characterization, initial=initial)
        initial = {}
        if old_sample:
            initial["sample"] = old_sample.pk
        sample_form = form_utils.SampleForm(request.user, sputter_characterization, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not sputter_characterization else None
        edit_description_form = form_utils.EditDescriptionForm() if sputter_characterization else None
    title = _("Sputter characterization of {sample}").format(sample=old_sample) if sputter_characterization \
        else _("Add sputter characterization")
    return render_to_response("samples/edit_sputter_characterization.html",
                              {"title": title,
                               "remove_from_my_samples": remove_from_my_samples_form,
                               "measurement": sputter_characterization_form,
                               "sample": sample_form,
                               "edit_description": edit_description_form},
                              context_instance=RequestContext(request))
