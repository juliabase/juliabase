#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


"""A views and helper routines for adding new samples.  I must override the
default view for adding samples in JuliaBase-samples because I wanto to have a
substrate with every sample, too (and possibly a cleaning process).
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six

import datetime
from django.db import transaction, IntegrityError
from django.shortcuts import render, get_object_or_404
import django.forms as forms
from django.forms.util import ValidationError
from django.forms import widgets
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.utils.translation import ugettext, ugettext_lazy as _
from django.contrib.auth.decorators import login_required
import django.core.urlresolvers
from jb_common.utils.base import help_link, get_really_full_name, int_or_zero
from jb_common.utils.views import TopicField
from samples import models, permissions
import samples.utils.views as utils
from institute import models as institute_models
from institute import printer_labels


class SimpleRadioSelectRenderer(widgets.RadioFieldRenderer):
    def render(self):
        return mark_safe("""<ul class="radio-select">\n{0}\n</ul>""".format("\n".join(
                    """<li style="white-space: nowrap">{0}</li>""".format(force_text(w)) for w in self)))


rename_choices = (("", _("no names")),
                    # Translators: "new-style" names
                ("new-style", _("new-style")),
                ("cleaning", _("cleaning number")))

class AddSamplesForm(forms.Form):
    """Form for adding new samples."""
    # FixMe: Although this form can never represent *one* sample but allows the
    # user to add arbitrary samples with the same properties (except for the
    # name of course), this should be converted to a *model* form in order to
    # satisfy the dont-repeat-yourself principle.
    #
    # Besides, we have massive code duplication to substrate.SubstrateForm.
    number_of_samples = forms.IntegerField(label=_("Number of samples"), min_value=1, max_value=100)
    substrate = forms.ChoiceField(label=_("Substrate"), choices=institute_models.substrate_materials, required=True)
    substrate_comments = forms.CharField(label=_("Substrate comments"), required=False)
    substrate_originator = forms.ChoiceField(label=_("Substrate originator"), required=False)
    timestamp = forms.DateTimeField(label=_("timestamp"))
    timestamp_inaccuracy = forms.IntegerField(required=False)
    current_location = forms.CharField(label=_("Current location"), max_length=50)
    purpose = forms.CharField(label=_("Purpose"), max_length=80, required=False)
    tags = forms.CharField(label=_("Tags"), max_length=255, required=False,
                           help_text=_("separated with commas, no whitespace"))
    topic = TopicField(label=_("Topic"), required=False)
    rename = forms.ChoiceField(label=_("Rename"), choices=rename_choices, required=False,
                               widget=forms.RadioSelect(renderer=SimpleRadioSelectRenderer))
    cleaning_number = forms.CharField(label=_("Cleaning number"), max_length=8, required=False)

    def __init__(self, user, data=None, **kwargs):
        super(AddSamplesForm, self).__init__(data, **kwargs)
        self.fields["timestamp"].initial = datetime.datetime.now()
        self.fields["topic"].set_topics(user)
        self.fields["substrate_comments"].help_text = \
            """<span class="markdown-hint">""" + _("""with {markdown_link} syntax""").format(
            markdown_link="""<a href="{0}">Markdown</a>""".format(
                    django.core.urlresolvers.reverse("jb_common.views.markdown_sandbox"))) + "</span>"
        self.fields["substrate_originator"].choices = [("<>", get_really_full_name(user))]
        external_contacts = user.external_contacts.all()
        if external_contacts:
            for external_operator in external_contacts:
                self.fields["substrate_originator"].choices.append((external_operator.pk, external_operator.name))
            self.fields["substrate_originator"].required = True
        self.user = user

    def clean_timestamp(self):
        """Forbid timestamps that are in the future.
        """
        timestamp = self.cleaned_data["timestamp"]
        if timestamp > datetime.datetime.now():
            raise ValidationError(_("The timestamp must not be in the future."))
        return timestamp

    def clean_substrate_originator(self):
        """Return the cleaned substrate originator.  Note that something is
        returned only if it is an external operator.
        """
        key = self.cleaned_data["substrate_originator"]
        if not key or key == "<>":
            return None
        return models.ExternalOperator.objects.get(pk=int(key))

    def clean(self):
        cleaned_data = super(AddSamplesForm, self).clean()
        if cleaned_data["substrate"] == "custom" and not cleaned_data.get("substrate_comments"):
            self.add_error("substrate_comments", _("For a custom substrate, you must give substrate comments."))
        if cleaned_data.get("rename") == "cleaning" and not cleaned_data.get("cleaning_number"):
            self.add_error("cleaning_number", _("You must provide a cleaning number if you want to use it for the names."))
        return cleaned_data


def add_samples_to_database(add_samples_form, user):
    """Create the new samples and add them to the database.  This routine consists
    of two parts: First, it tries to find a consecutive block of provisional
    sample names.  Then, in actuall creates the samples.

    :param add_samples_form: the form with the samples' common data, including
        the substrate
    :param user: the current user

    :type add_samples_form: `AddSamplesForm`
    :type user: django.contrib.auth.models.User

    :return:
      the names of the new samples

    :rtype: list of unicode
    """
    cleaned_data = add_samples_form.cleaned_data
    cleaning_number = cleaned_data.get("cleaning_number")
    substrate = institute_models.Substrate.objects.create(operator=user, timestamp=cleaned_data["timestamp"],
                                                    material=cleaned_data["substrate"],
                                                    comments=cleaned_data["substrate_comments"],
                                                    external_operator=cleaned_data["substrate_originator"])
    inaccuracy = cleaned_data["timestamp_inaccuracy"]
    if inaccuracy:
        substrate.timestamp_inaccuracy = inaccuracy
        substrate.save()
    provisional_sample_names = \
        models.Sample.objects.filter(name__startswith="*").values_list("name", flat=True)
    occupied_provisional_numbers = [int(name[1:]) for name in provisional_sample_names]
    occupied_provisional_numbers.sort()
    occupied_provisional_numbers.insert(0, 0)
    number_of_samples = cleaned_data["number_of_samples"]
    if add_samples_form.cleaned_data.get("rename") == "cleaning":
        subnumbers = [int_or_zero(name.rpartition("-")[2]) for name in
                      models.Sample.objects.filter(name__startswith=cleaning_number).values_list("name", flat=True)]
        starting_number = max(subnumbers) + 1 if subnumbers else 1
        names = [cleaning_number + "-{0:02}".format(i) for i in range(starting_number, starting_number + number_of_samples)]
    else:
        for i in range(len(occupied_provisional_numbers) - 1):
            if occupied_provisional_numbers[i + 1] - occupied_provisional_numbers[i] - 1 >= number_of_samples:
                starting_number = occupied_provisional_numbers[i] + 1
                break
        else:
            starting_number = occupied_provisional_numbers[-1] + 1
        names = ["*{0:05}".format(i) for i in range(starting_number, starting_number + number_of_samples)]
    new_names = []
    samples = []
    current_location, purpose, tags, topic = cleaned_data["current_location"], cleaned_data["purpose"], \
        cleaned_data["tags"], cleaned_data["topic"]
    for new_name in names:
        sample = models.Sample.objects.create(name=new_name, current_location=current_location,
                                              currently_responsible_person=user, purpose=purpose, tags=tags, topic=topic)
        samples.append(sample)
        sample.processes.add(substrate)
        if cleaning_number:
            models.SampleAlias.objects.create(name=cleaning_number, sample=sample)
        sample.watchers.add(user)
        if topic:
            for watcher in (user_details.user for user_details in topic.auto_adders.all()):
                watcher.my_samples.add(sample)
        new_names.append(six.text_type(sample))
    return new_names, samples


@help_link("demo.html#add-samples")
@login_required
def add(request):
    """View for adding new samples.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    user = request.user
    if request.method == "POST":
        add_samples_form = AddSamplesForm(user, request.POST)
        if add_samples_form.is_valid():
            # FixMe: Find more reliable way to find stared sample names
            max_cycles = 10
            while max_cycles > 0:
                max_cycles -= 1
                try:
                    savepoint_without_samples = transaction.savepoint()
                    new_names, samples = add_samples_to_database(add_samples_form, user)
                except IntegrityError:
                    if max_cycles > 0:
                        transaction.savepoint_rollback(savepoint_without_samples)
                    else:
                        raise
                else:
                    break
            ids = [sample.pk for sample in samples]
            utils.Reporter(user).report_new_samples(samples)
            if add_samples_form.cleaned_data["topic"]:
                for watcher in (user_details.user
                                for user_details in add_samples_form.cleaned_data["topic"].auto_adders.all()):
                    for sample in samples:
                        watcher.my_samples.add(sample)
            if len(new_names) > 1:
                success_report = \
                    _("Your samples have the names from {first_name} to {last_name}.  "
                      "They were added to “My Samples”.").format(first_name=new_names[0], last_name=new_names[-1])
            else:
                success_report = _("Your sample has the name {name}.  It was added to “My Samples”."). \
                    format(name=new_names[0])
            if add_samples_form.cleaned_data["rename"] == "new-style":
                return utils.successful_response(request, success_report, "samples.views.bulk_rename.bulk_rename",
                                                 query_string="ids=" + ",".join(str(id_) for id_ in ids),
                                                 forced=True, json_response=ids)
            else:
                return utils.successful_response(request, success_report, json_response=ids)
    else:
        add_samples_form = AddSamplesForm(user)
    return render(request, "samples/add_samples.html", {"title": _("Add samples"),
                                                        "add_samples": add_samples_form,
                                                        "external_operators_available": user.external_contacts.exists()})


class DestinationSamplesForm(forms.Form):
    samples = utils.MultipleSamplesField(label=_("Destination samples"))

    def __init__(self, user, current_sample, *args, **kwargs):
        super(DestinationSamplesForm, self).__init__(*args, **kwargs)
        samples = [sample for sample in user.my_samples.exclude(pk=current_sample.pk)
                   if permissions.has_permission_to_edit_sample(user, sample)]
        self.fields["samples"].set_samples(user, samples)
        self.fields["samples"].widget.attrs["size"] = "20"


@login_required
def copy_informal_stack(request, sample_name):
    """View for copying the informal stack of a sample to other samples.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: unicode

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample, __ = utils.lookup_sample(sample_name, request.user, with_clearance=True)
    if request.method == "POST":
        destination_samples_form = DestinationSamplesForm(request.user, sample, request.POST)
        if destination_samples_form.is_valid():
            destination_samples = destination_samples_form.cleaned_data["samples"]
            informal_layers = sample.sample_details.informal_layers.all()
            for destination_sample in destination_samples:
                destination_sample.sample_details.informal_layers.all().delete()
                for layer in informal_layers:
                    layer.sample_details = destination_sample.sample_details
                    layer.id = None
                    layer.save()
            feed_reporter = utils.Reporter(request.user)
            message = _("Informal stack was copied from sample {sample}.".format(sample=sample))
            feed_reporter.report_edited_samples(destination_samples,
                                                edit_description={"important": False, "description": message})
            return utils.successful_response(
                request, _("Informal stack of {sample} was successfully copied.").format(sample=sample),
                "samples.views.sample.by_id", {"sample_id": sample.id, "path_suffix": ""})
    else:
        destination_samples_form = DestinationSamplesForm(request.user, sample)
    context = {"title": _("Copy informal stack of “{sample}”").format(sample=sample),
               "sample": sample, "destination_samples": destination_samples_form}
    context.update(sample.sample_details.get_context_for_user(request.user, {}))
    return render(request, "samples/copy_informal_stack.html", context)


@login_required
def printer_label(request, sample_id):
    """Generates a PDF for the label printer in 9×45 mm² format.  It contains
    the name and the QR code of a sample.

    :param request: the current HTTP Request object
    :param sample_id: the ID of the sample

    :type request: HttpRequest
    :type sample_id: unicode

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id))
    permissions.get_sample_clearance(request.user, sample)
    pdf_output = printer_labels.printer_label(sample)
    response = HttpResponse()
    response.write(pdf_output)
    response["Content-Type"] = "application/pdf"
    response["Content-Length"] = len(pdf_output)
    return response


_ = ugettext
