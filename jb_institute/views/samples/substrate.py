#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Views to add and edit substrates.
"""

from __future__ import unicode_literals
import datetime
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from jb_common.utils import append_error
from jb_institute import models as institute_models
from samples import permissions
from samples.views import utils, feed_utils, form_utils


class SubstrateForm(form_utils.ProcessForm):
    """Model form class for a substrate.
    """
    _ = ugettext_lazy
    combined_operator = form_utils.OperatorField(label=_("Operator"))

    class Meta:
        model = institute_models.Substrate
        fields = "__all__"

    def __init__(self, user, *args, **kwargs):
        super(SubstrateForm, self).__init__(*args, **kwargs)
        self.old_substrate = kwargs.get("instance")
        self.user = user
        self.fields["combined_operator"].set_choices(user, self.old_substrate)
        if not user.is_staff:
            self.fields["external_operator"].choices = []
            self.fields["operator"].choices = []
            self.fields["operator"].required = False
        else:
            self.fields["combined_operator"].required = False
        if self.old_substrate:
            if not user.is_staff:
                self.fields["timestamp"].widget.attrs["readonly"] = "readonly"
        self.fields["timestamp"].initial = datetime.datetime.now()

    def clean_timestamp(self):
        if not self.user.is_staff and self.old_substrate:
            return self.old_substrate.timestamp
        return self.cleaned_data["timestamp"]

    def clean_timestamp_inaccuracy(self):
        if not self.user.is_staff and self.old_substrate:
            return self.old_substrate.timestamp_inaccuracy
        return self.cleaned_data["timestamp_inaccuracy"]

    def clean(self):
        _ = ugettext
        cleaned_data = self.cleaned_data
        if cleaned_data.get("material") == "custom" and not cleaned_data.get("comments"):
            append_error(self, _("For a custom substrate, you must give substrate comments."), "comments")
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


def is_referentially_valid(substrate_form, samples_form, edit_description_form):
    """Test whether all forms are consistent with each other and with the
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
                    append_error(samples_form, _("Sample {0} has already processes before the timestamp of this substrate, "
                                                 "namely from {1}.").format(sample, earliest_timestamp), "sample_list")
                for process in processes:
                    if process.content_type.model_class() == institute_models.Substrate:
                        append_error(samples_form, _("Sample {0} has already a substrate.").format(sample), "sample_list")
                        referentially_valid = False
                        break
    return referentially_valid


@login_required
def edit(request, substrate_id):
    """Central view for editing and creating substrates.  If ``substrate_id``
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
    substrate = get_object_or_404(institute_models.Substrate, pk=utils.convert_id_to_int(substrate_id)) if substrate_id else None
    permissions.assert_can_add_edit_physical_process(request.user, substrate, institute_models.Substrate)
    preset_sample = utils.extract_preset_sample(request) if not substrate else None
    if request.method == "POST":
        substrate_form = SubstrateForm(request.user, request.POST, instance=substrate)
        samples_form = form_utils.DepositionSamplesForm(request.user, preset_sample, substrate, request.POST)
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if substrate else None
        referentially_valid = is_referentially_valid(substrate_form, samples_form, edit_description_form)
        if all([substrate_form.is_valid(), samples_form.is_valid() or not samples_form.is_bound,
                edit_description_form.is_valid() if edit_description_form else True]) and referentially_valid:
            new_substrate = substrate_form.save()
            if samples_form.is_bound:
                new_substrate.samples = samples_form.cleaned_data["sample_list"]
            feed_utils.Reporter(request.user).report_physical_process(
                new_substrate, edit_description_form.cleaned_data if edit_description_form else None)
            if substrate:
                # FixMe: Give the show-substrate function as the "view"
                # parameter once we have it.
                return utils.successful_response(
                    request, _("Substrate {0} was successfully changed in the database.").format(new_substrate))
            else:
                # FixMe: Give the show-substrate function as the "view"
                # parameter once we have it.
                return utils.successful_response(
                    request, _("Substrate {0} was successfully added to the database.").format(new_substrate),
                    json_response=new_substrate.pk)
    else:
        substrate_form = SubstrateForm(request.user, instance=substrate)
        samples_form = form_utils.DepositionSamplesForm(request.user, preset_sample, substrate)
        edit_description_form = form_utils.EditDescriptionForm() if substrate else None
    title = _("Edit substrate “{0}”").format(substrate) if substrate else _("Add substrate")
    return render_to_response("samples/edit_substrate.html", {"title": title, "substrate": substrate_form,
                                                              "samples": samples_form,
                                                              "edit_description": edit_description_form},
                              context_instance=RequestContext(request))
