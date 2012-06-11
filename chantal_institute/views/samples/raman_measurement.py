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


"""There are two Raman measurments, maybe three in the future, in this institut.
Each measurement has its own view and database model.
This one is for the Raman measurement.
"""

from __future__ import absolute_import, unicode_literals

import datetime, re, codecs
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django import forms
from django.forms.util import ValidationError
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.db.models import Q
import django.contrib.auth.models
from chantal_common.utils import append_error, is_json_requested, respond_in_json
from samples.views import utils, feed_utils
from chantal_institute.views import form_utils
from samples import models, permissions
import chantal_institute.models as institute_models


class SampleForm(forms.Form):
    """Form for the sample selection field.  You can only select *one* sample
    per Raman measurement (in contrast to depositions).
    """
    _ = ugettext_lazy
    # FixMe: Should be lowercase and use .capitalize() to ease translating
    sample = form_utils.SampleField(label=_("Sample"))

    def __init__(self, user, raman_measurement, preset_sample, *args, **kwargs):
        """Form constructor.  I only set the selection of samples to the
        current user's “My Samples”.

        :Parameters:
          - `user`: the current user
          - `raman_measurement`: the Raman measurement to be edited, or ``None`` if
            a new is about to be created
          - `preset_sample`: the sample to which the Raman measurement should be
            appended when creating a new Raman measurement; see
            `utils.extract_preset_sample`

        :type user: `models.UserDetails`
        :type raman_measurement: `institute_models.RamanMeasurement`
        :type preset_sample: `models.Sample`
        """
        super(SampleForm, self).__init__(*args, **kwargs)
        samples = list(user.my_samples.all())
        if raman_measurement:
            samples.extend(raman_measurement.samples.all()[:1])
        if preset_sample:
            samples.append(preset_sample)
            self.fields["sample"].initial = preset_sample.pk
        self.fields["sample"].set_samples(samples, user)


class SimpleRadioSelectRenderer(forms.widgets.RadioFieldRenderer):
    def render(self):
        return mark_safe("""<ul class="radio-select">\n{0}\n</ul>""".format("\n".join(
                    "<li>{0}</li>".format(force_unicode(w)) for w in self)))


class RamanMeasurementForm(form_utils.ProcessForm):
    """Model form for the core Raman measurement data.  I only redefine the
    ``operator`` field here in oder to have the full names of the users.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, sample, raman_model, *args, **kwargs):
        measurement = kwargs.get("instance")
        numbers = raman_model.objects.values_list("number", flat=True)
        next_number = max(numbers) + 1 if numbers else 1
        self.number = measurement.number if measurement else next_number
        kwargs.setdefault("initial", {})["number"] = self.number
        super(RamanMeasurementForm, self).__init__(*args, **kwargs)
        self.fields["datafile"].widget.attrs["size"] = "50"
        self.fields["evaluated_datafile"].widget.attrs["size"] = "50"
        self.fields["number"].widget.attrs.update({"readonly": "readonly"})
        self.fields["number"].required = False
        self.fields["operator"].set_operator(measurement.operator if measurement else user, user.is_staff)
        self.fields["operator"].initial = measurement.operator.pk if measurement else user.pk
        self.fields["dektak_measurement"].queryset = institute_models.DektakMeasurement.objects.filter(samples=sample)
        self.user = user

    def clean_number(self):
        return self.number

    def clean(self):
        _ = ugettext
        def check_special_fields(required, forbidden):
            for fieldname in required:
                if cleaned_data.get(fieldname) is None:
                    append_error(self, _("This field is required for this kind of measurement."), fieldname)
            for fieldname in forbidden:
                if cleaned_data.get(fieldname) is not None:
                    append_error(self, _("This field is forbidden for this kind of measurement."), fieldname)
        cleaned_data = super(RamanMeasurementForm, self).clean()
        kind = cleaned_data.get("kind")
        if kind == "single":
            check_special_fields(
                [], ["sampling_period", "sampling_distance_x", "number_points_x", "sampling_distance_y", "number_points_y"])
        elif kind == "line scan":
            check_special_fields(["sampling_distance_x", "number_points_x"],
                                 ["sampling_period", "sampling_distance_y", "number_points_y"])
        elif kind == "2D":
            check_special_fields(["sampling_distance_x", "number_points_x", "sampling_distance_y", "number_points_y"],
                                 ["sampling_period"])
        elif kind == "time-resolved":
            check_special_fields(["sampling_period", "sampling_distance_x"],
                                 ["number_points_x", "sampling_distance_y", "number_points_y"])
            try:
                sampling_period = cleaned_data["sampling_period"]
                accumulation = cleaned_data["accumulation"]
                time = cleaned_data["time"]
            except KeyError:
                pass
            else:
                if time * accumulation > sampling_period:
                    append_error(self, _("It must be: time × accumulation ≤ sampling period."), "sampling_period")
        return cleaned_data

    class Meta:
        exclude = ("external_operator",)
        widgets = {
            "kind": forms.RadioSelect(renderer=SimpleRadioSelectRenderer),
            }


class RamanMeasurementOneForm(RamanMeasurementForm):
    def __init__(self, user, sample, *args, **kwargs):
        super(RamanMeasurementOneForm, self).__init__(user, sample, institute_models.RamanMeasurementOne, *args, **kwargs)
    class Meta(RamanMeasurementForm.Meta):
        model = institute_models.RamanMeasurementOne


class RamanMeasurementTwoForm(RamanMeasurementForm):
    def __init__(self, user, sample, *args, **kwargs):
        super(RamanMeasurementTwoForm, self).__init__(user, sample, institute_models.RamanMeasurementTwo, *args, **kwargs)
    class Meta(RamanMeasurementForm.Meta):
        model = institute_models.RamanMeasurementTwo


class RamanMeasurementThreeForm(RamanMeasurementForm):
    def __init__(self, user, sample, *args, **kwargs):
        super(RamanMeasurementThreeForm, self).__init__(user, sample, institute_models.RamanMeasurementThree, *args, **kwargs)
    class Meta(RamanMeasurementForm.Meta):
        model = institute_models.RamanMeasurementThree


def is_all_valid(raman_measurement_form, sample_form, remove_from_my_samples_form, edit_description_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `raman_measurement_form`: a bound Raman measurement form
      - `sample_form`: a bound sample selection form
      - `overwrite_form`: a bound overwrite data form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form
      - `edit_description_form`: a bound edit-description form

    :type raman_measurement_form: `RamanMeasurementForm`
    :type sample_form: `SampleForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm`

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = raman_measurement_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid


def is_referentially_valid(raman_measurement_form, raman_model, sample_form, raman_number):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `raman_measurement_form`: a bound Raman measurement form
      - `raman_model`: the concrete Raman model class
      - `sample_form`: a bound sample selection form
      - `raman_number`: The Raman number of the Raman measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.

    :type raman_measurement_form: `RamanMeasurementForm`
    :type raman_model: ``class`` (subclass of `institute_models.RamanMeasurement`)
    :type sample_form: `SampleForm`
    :type raman_number: unicode

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    return form_utils.measurement_is_referentially_valid(raman_measurement_form, sample_form, raman_number, raman_model)


@login_required
def edit(request, apparatus_number, raman_number):
    """Edit and create view for Raman measurements.

    :Parameters:
      - `request`: the current HTTP Request object
      - `apparatus_number`: the number of the Raman apparatus; currently, it
        can be 1, 2, or 3
      - `raman_number`: The Raman number of the Raman measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.

    :type request: ``HttpRequest``
    :type apparatus_number: unicode
    :type raman_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    raman_model = {"1": institute_models.RamanMeasurementOne, "2": institute_models.RamanMeasurementTwo,
                   "3": institute_models.RamanMeasurementThree}[apparatus_number]
    form_class = {"1": RamanMeasurementOneForm, "2": RamanMeasurementTwoForm,
                  "3": RamanMeasurementThreeForm}[apparatus_number]
    raman_measurement = get_object_or_404(raman_model, number=utils.convert_id_to_int(raman_number)) \
        if raman_number is not None else None
    old_sample = raman_measurement.samples.get() if raman_measurement else None
    permissions.assert_can_add_edit_physical_process(request.user, raman_measurement, raman_model)
    preset_sample = utils.extract_preset_sample(request) if not raman_measurement else None
    if request.method == "POST":
        raman_measurement_form = None
        sample_form = SampleForm(request.user, raman_measurement, preset_sample, request.POST)
        sample = sample_form.is_valid() and sample_form.cleaned_data["sample"] or old_sample or preset_sample
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not raman_measurement else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if raman_measurement else None
        raman_measurement_form = form_class(request.user, sample, request.POST, instance=raman_measurement)
        all_valid = is_all_valid(raman_measurement_form, sample_form, remove_from_my_samples_form, edit_description_form)
        referentially_valid = is_referentially_valid(raman_measurement_form, raman_model, sample_form, raman_number)
        if all_valid and referentially_valid:
            raman_measurement = raman_measurement_form.save()
            samples = [sample_form.cleaned_data["sample"]]
            raman_measurement.samples = samples
            feed_utils.Reporter(request.user).report_physical_process(
                raman_measurement, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            success_report = _("{process} was successfully changed in the database.").format(process=raman_measurement) \
                if raman_number else \
                _("{process} was successfully added to the database.").format(process=raman_measurement)
            if raman_number:
                view = None
                kwargs = {}
            else:
                view = "add_raman_measurement"
                kwargs = {"apparatus_number": apparatus_number}
            return utils.successful_response(request, success_report, view, kwargs, json_response=raman_measurement.pk)
    else:
        initial = {}
        if raman_number is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
            if raman_model.objects.exists():
                latest = raman_model.objects.latest("number")
                initial["kind"] = latest.kind
                initial["slit"] = latest.slit
                initial["central_wavelength"] = latest.central_wavelength
                initial["excitation_wavelength"] = latest.excitation_wavelength
                initial["accumulation"] = latest.accumulation
                initial["time"] = latest.time
                initial["grating"] = latest.grating
                initial["laser_power"] = latest.laser_power
                initial["setup"] = latest.setup
                initial["detector"] = latest.detector
                initial["through_substrate"] = latest.through_substrate
                initial["objective"] = latest.objective
                initial["filters"] = latest.filters
                initial["sampling_distance_x"] = latest.sampling_distance_x
                initial["sampling_distance_y"] = latest.sampling_distance_y
                initial["number_points_x"] = latest.number_points_x
                initial["number_points_y"] = latest.number_points_y
                initial["sampling_period"] = latest.sampling_period
        raman_measurement_form = form_class(request.user, old_sample or preset_sample, instance=raman_measurement,
                                            initial=initial)
        initial = {}
        if old_sample:
            initial["sample"] = old_sample.pk
        sample_form = SampleForm(request.user, raman_measurement, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not raman_measurement else None
        edit_description_form = form_utils.EditDescriptionForm() if raman_measurement else None
    title = _("Edit Raman {apparatus_number} measurement of {sample}"). \
        format(apparatus_number=apparatus_number, sample=old_sample) if raman_measurement else \
        _("Add Raman {apparatus_number} measurement").format(apparatus_number=apparatus_number)
    return render_to_response("samples/edit_raman_measurement.html",
                              {"title": title, "raman_measurement": raman_measurement_form, "sample": sample_form,
                               "remove_from_my_samples": remove_from_my_samples_form,
                               "edit_description": edit_description_form,
                               "apparatus": apparatus_number},
                              context_instance=RequestContext(request))


@login_required
def show(request, apparatus_number, raman_number):
    """Show an existing Raman measurement.  You must be a Raman supervisor
    operator *or* be able to view one of the samples affected by this
    deposition in order to be allowed to view it.

    :Parameters:
      - `request`: the current HTTP Request object
      - `apparatus_number`: the number of the Raman apparatus; currently, it
        can be 1, 2, or 3
      - `deposition_number`: the number (=name) or the deposition

    :type request: ``HttpRequest``
    :type apparatus_number: unicode
    :type deposition_number: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    raman_model = {"1": institute_models.RamanMeasurementOne, "2": institute_models.RamanMeasurementTwo,
                   "3": institute_models.RamanMeasurementThree}[apparatus_number]
    raman_measurement = get_object_or_404(raman_model, number=utils.convert_id_to_int(raman_number))
    permissions.assert_can_view_physical_process(request.user, raman_measurement)
    if is_json_requested(request):
        return respond_in_json(raman_measurement.get_data().to_dict())
    template_context = {"title": _("Raman {apparatus_number} measurement #{raman_number}").format(
                                     apparatus_number=apparatus_number, raman_number=raman_number),
                        "samples": raman_measurement.samples.all(), "process": raman_measurement}
    template_context.update(utils.digest_process(raman_measurement, request.user))
    return render_to_response("samples/show_process.html", template_context, context_instance=RequestContext(request))
