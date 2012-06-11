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


"""After an etching process the sample gets the etching number as an alias name.
The sample retain their original names.
With the manual etching plant, only one sample can be etched at the same time.
"""

from __future__ import absolute_import, unicode_literals

import datetime, re, codecs
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
from django.db.models import Q
import django.contrib.auth.models
from chantal_common.utils import append_error
from samples.views import utils, feed_utils
from chantal_institute.views import form_utils
from samples import models, permissions
import chantal_institute.models as institute_models


class ManualEtchingForm(form_utils.ProcessForm):

    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, *args, **kwargs):
        super(ManualEtchingForm, self).__init__(*args, **kwargs)
        process = kwargs.get("instance")
        self.fields["operator"].set_operator(process.operator if process else user, user.is_staff)
        self.fields["operator"].initial = process.operator.pk if process else user.pk
        self.fields["number"].widget.attrs.update({"style": "font-size: large", "size": "12"})
        self.fields["acid_value_field"].initial = 0.5
        self.fields["temperature"].initial = 25
        self.fields["time"].initial = 40
        self.user = user
        self.edit = False
        if process:
            self.edit = True
        for field in ["acid_label_field", "acid_value_field", "temperature", "time", "resistance_before", "resistance_after",
                      "thickness_before", "thickness_after", "timestamp"]:
            self.fields[field].widget.attrs.update({"size": "15"})

    def clean_number(self):
        number = self.cleaned_data["number"]
        if number:
            if not re.match(datetime.date.today().strftime("%y") + r"X-\d{3,4}$", number):
                raise ValidationError(_("The etching number you have chosen isn't valid."))
            if institute_models.ManualEtching.objects.filter(number=number).exists() and not self.edit:
                raise ValidationError(_("The etching number you have chosen already exists."))
        return number

    def clean(self):
        cleaned_data = self.cleaned_data
        thickness_before = cleaned_data.get("thickness_before")
        thickness_after = cleaned_data.get("thickness_after")
        if thickness_before is not None and thickness_after is not None and thickness_after >= thickness_before:
            append_error(self, _("The thickness after the etching must be smaller then before the etching."), "thickness_after")
            del cleaned_data["thickness_after"]
        return cleaned_data

    def validate_unique(self):
        """Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `edit`.  I cannot use Django's built-in test anyway
        because it leads to an error message in wrong German (difficult to fix,
        even for the Django guys).
        """
        pass

    class Meta:
        model = institute_models.ManualEtching
        exclude = ("external_operator",)

class SplitAfterEtchingForm(forms.Form):
    """Form for the question whether the user wants to split the samples
    after the etching process.
    """
    _ = ugettext_lazy
    split_after_etching = forms.BooleanField(label=_("Split the sample after etching"),
                                                          required=False, initial=False)


def is_all_valid(manual_etching_form, sample_form, remove_from_my_samples_form, edit_description_form,
                 split_after_etching_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `manual_etching_form`: a bound etching process form
      - `sample_form`: a bound sample selection form
      - `overwrite_form`: a bound overwrite data form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form
      - `edit_description_form`: a bound edit-description form
      - `split_after_etching_form`: a bound split after etching form

    :type manual_etching_form: `ManualEtchingForm`
    :type sample_form: `SampleForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or
      ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm`
    :type split_after_etching_form: `SplitAfterEtchingForm` or
        ``NoneType``

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = manual_etching_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    if remove_from_my_samples_form:
        all_valid = remove_from_my_samples_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    if split_after_etching_form:
        all_valid = split_after_etching_form.is_valid() and all_valid
    return all_valid


def is_referentially_valid(manual_etching_form, sample_form, etching_number):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the etching process.

    :Parameters:
      - `manual_etching_form`: a bound manual etching form
      - `sample_form`: a bound sample selection form
      - `etching_number`: The etching number of the manual etching process to
        be edited.  If it is ``None``, a new etching process is added to the
        database.

    :type manual_etching_form: `ManualEtchingForm`
    :type sample_form: `SampleForm`
    :type etching_number: unicode

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if manual_etching_form.is_valid():
        number = manual_etching_form.cleaned_data["number"]
        if unicode(number) != etching_number and institute_models.ManualEtching.objects.filter(number=number).count():
            append_error(manual_etching_form, _("This etching number is already in use."))
            referentially_valid = False
        if sample_form.is_valid() and form_utils.dead_samples([sample_form.cleaned_data["sample"]],
                                                              manual_etching_form.cleaned_data["timestamp"]):
            append_error(manual_etching_form, _("Sample is already dead at this time."), "timestamp")
            referentially_valid = False
    return referentially_valid


@login_required
def edit(request, etching_number):
    """Edit and create view for manual etching processes.

    :Parameters:
      - `request`: the current HTTP Request object
      - `etching_number`: The etching number of the manual etching process to
        be edited.  If it is ``None``, a new measurement is added to the
        database.

    :type request: ``HttpRequest``
    :type etching_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    manual_etching = get_object_or_404(institute_models.ManualEtching, number=etching_number) \
        if etching_number is not None else None
    permissions.assert_can_add_edit_physical_process(request.user, manual_etching, institute_models.ManualEtching)
    preset_sample = utils.extract_preset_sample(request) if not manual_etching else None
    if request.method == "POST":
        manual_etching_form = None
        sample_form = form_utils.SampleForm(request.user, manual_etching, preset_sample, request.POST)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(request.POST) if not manual_etching else None
        split_after_etching_form = SplitAfterEtchingForm(request.POST) if not manual_etching else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if manual_etching else None
        if manual_etching_form is None:
            manual_etching_form = ManualEtchingForm(request.user, request.POST, instance=manual_etching)
        all_valid = is_all_valid(manual_etching_form, sample_form, remove_from_my_samples_form,
                                 edit_description_form, split_after_etching_form)
        referentially_valid = is_referentially_valid(manual_etching_form, sample_form, etching_number)
        if all_valid and referentially_valid:
            manual_etching = manual_etching_form.save()
            samples = [sample_form.cleaned_data["sample"]]
            manual_etching.samples = samples
            feed_utils.Reporter(request.user).report_physical_process(
                manual_etching, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, request.user)
            if etching_number:
                return utils.successful_response(
                    request, _("Etching process {number} was successfully changed in the database."). \
                        format(number=manual_etching.number))
            else:
                models.SampleAlias(name=manual_etching.number, sample=samples[0]).save()
                samples[0].save()
                if split_after_etching_form and split_after_etching_form.cleaned_data["split_after_etching"]:
                    return utils.successful_response(
                        request, _("Etching process {number} was successfully added to the database."). \
                            format(number=manual_etching.number), "samples.views.split_and_rename.split_and_rename",
                        {"parent_name": manual_etching.number}, forced=True, json_response=manual_etching.number)
                else:
                    return utils.successful_response(
                        request, _("Etching process {number} was successfully added to the database."). \
                            format(number=manual_etching.number), forced=True, json_response=manual_etching.number)
    else:
        initial = {}
        if etching_number is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
            try:
                number = institute_models.ManualEtching.objects.latest('number').number
                initial["number"] = "{0}{1:04}".format(number[:4], int(number[4:]) + 1)
            except:
                initial["number"] = datetime.date.today().strftime("%y") + "X-0001"
        manual_etching_form = ManualEtchingForm(request.user, instance=manual_etching, initial=initial)
        initial = {}
        if manual_etching:
            samples = manual_etching.samples.all()
            if samples:
                initial["sample"] = samples[0].pk
        sample_form = form_utils.SampleForm(request.user, manual_etching, preset_sample, initial=initial)
        remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not manual_etching else None
        split_after_etching_form = SplitAfterEtchingForm() if not manual_etching else None
        edit_description_form = form_utils.EditDescriptionForm() if manual_etching else None
    title = _("Manual etching #{number}").format(number=etching_number) \
        if etching_number else _("Add manual etching")
    return render_to_response("samples/edit_manual_etching.html", {"title": title,
                                                                   "process": manual_etching_form,
                                                                   "sample": sample_form,
                                                                   "remove_from_my_samples": remove_from_my_samples_form,
                                                                   "edit_description": edit_description_form,
                                                                   "split_after_etching": split_after_etching_form},
                              context_instance=RequestContext(request))
