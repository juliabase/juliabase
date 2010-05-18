#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views to add and edit substrates.  Practically, they are only used by the
remote client.
"""

import re, datetime
from django import forms
from django.forms.util import ValidationError
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.template import RequestContext
from chantal_common.utils import append_error
from samples import models, permissions
from samples.views import utils, feed_utils, form_utils


class SubstrateForm(form_utils.ProcessForm):
    u"""Model form class for a substrate.
    """
    _ = ugettext_lazy
    operator = form_utils.OperatorField(label=_(u"Operator"))

    class Meta:
        model = models.Substrate

    def __init__(self, user, *args, **kwargs):
        super(SubstrateForm, self).__init__(*args, **kwargs)
        self.old_substrate = kwargs.get("instance")
        self.user = user
        self.fields["operator"].set_choices(user, self.old_substrate)
        if not user.is_staff:
            self.fields["external_operator"].choices = []
        self.can_clean_substrates = user.has_perm("samples.clean_substrate")
        if not self.can_clean_substrates:
            self.fields["cleaning_number"].widget.attrs["readonly"] = "readonly"
        if self.old_substrate:
            if not user.is_staff:
                self.fields["timestamp"].widget.attrs["readonly"] = "readonly"
                self.fields["timestamp_inaccuracy"].widget.attrs["disabled"] = "disabled"
                self.fields["timestamp_inaccuracy"].required = False
                self.fields["operator"].widget.attrs["disabled"] = "disabled"
                self.fields["operator"].required = False
                self.fields["external_operator"].widget.attrs["disabled"] = "disabled"
            self.fields["cleaning_number"].widget.attrs["readonly"] = "readonly"
        self.fields["timestamp"].initial = datetime.datetime.now()

    def clean_timestamp(self):
        timestamp = super(SubstrateForm, self).clean_timestamp()
        if not self.user.is_staff and self.old_substrate and self.old_substrate.timestamp != timestamp:
            raise ValidationError(u"You must be admin to change the timestamp of an existing substrate.")
        return timestamp

    def clean_timestamp_inaccuracy(self):
        timestamp_inaccuracy = self.cleaned_data["timestamp_inaccuracy"]
        if not self.user.is_staff and self.old_substrate and \
                self.old_substrate.timestamp_inaccuracy != timestamp_inaccuracy:
            raise ValidationError(u"You must be admin to change the timestamp inaccuracy of an existing substrate.")
        return timestamp_inaccuracy

    def clean_cleaning_number(self):
        cleaning_number = self.cleaned_data["cleaning_number"]
        if self.old_substrate and self.old_substrate.cleaning_number != cleaning_number:
            raise ValidationError(u"You can't change the cleaning number of an existing substrate.")
        if not self.old_substrate and cleaning_number:
            if not self.can_clean_substrates:
                # Not translatable because can't happen with unmodified browser
                raise ValidationError(u"You don't have the permission to give cleaning numbers.")
            if not re.match(datetime.date.today().strftime("%y") + r"N-\d{3,4}$", cleaning_number):
                raise ValidationError(_(u"The cleaning number you have chosen isn't valid."))
            if models.Substrate.objects.filter(cleaning_number=cleaning_number).exists():
                raise ValidationError(_(u"The cleaning number you have chosen already exists."))
        return cleaning_number

    def clean(self):
        _ = ugettext
        cleaned_data = self.cleaned_data
        if cleaned_data.get("material") == "custom" and not cleaned_data.get("comments"):
            append_error(self, _(u"For a custom substrate, you must give substrate comments."), "comments")
        # FixMe: The following could be done in ProcessForm.clean().
        if self.cleaned_data.get("external_operator"):
            if not self.user.is_staff:
                append_error(self, u"Only an admin may submit an external operator")
                del self.cleaned_data["external_operator"]
        else:
            self.cleaned_data["external_operator"] = self.fields["operator"].external_operator
        return cleaned_data


def is_referentially_valid(substrate_form, samples_form, edit_description_form):
    u"""Test whether all forms are consistent with each other and with the
    database.  For example, no sample must get more than one substrate.

    :Parameters:
      - `substrate_form`: form with the substrate core data
      - `samples_form`: form with the sample selection
      - `edit_description_form`: form with the description of the changes

    :type substrate_form: `SubstrateForm`
    :type samples_form: `form_utils.DepositionSamplesForm`
    :type edit_description_form: `form_utils.EditDescriptionForm` or
        ``NoneType``

    :Return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if samples_form.is_valid() and substrate_form.is_valid() and samples_form.is_bound:
        for sample in samples_form.cleaned_data["sample_list"]:
            processes = list(sample.processes.all())
            if processes:
                earliest_timestamp = min(process.timestamp for process in processes)
                if earliest_timestamp < substrate_form.cleaned_data["timestamp"]:
                    append_error(samples_form, _(u"Sample {0} has already processes before the timestamp of this substrate, "
                                                 u"namely from {1}.").format(sample, earliest_timestamp), "sample_list")
                for process in processes:
                    if isinstance(process.find_actual_instance(), models.Substrate):
                        append_error(samples_form, _(u"Sample {0} has already a substrate.").format(sample), "sample_list")
                        referencially_valid = False
                        break
    return referentially_valid


def edit(request, substrate_id):
    u"""Central view for editing and creating substrates.  If ``substrate_id``
    is ``None``, a new substrate is created.

    :Parameters:
      - `request`: the HTTP request object
      - `substrate_id`: the id of the subtrate

    :type request: ``QueryDict``
    :type deposition_number: unicode or ``NoneType``

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    substrate = get_object_or_404(models.Substrate, pk=utils.int_or_zero(substrate_id)) if substrate_id else None
    permissions.assert_can_add_edit_physical_process(request.user, substrate, models.Substrate)
    user_details = utils.get_profile(request.user)
    preset_sample = utils.extract_preset_sample(request) if not substrate else None
    if request.method == "POST":
        substrate_form = SubstrateForm(request.user, request.POST, instance=substrate)
        samples_form = form_utils.DepositionSamplesForm(user_details, preset_sample, substrate, request.POST)
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if substrate else None
        referentially_valid = is_referentially_valid(substrate_form, samples_form, edit_description_form)
        if all([substrate_form.is_valid(), samples_form.is_valid() or not samples_form.is_bound,
                edit_description_form.is_valid() if edit_description_form else True]) and referentially_valid:
            new_substrate = substrate_form.save(commit=False)
            cleaned_data = substrate_form.cleaned_data
            if isinstance(cleaned_data["operator"], models.ExternalOperator):
                new_substrate.external_operator = cleaned_data["operator"]
                new_substrate.operator = substrate.operator if substrate else request.user
            else:
                new_substrate.external_operator = None
            new_substrate.save()
            if samples_form.is_bound:
                new_substrate.samples = samples_form.cleaned_data["sample_list"]
            feed_utils.Reporter(request.user).report_physical_process(
                new_substrate, edit_description_form.cleaned_data if edit_description_form else None)
            if substrate:
                return utils.successful_response(
                    request, _(u"Substrate {0} was successfully changed in the database.").format(new_substrate),
                    new_substrate.get_absolute_url())
            else:
                return utils.successful_response(
                    request, _(u"Substrate {0} was successfully added to the database.").format(new_substrate),
                    new_substrate.get_absolute_url(), remote_client_response=new_substrate.pk)
    else:
        substrate_form = SubstrateForm(request.user, instance=substrate)
        samples_form = form_utils.DepositionSamplesForm(user_details, preset_sample, substrate)
        edit_description_form = form_utils.EditDescriptionForm() if substrate else None
    title = _(u"Edit substrate “{0}”").format(substrate) if substrate else _(u"Add substrate")
    return render_to_response("samples/edit_substrate.html", {"title": title, "substrate": substrate_form,
                                                              "samples": samples_form,
                                                              "edit_description": edit_description_form},
                              context_instance=RequestContext(request))
