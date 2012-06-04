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
import datetime, re
from django import forms
from django.template import RequestContext
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms.util import ValidationError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from samples.views import utils, feed_utils
from chantal_ipv.views import form_utils
from samples import permissions
import chantal_ipv.models as ipv_models
from django.conf import settings
from chantal_common.utils import append_error, is_json_requested, respond_in_json


class DSRForm(form_utils.ProcessForm):
    """Form for the DSR measurement.
    """
    _ = ugettext_lazy
    combined_operator = form_utils.OperatorField(label=_(u"Operator"))

    def __init__(self, user, *args, **kwargs):
        super(DSRForm, self).__init__(*args, **kwargs)
        measurement = kwargs.get("instance")
        self.user = user
        self.fields["combined_operator"].set_choices(user, measurement)
        if not user.is_staff:
            self.fields["external_operator"].choices = []
            self.fields["operator"].choices = []
            self.fields["operator"].required = False
        else:
            self.fields["combined_operator"].required = False
        self.fields["timestamp"].initial = datetime.datetime.now()


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
        model = ipv_models.DSRMeasurement
        exclude = ("external_operator",)


class IVForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(IVForm, self).__init__(*args, **kwargs)

    def validate_unique(self):
        """Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `edit`.  I cannot use Django's built-in test anyway
        because it leads to an error message in wrong German (difficult to fix,
        even for the Django guys).
        """
        pass

    class Meta:
        model = ipv_models.DSRIVData
        exclude = ("measurement",)


class SpectralForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(SpectralForm, self).__init__(*args, **kwargs)

    def validate_unique(self):
        """Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `edit`.  I cannot use Django's built-in test anyway
        because it leads to an error message in wrong German (difficult to fix,
        even for the Django guys).
        """
        pass

    class Meta:
        model = ipv_models.DSRSpectralData
        exclude = ("measurement",)


def _collect_subform_indices(post_data, subform_key):
    subform_name_pattern = re.compile(r"(?P<index>\d+)(_\d+)*-(?P<subform_key>.+)")
    indices = []
    for key in post_data.iterkeys():
        match = subform_name_pattern.match(key)
        if match:
            index = int(match.group("index"))
            if match.group("subform_key") == subform_key:
                indices.append(int(index))
    return sorted(indices)

def data_forms_from_post(post, form_cls):
    """This function initializes the iv and spectral forms from the post data.

    :Parameters:
      - `post`: the post dictionary

    :type post: `request.POST`

    :Return:
     a list of bound iv forms or spectral forms

    :rtype: list
    """
    if form_cls == IVForm:
        indices = _collect_subform_indices(post, "iv_data_file")
    elif form_cls == SpectralForm:
        indices = _collect_subform_indices(post, "spectral_data_file")
    return [form_cls(post, prefix=str(measurement_index)) for measurement_index in indices]


def is_all_valid(sample_form, dsr_measurement_form, iv_forms, spectral_forms,
                 edit_description_form, remove_from_my_samples_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `sample_form`: a bound sample selection form
      - `dsr_measurement_form`: a bound DSR measurement form
      - `iv_forms`:
      - `spectral_forms`:
      - `edit_description_form`: a bound edit-description form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form

    :type sample_form: `SampleForm`
    :type dsr_measurement_form: `DSRMeasurementForm`
    :
    :
    :type edit_description_form: `form_utils.EditDescriptionForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``


    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = dsr_measurement_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    if iv_forms:
        all_valid = all([iv_form.is_valid() for iv_form in iv_forms]) and all_valid
    if spectral_forms:
        all_valid = all([spectral_form.is_valid() for spectral_form in spectral_forms]) and all_valid
    return all_valid


def is_referentially_valid(dsr_measurement_form, iv_forms, spectral_forms, sample_form, process_id):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `dsr_measurement_form`: a bound DSR measurement form
      - `iv_forms`: list of bound iv data file forms
      - `spectral_forms`: list of bound spectral data file forms
      - `sample_form`: a bound sample selection form
      - `dsr_number`: The DSR number of the DSR measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.

    :type dsr_measurement_form: `DSRMeasurementForm`
    :type iv_forms: list of `IVForm`
    :type spectral_forms: list of `SpectralForm`
    :type sample_form: `SampleForm`
    :type dsr_number: unicode

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if dsr_measurement_form and dsr_measurement_form.is_valid():
        if sample_form.is_valid() and referentially_valid:
            sample = sample_form.cleaned_data["sample"]
            if form_utils.dead_samples([sample], dsr_measurement_form.cleaned_data.get("timestamp")):
                append_error(dsr_measurement_form, _(u"Sample is already dead at this time."),
                             "timestamp")
                referentially_valid = False
        for measurement_form in iv_forms:
            if measurement_form.is_valid():
                data_file = measurement_form.cleaned_data["iv_data_file"]
                query_set = measurement_form._meta.model.objects.filter(iv_data_file=data_file)
                if process_id:
                    query_set = query_set.exclude(measurement__id=process_id)
                if query_set.exists():
                    append_error(measurement_form,
                                 _(u"A dsr measurement with this data file already exists."))
                    referentially_valid = False
        for measurement_form in spectral_forms:
            if measurement_form.is_valid():
                data_file = measurement_form.cleaned_data["spectral_data_file"]
                query_set = measurement_form._meta.model.objects.filter(spectral_data_file=data_file)
                if process_id:
                    query_set = query_set.exclude(measurement__id=process_id)
                if query_set.exists():
                    append_error(measurement_form,
                                 _(u"A dsr measurement with this data file already exists."))
                    referentially_valid = False
    else:
        referentially_valid = False
    return referentially_valid



@login_required
def edit(request, process_id):
    """Edit and create view for DSR measurements.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: The database id of the DSR measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    dsr_measurement = get_object_or_404(ipv_models.DSRMeasurement, id=utils.convert_id_to_int(process_id)) \
    if process_id is not None else None
    permissions.assert_can_add_edit_physical_process(request.user, dsr_measurement, ipv_models.DSRMeasurement)
    preset_sample = utils.extract_preset_sample(request) if not dsr_measurement else None
    if request.method == "POST":
        dsr_form = DSRForm(request.user, request.POST, instance=dsr_measurement)
        iv_forms = data_forms_from_post(request.POST, IVForm)
        spectral_forms = data_forms_from_post(request.POST, SpectralForm)
        sample_form = form_utils.SampleForm(request.user, dsr_measurement, preset_sample, request.POST)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not dsr_measurement else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if dsr_measurement else None
        all_valid = is_all_valid(sample_form, dsr_form, iv_forms, spectral_forms, edit_description_form,
                                 remove_from_my_samples_form)
        samples = [sample_form.cleaned_data["sample"]]
        referentially_valid = is_referentially_valid(dsr_form, iv_forms, spectral_forms, sample_form, process_id)
        if all_valid and referentially_valid:
            dsr_measurement = dsr_form.save()
            dsr_measurement.samples = samples
            dsr_measurement.iv_data_files.all().delete()
            for iv_form in iv_forms:
                iv_data = iv_form.save(commit=False)
                iv_data.measurement = dsr_measurement
                iv_data.save()
            dsr_measurement.spectral_data_files.all().delete()
            for spectral_form in spectral_forms:
                spectral_data = spectral_form.save(commit=False)
                spectral_data.measurement = dsr_measurement
                spectral_data.save()
            feed_utils.Reporter(request.user).report_physical_process(
                dsr_measurement, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            success_report = _("{process} was successfully changed in the database.").format(process=dsr_measurement) \
                if process_id else _("{process} was successfully added to the database.").format(process=dsr_measurement)
            return utils.successful_response(request, success_report, json_response=dsr_measurement.pk)
    else:
        initial = {}
        if process_id is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
        dsr_form = DSRForm(request.user, instance=dsr_measurement, initial=initial)
        initial = {}
        if dsr_measurement:
            samples = dsr_measurement.samples.all()
            if samples:
                initial["sample"] = samples[0].pk
            iv_forms = [IVForm(prefix=str(index), instance=iv_data)
                        for index, iv_data in enumerate(dsr_measurement.iv_data_files.all())]
            spectral_forms = [SpectralForm(prefix=str(index), instance=spectral_data)
                              for index, spectral_data in enumerate(dsr_measurement.spectral_data_files.all())]
        else:
            iv_forms = spectral_forms = []
        sample_form = form_utils.SampleForm(request.user, dsr_measurement, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not dsr_measurement else None
        edit_description_form = form_utils.EditDescriptionForm() if dsr_measurement else None
    title = _("DSR measurement of {sample}").format(sample=samples[0]) if dsr_measurement else _("Add DSR measurement")
    return render_to_response("samples/edit_dsr_measurement.html",
                              {"title": title,
                               "dsr_measurement": dsr_form,
                               "sample": sample_form,
                               "iv_data_files": iv_forms,
                               "spectral_data_files": spectral_forms,
                               "remove_from_my_samples": remove_from_my_samples_form,
                               "edit_description": edit_description_form},
                              context_instance=RequestContext(request))


def show(request, process_id):
    """Show an existing  measurement.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the id of the  measurement

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    dsr_measurement = get_object_or_404(ipv_models.DSRMeasurement, id=utils.convert_id_to_int(process_id))
    permissions.assert_can_view_physical_process(request.user, dsr_measurement)
    if is_json_requested(request):
        return respond_in_json(dsr_measurement.get_data().to_dict())
    try:
        iv_data_list = dsr_measurement.iv_data_files.all()
    except ipv_models.DSRIVData.DoesNotExist:
        iv_data_list = None
    try:
        spectral_data_list = dsr_measurement.spectral_data_files.all()
    except ipv_models.DSRSpectralData.DoesNotExist:
        spectral_data_list = None
    template_context = {"title": _(u"DSR measurement from cell {cell_position}").format(cell_position=dsr_measurement.cell_position),
                        "samples": dsr_measurement.samples.all(), "process": dsr_measurement,
                        "iv_data_list": iv_data_list, "spectral_data_list": spectral_data_list
                        }
    template_context.update(utils.digest_process(dsr_measurement, request.user))
