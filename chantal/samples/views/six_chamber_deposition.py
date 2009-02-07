#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""All views and helper routines directly connected with the 6-chamber
deposition.  This includes adding, editing, and viewing such processes.

In principle, you can copy the code here to implement other deposition systems,
however, this is not implemented perfectly: If done again, *all* form data
should be organised in a real form instead of being hard-coded in the template.
Additionally, `DataModelForm` was a sub-optimal idea: Instead, their data
should be exported into forms of their own, so that I needn't rely on the
validity of the main forms.
"""

import re, datetime
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.forms import ModelForm, Form
from django.forms.util import ValidationError
from django import forms
import django.core.urlresolvers
from django.contrib.auth.decorators import login_required
from chantal.samples.models import SixChamberDeposition, SixChamberLayer, SixChamberChannel
from chantal.samples import models, permissions
from chantal.samples.views import utils, feed_utils, form_utils
from chantal.samples.views.form_utils import DataModelForm
from django.utils.translation import ugettext as _, ugettext, ugettext_lazy, ungettext
from django.conf import settings
import django.contrib.auth.models


class RemoveFromMySamplesForm(Form):
    u"""Form class for one single checkbox for removing deposited samples from
    “My Samples”.
    """
    _ = ugettext_lazy
    remove_deposited_from_my_samples = forms.BooleanField(label=_(u"Remove deposited samples from My Samples"),
                                                          required=False, initial=True)


class AddMyLayerForm(Form):
    u"""Form class for a choice field for appending nicknamed layers from “My
    Layers” to the current deposition.
    """
    _ = ugettext_lazy
    my_layer_to_be_added = forms.ChoiceField(label=_(u"Nickname of My Layer to be added"), required=False)
    def __init__(self, data=None, **kwargs):
        user_details = kwargs.pop("user_details")
        super(AddMyLayerForm, self).__init__(data, **kwargs)
        self.fields["my_layer_to_be_added"].choices = form_utils.get_my_layers(user_details, SixChamberDeposition)


class DepositionForm(form_utils.ProcessForm):
    u"""Model form for the basic deposition data.
    """
    _ = ugettext_lazy
    sample_list = form_utils.MultipleSamplesField(label=_(u"Samples"))
    operator = form_utils.FixedOperatorField(label=_(u"Operator"))

    def __init__(self, user_details, preset_sample, data=None, **kwargs):
        u"""Form constructor.  I have to initialise a couple of things here in
        a non-trivial way, especially those that I have added myself
        (``sample_list`` and ``operator``).
        """
        deposition = kwargs.get("instance")
        self.is_new = not deposition
        samples = list(user_details.my_samples.all())
        if not self.is_new:
            # If editing an existing deposition, always have an *unbound* form
            # so that the samples are set although sample selection is
            # "disabled" and thus never successful when submitting
            super(DepositionForm, self).__init__(**kwargs)
            samples.extend(deposition.samples.all())
            self.fields["sample_list"].widget.attrs["disabled"] = "disabled"
            self.fields["sample_list"].required = False
            self.fields["sample_list"].initial = deposition.samples.values_list("pk", flat=True)
        else:
            super(DepositionForm, self).__init__(data, **kwargs)
        if preset_sample:
            samples.append(preset_sample)
            self.fields["sample_list"].initial = [preset_sample.pk]
        self.fields["sample_list"].set_samples(samples)
        self.fields["sample_list"].widget.attrs.update({"size": "15", "style": "vertical-align: top"})
        user = user_details.user
        self.fields["operator"].set_operator(user if self.is_new else deposition.operator, user.is_staff)
        self.fields["operator"].initial = deposition.operator.pk if deposition else user.pk

    def clean_number(self):
        return form_utils.clean_deposition_number_field(self.cleaned_data["number"], "B")

    def clean(self):
        _ = ugettext
        if "number" in self.cleaned_data and "timestamp" in self.cleaned_data:
            if int(self.cleaned_data["number"][:2]) != self.cleaned_data["timestamp"].year % 100:
                form_utils.append_error(self, _(u"The first two digits must match the year of the deposition."), "number")
                del self.cleaned_data["number"]
        return self.cleaned_data

    def save(self, *args, **kwargs):
        u"""Additionally to the deposition itself, I must store the list of
        samples connected with the deposition (if it is a new one)."""
        deposition = super(DepositionForm, self).save(*args, **kwargs)
        if self.is_new:
            deposition.samples = self.cleaned_data["sample_list"]
        return deposition

    class Meta:
        model = SixChamberDeposition


class LayerForm(DataModelForm):
    u"""Model form for a 6-chamber layer."""

    def __init__(self, data=None, **kwargs):
        u"""Model form constructor.  I do additional initialisation here, but
        very harmless: It's only about visual appearance and numerical limits.
        """
        super(LayerForm, self).__init__(data, **kwargs)
        self.fields["number"].widget.attrs.update({"size": "2", "style": "text-align: center; font-size: xx-large"})
        self.fields["comments"].widget.attrs["cols"] = "30"
        for fieldname in ["pressure", "time", "substrate_electrode_distance", "transfer_in_chamber", "pre_heat",
                          "gas_pre_heat_gas", "gas_pre_heat_pressure", "gas_pre_heat_time", "heating_temperature",
                          "transfer_out_of_chamber", "plasma_start_power",
                          "deposition_frequency", "deposition_power", "base_pressure"]:
            self.fields[fieldname].widget.attrs["size"] = "10"
        for fieldname, min_value, max_value in [("deposition_frequency", 13, 150), ("plasma_start_power", 0, 1000),
                                                ("deposition_power", 0, 1000)]:
            self.fields[fieldname].min_value = min_value
            self.fields[fieldname].max_value = max_value

    def clean_time(self):
        return form_utils.clean_time_field(self.cleaned_data["time"])

    def clean_pre_heat(self):
        return form_utils.clean_time_field(self.cleaned_data["pre_heat"])

    def clean_gas_pre_heat_time(self):
        return form_utils.clean_time_field(self.cleaned_data["gas_pre_heat_time"])

    def clean_pressure(self):
        return form_utils.clean_quantity_field(self.cleaned_data["pressure"], ["mTorr", "mbar", "Torr", "hPa"])

    def clean_gas_pre_heat_pressure(self):
        return form_utils.clean_quantity_field(self.cleaned_data["gas_pre_heat_pressure"], ["Torr"])

    def clean_comments(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        form_utils.check_markdown(comments)
        return comments

    class Meta:
        model = SixChamberLayer
        exclude = ("deposition",)


class ChannelForm(ModelForm):
    u"""Model form for channels in 6-chamber depositions."""

    def __init__(self, data=None, **kwargs):
        u"""Model form constructor.  I do additional initialisation here, but
        very harmless: It's only about visual appearance.
        """
        super(ChannelForm, self).__init__(data, **kwargs)
        self.fields["number"].widget = forms.TextInput(attrs={"size": "3", "style": "text-align: center"})
        self.fields["flow_rate"].widget = forms.TextInput(attrs={"size": "7"})

    class Meta:
        model = SixChamberChannel
        exclude = ("layer",)


def is_all_valid(deposition_form, layer_forms, channel_form_lists, remove_from_my_samples_form,
                 edit_description_form):
    u"""Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    Note that the validity of the ``add_my_layer_form`` is not checked – its
    contents is tested and used directly in `change_structure`.

    :Parameters:
      - `deposition_form`: a bound deposition form
      - `layer_forms`: the list with all bound layer forms of the deposition
      - `channel_form_lists`: all bound channel forms of this deposition.  It
        is a list, and every item is again a list containing all the channels
        of the layer with the same index in ``layer forms``.
      - `remove_from_my_samples_form`: a bound form for the checkbox for
        removing deposited samples from My Samples; ``None`` if we're editing
        an existing deposition
      - `edit_description_form`: a bound form with description of edit changes
        if editing an existing deposition, or ``None`` if a new one is created

    :type deposition_form: `DepositionForm`
    :type layer_forms: list of `LayerForm`
    :type channel_form_lists: list of lists of `ChannelForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm` or ``NoneType``
    :type edit_description_form: `form_utils.EditDescriptionForm` or ``NoneType``

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    valid = deposition_form.is_valid()
    if remove_from_my_samples_form:
        valid = remove_from_my_samples_form.is_valid() and valid
    valid = (edit_description_form.is_valid() if edit_description_form else True) and valid
    # Don't use a generator expression here because I want to call ``is_valid``
    # for every form
    valid = valid and all([layer_form.is_valid() for layer_form in layer_forms])
    for forms in channel_form_lists:
        valid = valid and all([channel_form.is_valid() for channel_form in forms])
    return valid


def change_structure(layer_forms, channel_form_lists, post_data):
    u"""Add or delete layers and channels in the form.  While changes in form
    fields are performs by the form objects themselves, they can't change the
    *structure* of the view.  This is performed here.

    :Parameters:
      - `layer_forms`: the list with all bound layer forms of the deposition
      - `channel_form_lists`: all bound channel forms of this deposition.  It
        is a list, and every item is again a list containing all the channels
        of the layer with the same index in ``layer forms``.
      - `post_data`: the result of ``request.POST``

    :type layer_forms: list of `LayerForm`
    :type channel_form_lists: list of lists of `ChannelForm`
    :type post_data: ``QueryDict``

    :Return:
      whether the structure was changed, i.e. whether layers/channels were
      add or deleted

    :rtype: bool
    """
    # Attention: `post_data` doesn't contain the normalised prefixes, so it
    # must not be used for anything except the `change_params`.  (The
    # structural-change prefixes needn't be normalised!)
    structure_changed = False
    change_params = dict([(key, post_data[key]) for key in post_data if key.startswith("structural-change-")])
    biggest_layer_number = max([utils.int_or_zero(layer.uncleaned_data("number")) for layer in layer_forms] + [0])
    new_layers = []
    new_channel_lists = []

    # First step: Duplicate layers
    for i, layer_form in enumerate(layer_forms):
        if layer_form.is_valid() and all([channel.is_valid() for channel in channel_form_lists[i]]) and \
                "structural-change-duplicate-layerindex-%d" % i in change_params:
            structure_changed = True
            layer_data = layer_form.cleaned_data
            layer_data["number"] = biggest_layer_number + 1
            biggest_layer_number += 1
            layer_index = len(layer_forms) + len(new_layers)
            new_layers.append(LayerForm(initial=layer_data, prefix=str(layer_index)))
            new_channel_lists.append(
                [ChannelForm(initial=channel.cleaned_data, prefix="%d_%d"%(layer_index, channel_index))
                 for channel_index, channel in enumerate(channel_form_lists[i])])

    # Second step: Add layers
    to_be_added_layers = utils.int_or_zero(change_params.get("structural-change-add-layers"))
    if to_be_added_layers < 0:
        to_be_added_layers = 0
    structure_changed = structure_changed or to_be_added_layers > 0
    for i in range(to_be_added_layers):
        layer_index = len(layer_forms) + len(new_layers)
        new_layers.append(LayerForm(initial={"number": biggest_layer_number+1}, prefix=str(layer_index)))
        biggest_layer_number += 1
        new_channel_lists.append([])
    # Third step: Add My Layer
    my_layer = change_params.get("structural-change-my_layer_to_be_added")
    if my_layer:
        structure_changed = True
        deposition_id, layer_number = my_layer.split("-")
        deposition_id, layer_number = int(deposition_id), int(layer_number)
        try:
            # FixMe: "find_actual_instance()" should be "sixchamberdeposition".
            # However, I don't know which exceptions are possible then.
            deposition = models.Deposition.objects.get(pk=deposition_id).find_actual_instance()
        except models.Deposition.DoesNotExist:
            pass
        else:
            layer_query = deposition.layers.filter(number=layer_number)
            if layer_query.count() == 1:
                layer = layer_query[0]
                layer_data = layer_query.values()[0]
                layer_data["number"] = biggest_layer_number + 1
                biggest_layer_number += 1
                layer_index = len(layer_forms) + len(new_layers)
                new_layers.append(LayerForm(initial=layer_data, prefix=str(layer_index)))
                new_channels = []
                for channel_index, channel_data in enumerate(layer.channels.values()):
                    new_channels.append(ChannelForm(initial=channel_data, prefix="%d_%d"%(layer_index, channel_index)))
                new_channel_lists.append(new_channels)

    # Forth and fifth steps: Add and delete channels
    for layer_index, channels in enumerate(channel_form_lists):
        # Add channels
        to_be_added_channels = utils.int_or_zero(change_params.get(
                "structural-change-add-channels-for-layerindex-%d" % layer_index))
        if to_be_added_channels < 0:
            to_be_added_channels = 0
        structure_changed = structure_changed or to_be_added_channels > 0
        number_of_channels = len(channels)
        for channel_index in range(number_of_channels, number_of_channels+to_be_added_channels):
            channels.append(ChannelForm(prefix="%d_%d"%(layer_index, channel_index)))
        # Delete channels
        to_be_deleted_channels = [channel_index for channel_index in range(number_of_channels)
                                  if "structural-change-delete-channelindex-%d-for-layerindex-%d" %
                                  (channel_index, layer_index) in change_params]
        structure_changed = structure_changed or bool(to_be_deleted_channels)
        for channel_index in reversed(to_be_deleted_channels):
            del channels[channel_index]

    # Sixth step: Delete layers
    to_be_deleted_layers = [layer_index for layer_index in range(len(layer_forms))
                            if "structural-change-delete-layerindex-%d" % layer_index in change_params]
    structure_changed = structure_changed or bool(to_be_deleted_layers)
    for layer_index in reversed(to_be_deleted_layers):
        del layer_forms[layer_index]

    # Apply changes
    layer_forms.extend(new_layers)
    channel_form_lists.extend(new_channel_lists)
    return structure_changed


def is_referentially_valid(deposition, deposition_form, layer_forms, channel_form_lists):
    u"""Test whether all forms are consistent with each other and with the
    database.  For example, no layer number must occur twice, and the
    deposition number must not exist within the database.

    :Parameters:
      - `deposition`: the currently edited deposition, or ``None`` if we create
        a new one
      - `deposition_form`: a bound deposition form
      - `layer_forms`: the list with all bound layer forms of the deposition
      - `channel_form_lists`: all bound channel forms of this deposition.  It
        is a list, and every item is again a list containing all the channels
        of the layer with the same index in ``layer forms``.

    :type deposition: `models.SixChamberDeposition` or ``NoneType``
    :type deposition_form: `DepositionForm`
    :type layer_forms: list of `LayerForm`
    :type channel_form_lists: list of lists of `ChannelForm`

    :Return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if deposition_form.is_valid():
        if (not deposition or deposition.number != deposition_form.cleaned_data["number"]) and \
                models.Deposition.objects.filter(number=deposition_form.cleaned_data["number"]).count():
            form_utils.append_error(deposition_form, _(u"This deposition number exists already."))
            referentially_valid = False
        dead_samples = form_utils.dead_samples(deposition_form.cleaned_data["sample_list"],
                                               deposition_form.cleaned_data["timestamp"])
        if dead_samples:
            error_message = ungettext(u"The sample %s is already dead at this time.",
                                      u"The samples %s are already dead at this time.", len(dead_samples))
            error_message %= utils.format_enumeration([sample.name for sample in dead_samples])
            form_utils.append_error(deposition_form, error_message, "timestamp")
            referentially_valid = False
    if not layer_forms:
        form_utils.append_error(deposition_form, _(u"No layers given."))
        referentially_valid = False
    layer_numbers = set()
    for layer_form, channel_forms in zip(layer_forms, channel_form_lists):
        if layer_form.is_valid():
            if layer_form.cleaned_data["number"] in layer_numbers:
                form_utils.append_error(layer_form, _(u"Number is a duplicate."))
                referentially_valid = False
            else:
                layer_numbers.add(layer_form.cleaned_data["number"])
        channel_numbers = set()
        for channel_form in channel_forms:
            if channel_form.is_valid():
                if channel_form.cleaned_data["number"] in channel_numbers:
                    form_utils.append_error(channel_form, _(u"Number is a duplicate."))
                    referentially_valid = False
                else:
                    channel_numbers.add(channel_form.cleaned_data["number"])
    return referentially_valid


def save_to_database(deposition_form, layer_forms, channel_form_lists):
    u"""Save the forms to the database.  Only the deposition is just updated if
    it already existed.  However, layers and channels are completely deleted
    and re-constructed from scratch.

    :Parameters:
      - `deposition_form`: a bound deposition form
      - `layer_forms`: the list with all bound layer forms of the deposition
      - `channel_form_lists`: all bound channel forms of this deposition.  It
        is a list, and every item is again a list containing all the channels
        of the layer with the same index in ``layer forms``.

    :type deposition_form: `DepositionForm`
    :type layer_forms: list of `LayerForm`
    :type channel_form_lists: list of lists of `ChannelForm`

    :Return:
      The saved deposition object

    :rtype: `models.SixChamberDeposition`
    """
    deposition = deposition_form.save()
    deposition.layers.all().delete()  # deletes channels, too
    for layer_form, channel_forms in zip(layer_forms, channel_form_lists):
        layer = layer_form.save(commit=False)
        layer.deposition = deposition
        layer.save()
        for channel_form in channel_forms:
            channel = channel_form.save(commit=False)
            channel.layer = layer
            channel.save()
    return deposition


def forms_from_post_data(post_data):
    u"""Interpret the POST data and create bound forms for layers and channels
    from it.  The top-level channel list has the same number of elements as the
    layer list because they correspond to each other.

    :Parameters:
      - `post_data`: the result from ``request.POST``

    :type post_data: ``QueryDict``

    :Return:
      list of layer forms, list of lists of channel forms

    :rtype: list of `LayerForm`, list of lists of `ChannelForm`
    """
    post_data, number_of_layers, list_of_number_of_channels = form_utils.normalize_prefixes(post_data)
    layer_forms = [LayerForm(post_data, prefix=str(layer_index)) for layer_index in range(number_of_layers)]
    channel_form_lists = []
    for layer_index in range(number_of_layers):
        channel_form_lists.append(
            [ChannelForm(post_data, prefix="%d_%d"%(layer_index, channel_index))
             for channel_index in range(list_of_number_of_channels[layer_index])])
    return layer_forms, channel_form_lists


def forms_from_database(deposition):
    u"""Take a deposition instance and construct forms from it for its layers
    and their channels.  The top-level channel list has the same number of
    elements as the layer list because they correspond to each other.

    :Parameters:
      - `deposition`: the deposition to be converted to forms.

    :type deposition: `models.Deposition`

    :Return:
      list of layer forms, list of lists of channel forms

    :rtype: list of `LayerForm`, list of lists of `ChannelForm`
    """
    layers = deposition.layers.all()
    layer_forms = [LayerForm(prefix=str(layer_index), instance=layer) for layer_index, layer in enumerate(layers)]
    channel_form_lists = []
    for layer_index, layer in enumerate(layers):
        channel_form_lists.append(
            [ChannelForm(prefix="%d_%d"%(layer_index, channel_index), instance=channel)
             for channel_index, channel in enumerate(layer.channels.all())])
    return layer_forms, channel_form_lists


@login_required
def edit(request, deposition_number):
    u"""Central view for editing, creating, and duplicating 6-chamber
    depositions.  If `deposition_number` is ``None``, a new depositon is
    created (possibly by duplicating another one).

    :Parameters:
      - `request`: the HTTP request object
      - `deposition_number`: the number (=name) or the deposition

    :type request: ``QueryDict``
    :type deposition_number: unicode or ``NoneType``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    deposition = get_object_or_404(SixChamberDeposition, number=deposition_number) if deposition_number else None
    permissions.assert_can_add_edit_physical_process(request.user, deposition, SixChamberDeposition)
    user_details = utils.get_profile(request.user)
    preset_sample = utils.extract_preset_sample(request) if not deposition else None
    if request.method == "POST":
        deposition_form = DepositionForm(user_details, preset_sample, request.POST, instance=deposition)
        layer_forms, channel_form_lists = forms_from_post_data(request.POST)
        remove_from_my_samples_form = RemoveFromMySamplesForm(request.POST) if not deposition else None
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if deposition else None
        all_valid = is_all_valid(
            deposition_form, layer_forms, channel_form_lists, remove_from_my_samples_form, edit_description_form)
        structure_changed = change_structure(layer_forms, channel_form_lists, request.POST)
        referentially_valid = is_referentially_valid(deposition, deposition_form, layer_forms, channel_form_lists)
        if all_valid and referentially_valid and not structure_changed:
            deposition = save_to_database(deposition_form, layer_forms, channel_form_lists)
            feed_utils.Reporter(request.user).report_physical_process(
                deposition, edit_description_form.cleaned_data if edit_description_form else None)
            if remove_from_my_samples_form and remove_from_my_samples_form.cleaned_data["remove_deposited_from_my_samples"]:
                utils.remove_samples_from_my_samples(deposition.samples.all(), user_details)
            if deposition_number:
                request.session["success_report"] = \
                    _(u"Deposition %s was successfully changed in the database.") % deposition.number
                return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse("samples.views.main.main_menu"))
            else:
                if utils.is_remote_client(request):
                    return utils.respond_to_remote_client(deposition.number)
                else:
                    request.session["success_report"] = \
                        _(u"Deposition %s was successfully added to the database.") % deposition.number
                    return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse(
                            "samples.views.split_after_deposition.split_and_rename_after_deposition",
                            kwargs={"deposition_number": deposition.number}))
    else:
        deposition_form = None
        copy_from = utils.parse_query_string(request).get("copy_from")
        if not deposition and copy_from:
            # Duplication of a deposition
            copy_from_query = models.SixChamberDeposition.objects.filter(number=copy_from)
            if copy_from_query.count() == 1:
                deposition_data = copy_from_query.values()[0]
                deposition_data["timestamp"] = datetime.datetime.now()
                deposition_data["number"] = utils.get_next_deposition_number("B")
                deposition_form = DepositionForm(user_details, preset_sample, initial=deposition_data)
                layer_forms, channel_form_lists = forms_from_database(copy_from_query.all()[0])
        if not deposition_form:
            if deposition:
                # Normal edit of existing deposition
                deposition_form = DepositionForm(user_details, preset_sample, instance=deposition)
                layer_forms, channel_form_lists = forms_from_database(deposition)
            else:
                # New deposition, or duplication has failed
                deposition_form = DepositionForm(
                    user_details, preset_sample, initial={"number": utils.get_next_deposition_number("B"),
                                                          "timestamp": datetime.datetime.now()})
                layer_forms, channel_form_lists = [], []
        remove_from_my_samples_form = \
            RemoveFromMySamplesForm(initial={"remove_deposited_from_my_samples": not deposition}) if not deposition else None
        edit_description_form = form_utils.EditDescriptionForm() if deposition else None
    add_my_layer_form = AddMyLayerForm(user_details=user_details, prefix="structural-change")
    title = _(u"6-chamber deposition “%s”") % deposition_number if deposition_number else _(u"New 6-chamber deposition")
    return render_to_response("edit_six_chamber_deposition.html",
                              {"title": title, "deposition": deposition_form,
                               "layers_and_channels": zip(layer_forms, channel_form_lists),
                               "add_my_layer": add_my_layer_form,
                               "remove_from_my_samples": remove_from_my_samples_form,
                               "edit_description": edit_description_form},
                              context_instance=RequestContext(request))


@login_required
def show(request, deposition_number):
    u"""Show an existing 6-chamber deposision.  You must be a 6-chamber
    operator *or* be able to view one of the samples affected by this
    deposition in order to be allowed to view it.

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: the number (=name) or the deposition

    :type request: ``HttpRequest``
    :type deposition_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    deposition = get_object_or_404(SixChamberDeposition, number=deposition_number)
    permissions.assert_can_view_physical_process(request.user, deposition)
    samples = deposition.samples
    template_context = {"title": _(u"6-chamber deposition “%s”") % deposition.number, "samples": samples.all(),
                        "process": deposition}
    template_context.update(utils.ProcessContext(request.user).digest_process(deposition))
    return render_to_response("show_process.html", template_context, context_instance=RequestContext(request))
