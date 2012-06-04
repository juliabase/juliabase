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


"""Views to add and edit large area cleaning processes.
"""

from __future__ import unicode_literals
import re, datetime
from django import forms
from django.forms.util import ValidationError
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.template import RequestContext
from chantal_common.utils import append_error
from samples import models, permissions
from chantal_ipv import models as ipv_models
from samples.views import utils, feed_utils, form_utils


class CleaningProcessForm(form_utils.ProcessForm):
    """Model form class for a cleaning process.
    """
    _ = ugettext_lazy
    combined_operator = form_utils.OperatorField(label=_("Operator"))

    class Meta:
        model = ipv_models.LargeAreaCleaningProcess

    def __init__(self, user, *args, **kwargs):
        super(CleaningProcessForm, self).__init__(*args, **kwargs)
        self.old_cleaningprocess = kwargs.get("instance")
        self.user = user
        self.fields["combined_operator"].set_choices(user, self.old_cleaningprocess)
        if not user.is_staff:
            self.fields["external_operator"].choices = []
            self.fields["operator"].choices = []
            self.fields["operator"].required = False
        else:
            self.fields["combined_operator"].required = False
        if self.old_cleaningprocess:
            if not user.is_staff:
                self.fields["timestamp"].widget.attrs["readonly"] = "readonly"
            self.fields["cleaning_number"].widget.attrs["readonly"] = "readonly"
        self.fields["timestamp"].initial = datetime.datetime.now()
        current_year = datetime.date.today().strftime("%y")
        old_cleaning_numbers = list(ipv_models.LargeAreaCleaningProcess.objects.filter(cleaning_number__startswith=current_year).
                                        values_list("cleaning_number", flat=True))
        next_cleaning_number = max(int(cleaning_number[4:]) for cleaning_number in old_cleaning_numbers) + 1 \
        if old_cleaning_numbers else 1
        self.fields["cleaning_number"].initial = "{0}Y-{1:03}".format(current_year, next_cleaning_number)
        self.fields["cleaning_number"].widget.attrs.update({"style": "font-size: large", "size": "8"})
        for fieldname in ["temperature_start", "temperature_end", "time", "resistance", "conductance_value_1", "conductance_value_2"]:
            self.fields[fieldname].widget.attrs["size"] = "10"

    def clean_timestamp(self):
        if not self.user.is_staff and self.old_cleaningprocess:
            return self.old_cleaningprocess.timestamp
        return self.cleaned_data["timestamp"]

    def clean_timestamp_inaccuracy(self):
        if not self.user.is_staff and self.old_cleaningprocess:
            return self.old_cleaningprocess.timestamp_inaccuracy
        return self.cleaned_data["timestamp_inaccuracy"]

    def clean_cleaning_number(self):
        if self.old_cleaningprocess:
            return self.old_cleaningprocess.cleaning_number
        cleaning_number = self.cleaned_data["cleaning_number"]
        if not self.old_cleaningprocess and cleaning_number:
            if not re.match(r"\d\dY-\d{3,4}$", cleaning_number):
                raise ValidationError(_("The cleaning number you have chosen isn't valid."))
            if ipv_models.LargeAreaCleaningProcess.objects.filter(cleaning_number=cleaning_number).exists():
                raise ValidationError(_("The cleaning number you have chosen already exists."))
        return cleaning_number

    def clean(self):
        _ = ugettext
        cleaned_data = self.cleaned_data
        if "cleaning_number" in cleaned_data and "timestamp" in cleaned_data:
            if cleaned_data["cleaning_number"][:2] != cleaned_data["timestamp"].strftime("%y"):
                append_error(self, _("The first two digits must match the year of the cleaning."), "cleaning_number")
                del cleaned_data["cleaning_number"]
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
        return cleaned_data


class SamplesForm(forms.Form):
    """Form for the list selection of samples.  Note that samples are
    optional, which is unique to cleaning processes.
    """
    _ = ugettext_lazy
    sample_list = form_utils.MultipleSamplesField(label=_("Samples"), required=False)

    def __init__(self, user, preset_sample, cleaning_process, data=None, **kwargs):
        """Class constructor.
        """
        samples = list(user.my_samples.all())
        if cleaning_process:
            kwargs["initial"] = {"sample_list": cleaning_process.samples.values_list("pk", flat=True)}
            samples.extend(cleaning_process.samples.all())
            super(SamplesForm, self).__init__(data, **kwargs)
        else:
            super(SamplesForm, self).__init__(data, **kwargs)
            self.fields["sample_list"].initial = []
            if preset_sample:
                samples.append(preset_sample)
                self.fields["sample_list"].initial.append(preset_sample.pk)
        self.fields["sample_list"].set_samples(samples, user)
        self.fields["sample_list"].widget.attrs.update({"size": "15", "style": "vertical-align: top"})


def edit(request, large_area_cleaning_process_id):
    """Central view for editing and creating large area cleaning processes.  If
    ``large_area_cleaning_process_id`` is ``None``, a new large area cleaning process is created.

    :Parameters:
      - `request`: the HTTP request object
      - `large_area_cleaning_process_id`: the id of the substrate

    :type request: ``QueryDict``
    :type large_area_cleaning_process_id: unicode or ``NoneType``

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    cleaning_process = get_object_or_404(ipv_models.LargeAreaCleaningProcess, pk=utils.convert_id_to_int(large_area_cleaning_process_id)) \
        if large_area_cleaning_process_id else None
    permissions.assert_can_add_edit_physical_process(request.user, cleaning_process, ipv_models.LargeAreaCleaningProcess)
    preset_sample = utils.extract_preset_sample(request) if not cleaning_process else None
    if request.method == "POST":
        cleaning_process_form = CleaningProcessForm(request.user, request.POST, instance=cleaning_process)
        samples_form = SamplesForm(request.user, preset_sample, cleaning_process, request.POST)
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if cleaning_process else None
        if all([cleaning_process_form.is_valid(), samples_form.is_valid() or not samples_form.is_bound,
                edit_description_form.is_valid() if edit_description_form else True]):
            new_cleaning_process = cleaning_process_form.save(commit=False)
            cleaned_data = cleaning_process_form.cleaned_data
            if isinstance(cleaned_data["operator"], models.ExternalOperator):
                new_cleaning_process.external_operator = cleaned_data["operator"]
                new_cleaning_process.operator = cleaning_process.operator if cleaning_process else request.user
            else:
                new_cleaning_process.external_operator = None
            new_cleaning_process.save()
            if not cleaning_process:
                if samples_form.is_bound:
                    samples = samples_form.cleaned_data["sample_list"]
                    if len(samples) == 1:
                        samples[0].name = new_cleaning_process.cleaning_number
                        models.SampleAlias(name=samples[0].name, sample=samples[0]).save()
                        samples[0].save()
                    else:
                        suffix = 1
                        for sample in samples:
                            sample.name = "{0}-{1:02}".format(new_cleaning_process.cleaning_number, suffix)
                            models.SampleAlias(name=new_cleaning_process.cleaning_number, sample=sample).save()
                            sample.save()
                            suffix += 1
                    new_cleaning_process.samples = samples
            feed_utils.Reporter(request.user).report_physical_process(
                new_cleaning_process, edit_description_form.cleaned_data if edit_description_form else None)
            if cleaning_process:
                return utils.successful_response(
                    request, _("Large area cleaning process {name} was successfully changed in the database."). \
                        format(name=new_cleaning_process),
                    new_cleaning_process.get_absolute_url())
            else:
                return utils.successful_response(
                    request, _("Large area cleaning process {name} was successfully added to the database."). \
                        format(name=new_cleaning_process), json_response=new_cleaning_process.pk)
    else:
        cleaning_process_form = CleaningProcessForm(request.user, instance=cleaning_process)
        samples_form = SamplesForm(request.user, preset_sample, cleaning_process)
        edit_description_form = form_utils.EditDescriptionForm() if cleaning_process else None
    title = _("Edit large area cleaning process “{name}”").format(name=cleaning_process) if cleaning_process \
        else _("Add large area cleaning process")
    return render_to_response("samples/edit_large_area_cleaning_process.html", {"title": title,
                                                                     "cleaning_process": cleaning_process_form,
                                                                     "samples": samples_form,
                                                                     "edit_description": edit_description_form},
                              context_instance=RequestContext(request))
