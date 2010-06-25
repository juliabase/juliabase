#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views to add and edit cleaning processes.
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


class CleaningProcessForm(form_utils.ProcessForm):
    u"""Model form class for a cleaning process.
    """
    _ = ugettext_lazy
    operator = form_utils.OperatorField(label=_(u"Operator"))

    class Meta:
        model = models.CleaningProcess

    def __init__(self, user, *args, **kwargs):
        super(CleaningProcessForm, self).__init__(*args, **kwargs)
        self.old_cleaningprocess = kwargs.get("instance")
        self.user = user
        self.fields["operator"].set_choices(user, self.old_cleaningprocess)
        if not user.is_staff:
            self.fields["external_operator"].choices = []
        self.can_clean_substrates = user.has_perm("samples.clean_substrate")
        if not self.can_clean_substrates:
            self.fields["cleaning_number"].widget.attrs["readonly"] = "readonly"
        if self.old_cleaningprocess:
            if not user.is_staff:
                self.fields["timestamp"].widget.attrs["readonly"] = "readonly"
                self.fields["timestamp_inaccuracy"].widget.attrs["disabled"] = "disabled"
                self.fields["timestamp_inaccuracy"].required = False
                self.fields["operator"].widget.attrs["disabled"] = "disabled"
                self.fields["operator"].required = False
                self.fields["external_operator"].widget.attrs["disabled"] = "disabled"
            self.fields["cleaning_number"].widget.attrs["readonly"] = "readonly"
        self.fields["timestamp"].initial = datetime.datetime.now()

    def clean_cleaning_number(self):
        cleaning_number = self.cleaned_data["cleaning_number"]
        if self.old_cleaningprocess and self.old_cleaningprocess.cleaning_number != cleaning_number:
            raise ValidationError(u"You can't change the cleaning number of an existing cleaning process.")
        if not self.old_cleaningprocess and cleaning_number:
            if not self.can_clean_substrates:
                # Not translatable because can't happen with unmodified browser
                raise ValidationError(u"You don't have the permission to give cleaning numbers.")
            if not re.match(datetime.date.today().strftime("%y") + r"N-\d{3,4}$", cleaning_number):
                raise ValidationError(_(u"The cleaning number you have chosen isn't valid."))
            if models.CleaningProcess.objects.filter(cleaning_number=cleaning_number).exists():
                raise ValidationError(_(u"The cleaning number you have chosen already exists."))
        return cleaning_number

    def clean(self):
        _ = ugettext
        cleaned_data = self.cleaned_data
        # FixMe: The following could be done in ProcessForm.clean().
        if self.cleaned_data.get("external_operator"):
            if not self.user.is_staff:
                append_error(self, u"Only an admin may submit an external operator")
                del self.cleaned_data["external_operator"]
        else:
            self.cleaned_data["external_operator"] = self.fields["operator"].external_operator
        return cleaned_data


def is_referentially_valid(cleaning_process_form, samples_form, edit_description_form):
    u"""Test whether all forms are consistent with each other and with the
    database.  For example, no sample must get more than one cleaning process.

    :Parameters:
      - `cleaning_process_form`: form with the cleaning_process core data
      - `samples_form`: form with the sample selection
      - `edit_description_form`: form with the description of the changes

    :type cleaning_process_form: `CleaningProcessForm`
    :type samples_form: `form_utils.DepositionSamplesForm`
    :type edit_description_form: `form_utils.EditDescriptionForm` or
        ``NoneType``

    :Return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    if samples_form.is_valid() and cleaning_process_form.is_valid() and samples_form.is_bound:
        if edit_description_form:
            return edit_description_form.is_valid()
        else:
            return True
    return False


def edit(request, cleaning_process_id):
    u"""Central view for editing and creating cleaning processes.  If ``cleaning_process_id``
    is ``None``, a new cleaning process is created.

    :Parameters:
      - `request`: the HTTP request object
      - `cleaning_process_id`: the id of the subtrate

    :type request: ``QueryDict``
    :type deposition_number: unicode or ``NoneType``

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    cleaning_process = get_object_or_404(models.CleaningProcess, pk=utils.int_or_zero(cleaning_process_id)) if cleaning_process_id else None
    permissions.assert_can_add_edit_physical_process(request.user, cleaning_process, models.CleaningProcess)
    user_details = utils.get_profile(request.user)
    preset_sample = utils.extract_preset_sample(request) if not cleaning_process else None
    if request.method == "POST":
        cleaning_process_form = CleaningProcessForm(request.user, request.POST, instance=cleaning_process)
        samples_form = form_utils.DepositionSamplesForm(user_details, preset_sample, cleaning_process, request.POST)
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if cleaning_process else None
        referentially_valid = is_referentially_valid(cleaning_process_form, samples_form, edit_description_form)
        if all([cleaning_process_form.is_valid(), samples_form.is_valid() or not samples_form.is_bound,
                edit_description_form.is_valid() if edit_description_form else True]) and referentially_valid:
            new_cleaning_process = cleaning_process_form.save(commit=False)
            cleaned_data = cleaning_process_form.cleaned_data
            if isinstance(cleaned_data["operator"], models.ExternalOperator):
                new_cleaning_process.external_operator = cleaned_data["operator"]
                new_cleaning_process.operator = cleaning_process.operator if cleaning_process else request.user
            else:
                new_cleaning_process.external_operator = None
            new_cleaning_process.save()
            if samples_form.is_bound:
                new_cleaning_process.samples = samples_form.cleaned_data["sample_list"]
            feed_utils.Reporter(request.user).report_physical_process(
                new_cleaning_process, edit_description_form.cleaned_data if edit_description_form else None)
            if cleaning_process:
                return utils.successful_response(
                    request, _(u"Cleaning process {0} was successfully changed in the database.").format(new_cleaning_process),
                    new_cleaning_process.get_absolute_url())
            else:
                return utils.successful_response(
                    request, _(u"Cleaning process {0} was successfully added to the database.").format(new_cleaning_process),
                    new_cleaning_process.get_absolute_url(), remote_client_response=new_cleaning_process.pk)
    else:
        cleaning_process_form = CleaningProcessForm(request.user, instance=cleaning_process)
        samples_form = form_utils.DepositionSamplesForm(user_details, preset_sample, cleaning_process)
        edit_description_form = form_utils.EditDescriptionForm() if cleaning_process else None
    title = _(u"Edit cleaning process “{0}”").format(cleaning_process) if cleaning_process else _(u"Add cleaning process")
    return render_to_response("samples/edit_cleaning_process.html", {"title": title,
                                                                     "cleaning_process": cleaning_process_form,
                                                                     "samples": samples_form,
                                                                     "edit_description": edit_description_form},
                              context_instance=RequestContext(request))
