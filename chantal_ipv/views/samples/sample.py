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


"""A views and helper routines for adding new samples.  I must override the
default view for adding samples in chantal-samples because I wanto to have a
substrate with every sample, too (and possibly a cleaning process).
"""

from __future__ import absolute_import, unicode_literals

import datetime, re
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
import django.forms as forms
from django.forms.util import ValidationError
from django.forms import widgets
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext, ugettext_lazy as _
from django.contrib.auth.decorators import login_required
import django.core.urlresolvers
from chantal_common.utils import append_error, get_really_full_name
from samples import models, permissions
from samples.views import utils, form_utils, feed_utils
from chantal_ipv import models as ipv_models
from chantal_ipv import printer_labels


class SimpleRadioSelectRenderer(widgets.RadioFieldRenderer):
    def render(self):
        return mark_safe("""<ul class="radio-select">\n{0}\n</ul>""".format("\n".join(
                    """<li style="white-space: nowrap">{0}</li>""".format(force_unicode(w)) for w in self)))


rename_choices = (("", _("no names")),
                    # Translators: "new-style" names
                ("new-style", _("new-style")),
                ("cleaning", _("cleaning number")))

class AddSamplesForm(forms.Form):
    """Form for adding new samples.

    FixMe: Although this form can never represent *one* sample but allows the
    user to add arbitrary samples with the same properties (except for the name
    of course), this should be converted to a *model* form in order to satisfy
    the dont-repeat-yourself principle.

    Besides, we have massive code duplication to substrate.SubstrateForm.
    """
    number_of_samples = forms.IntegerField(label=_("Number of samples"), min_value=1, max_value=100)
    substrate = forms.ChoiceField(label=_("Substrate"), choices=ipv_models.substrate_materials, required=True)
    substrate_comments = forms.CharField(label=_("Substrate comments"), required=False)
    substrate_originator = forms.ChoiceField(label=_("Substrate originator"), required=False)
    timestamp = forms.DateTimeField(label=_("timestamp"))
    timestamp_inaccuracy = forms.IntegerField(required=False)
    current_location = forms.CharField(label=_("Current location"), max_length=50)
    purpose = forms.CharField(label=_("Purpose"), max_length=80, required=False)
    tags = forms.CharField(label=_("Tags"), max_length=255, required=False,
                           help_text=_("separated with commas, no whitespace"))
    topic = form_utils.TopicField(label=_("Topic"), required=False)
    rename = forms.ChoiceField(label=_("Rename"), choices=rename_choices, required=False,
                               widget=forms.RadioSelect(renderer=SimpleRadioSelectRenderer))
    cleaning_number = forms.CharField(label=_("Cleaning number"), max_length=8, required=False)

    def __init__(self, user, data=None, **kwargs):
        _ = ugettext
        super(AddSamplesForm, self).__init__(data, **kwargs)
        self.fields["timestamp"].initial = datetime.datetime.now()
        self.fields["topic"].set_topics(user)
        self.fields["substrate_comments"].help_text = \
            """<span class="markdown-hint">""" + _("""with {markdown_link} syntax""").format(
            markdown_link="""<a href="{0}">Markdown</a>""".format(
                    django.core.urlresolvers.reverse("chantal_common.views.markdown_sandbox"))) + "</span>"
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
        _ = ugettext
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

    def clean_cleaning_number(self):
        _ = ugettext
        cleaning_number = self.cleaned_data["cleaning_number"]
        if cleaning_number:
            if not ipv_models.CleaningProcess.objects.filter(cleaning_number=cleaning_number).exists() and \
            not ipv_models.LargeAreaCleaningProcess.objects.filter(cleaning_number=cleaning_number).exists():
                raise ValidationError(_("The cleaning number you have chosen doesn't exist."))
        return cleaning_number

    def clean(self):
        _ = ugettext
        cleaned_data = self.cleaned_data
        if cleaned_data["substrate"] == "custom" and not cleaned_data.get("substrate_comments"):
            append_error(self, _("For a custom substrate, you must give substrate comments."), "substrate_comments")
        if cleaned_data.get("rename") == "cleaning" and not cleaned_data.get("cleaning_number"):
            append_error(self, _("You must provide a cleaning number if you want to use it for the names."),
                         "cleaning_number")
        return cleaned_data


def add_samples_to_database(add_samples_form, user):
    """Create the new samples and add them to the database.  This routine
    consists of two parts: First, it tries to find a consecutive block of
    provisional sample names.  Then, in actuall creates the samples.

    :Parameters:
      - `add_samples_form`: the form with the samples' common data, including
        the substrate
      - `user`: the current user

    :type add_samples_form: `AddSamplesForm`
    :type user: ``django.contrib.auth.models.User``

    :Return:
      the names of the new samples

    :rtype: list of unicode
    """
    _ = ugettext
    cleaned_data = add_samples_form.cleaned_data
    cleaning_number = cleaned_data.get("cleaning_number")
    substrate = ipv_models.Substrate.objects.create(operator=user, timestamp=cleaned_data["timestamp"],
                                                    material=cleaned_data["substrate"],
                                                    comments=cleaned_data["substrate_comments"],
                                                    external_operator=cleaned_data["substrate_originator"])
    inaccuracy = cleaned_data["timestamp_inaccuracy"]
    if inaccuracy:
        substrate.timestamp_inaccuracy = inaccuracy
        substrate.save()
    if cleaning_number:
        try:
            cleaning_process = ipv_models.CleaningProcess.objects.get(cleaning_number=cleaning_number)
        except ipv_models.CleaningProcess.DoesNotExist:
            cleaning_process = ipv_models.LargeAreaCleaningProcess.objects.get(cleaning_number=cleaning_number)
        if cleaning_process.timestamp <= cleaned_data["timestamp"]:
            substrate.timestamp = cleaning_process.timestamp - datetime.timedelta(minutes=1)
            substrate.save()
    else:
        cleaning_process = None
    provisional_sample_names = \
        models.Sample.objects.filter(name__startswith="*").values_list("name", flat=True)
    occupied_provisional_numbers = [int(name[1:]) for name in provisional_sample_names]
    occupied_provisional_numbers.sort()
    occupied_provisional_numbers.insert(0, 0)
    number_of_samples = cleaned_data["number_of_samples"]
    if add_samples_form.cleaned_data.get("rename") == "cleaning":
        subnumbers = [utils.int_or_zero(name.rpartition("-")[2]) for name in
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
            sample.processes.add(cleaning_process)
        sample.watchers.add(user)
        if topic:
            for watcher in (user_details.user for user_details in topic.auto_adders.all()):
                watcher.my_samples.add(sample)
        new_names.append(unicode(sample))
    return new_names, samples


@login_required
def add(request):
    """View for adding new samples.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    _ = ugettext
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
            feed_utils.Reporter(user).report_new_samples(samples)
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
    return render_to_response("samples/add_samples.html",
                              {"title": _("Add samples"),
                               "add_samples": add_samples_form,
                               "external_operators_available": user.external_contacts.exists()},
                              context_instance=RequestContext(request))


class DestinationSamplesForm(forms.Form):
    samples = form_utils.MultipleSamplesField(label=_("Destination samples"))

    def __init__(self, user, current_sample, *args, **kwargs):
        super(DestinationSamplesForm, self).__init__(*args, **kwargs)
        samples = [sample for sample in user.my_samples.exclude(pk=current_sample.pk)
                   if permissions.has_permission_to_edit_sample(user, sample)]
        self.fields["samples"].set_samples(samples, user)
        self.fields["samples"].widget.attrs["size"] = "20"


@login_required
def copy_informal_stack(request, sample_name):
    """View for copying the informal stack of a sample to other samples.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    _ = ugettext
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
            feed_reporter = feed_utils.Reporter(request.user)
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
    return render_to_response("samples/copy_informal_stack.html", context, context_instance=RequestContext(request))


@login_required
def printer_label(request, sample_id):
    """Generates a PDF for the label printer in 9×45 mm² format.  It contains
    the name and the QR code of a sample.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_id`: the ID of the sample

    :type request: ``HttpRequest``
    :type sample_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id))
    permissions.get_sample_clearance(request.user, sample)
    pdf_output = printer_labels.printer_label(sample)
    response = HttpResponse()
    response.write(pdf_output)
    response["Content-Type"] = "application/pdf"
    response["Content-Length"] = len(pdf_output)
    return response
