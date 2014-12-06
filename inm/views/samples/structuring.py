#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


from __future__ import absolute_import, unicode_literals

import datetime
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from samples.views import utils
from inm.views import form_utils
import inm.models as institute_models


class StructuringForm(form_utils.ProcessForm):
    _ = ugettext_lazy
    combined_operator = form_utils.OperatorField(label=_("Operator"))

    def __init__(self, user, *args, **kwargs):
        """Form constructor.
        """
        super(StructuringForm, self).__init__(*args, **kwargs)
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

    def clean(self):
        cleaned_data = self.cleaned_data
        final_operator = cleaned_data.get("operator")
        final_external_operator = cleaned_data.get("external_operator")
        if cleaned_data.get("combined_operator"):
            operator, external_operator = cleaned_data["combined_operator"]
            if operator:
                if final_operator and final_operator != operator:
                    self.add_error("combined_operator", "Your operator and combined operator didn't match.")
                else:
                    final_operator = operator
            if external_operator:
                if final_external_operator and final_external_operator != external_operator:
                    self.add_error("combined_external_operator",
                                   "Your external operator and combined external operator didn't match.")
                else:
                    final_external_operator = external_operator
        if not final_operator:
            # Can only happen for non-staff.  I deliberately overwrite a
            # previous operator because this way, we can log who changed it.
            final_operator = self.user
        cleaned_data["operator"], cleaned_data["external_operator"] = final_operator, final_external_operator
        return cleaned_data

    class Meta:
        model = institute_models.Structuring
        exclude = ("external_operator",)

def is_all_valid(structuring_form, sample_form, remove_from_my_samples_form, edit_description_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `structuring_form`: a bound structuring form
      - `sample_form`: a bound sample selection form
      - `overwrite_form`: a bound overwrite data form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form
      - `edit_description_form`: a bound edit-description form

    :type structuring_form: `StructuringForm`
    :type sample_form: `SampleForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm`

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = structuring_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid

def is_referentially_valid(structuring_form, sample_form):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the structuring process.

    :Parameters:
      - `structuring_form`: a bound StructuringForm
      - `sample_form`: a bound sample selection form

    :type structuring_form: `StructuringForm`
    :type sample_form: `SampleForm`

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if structuring_form.is_valid():
        if sample_form.is_valid() and form_utils.dead_samples([sample_form.cleaned_data["sample"]],
                                                              structuring_form.cleaned_data["timestamp"]):
            structuring_form.add_error("timestamp", _("Sample is already dead at this time."))
            referentially_valid = False
    return referentially_valid

@login_required
def edit(request, process_id):
    """Edit and create view for structuring processes.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: The process id of the structuring form process to
        be edited.  If it is ``None``, a new structuring is added to the
        database.

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    structuring = get_object_or_404(institute_models.Structuring, id=process_id) \
        if process_id is not None else None
    preset_sample = utils.extract_preset_sample(request) if not structuring else None
    if request.method == "POST":
        structuring_form = StructuringForm(request.user, request.POST, instance=structuring)
        sample_form = form_utils.SampleForm(request.user, structuring, preset_sample, request.POST)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not structuring else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if structuring else None
        all_valid = is_all_valid(structuring_form, sample_form, remove_from_my_samples_form, edit_description_form)
        referentially_valid = is_referentially_valid(structuring_form, sample_form)
        if all_valid and referentially_valid:
            structuring = structuring_form.save(commit=False)
            structuring.operator = structuring_form.cleaned_data["operator"]
            structuring.save()
            samples = [sample_form.cleaned_data["sample"]]
            structuring.samples = samples
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            if process_id:
                return utils.successful_response(
                    request, _("Structuring process was successfully changed in the database."))
            else:
                return utils.successful_response(
                        request, _("Structuring process was successfully added to the database."),
                        forced=True, json_response=structuring.id)
    else:
        structuring_form = StructuringForm(request.user, instance=structuring)
        initial = {}
        if structuring:
            samples = structuring.samples.all()
            if samples:
                initial["sample"] = samples[0].pk
        sample_form = form_utils.SampleForm(request.user, structuring, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not structuring else None
        edit_description_form = form_utils.EditDescriptionForm() if structuring else None
    title = _("Edit structuring process") if process_id else _("Add structuring process")
    return render(request, "samples/edit_structuring.html", {"title": title,
                                                             "process": structuring_form,
                                                             "sample": sample_form,
                                                             "remove_from_my_samples": remove_from_my_samples_form,
                                                             "edit_description": edit_description_form})
