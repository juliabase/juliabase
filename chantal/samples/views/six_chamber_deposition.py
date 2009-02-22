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

from __future__ import absolute_import

import re, datetime
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.forms import ModelForm, Form
from django.forms.util import ValidationError
from django import forms
import django.core.urlresolvers
from django.contrib.auth.decorators import login_required
from samples.models import SixChamberDeposition, SixChamberLayer, SixChamberChannel
from samples import models, permissions
from samples.views import utils, feed_utils, form_utils
from samples.views.form_utils import DataModelForm
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
    operator = form_utils.FixedOperatorField(label=_(u"Operator"))

    def __init__(self, user, data=None, **kwargs):
        u"""Form constructor.  I have to initialise a couple of things here,
        especially ``operator`` because I overrode it.
        """
        deposition = kwargs.get("instance")
        super(DepositionForm, self).__init__(data, **kwargs)
        self.fields["operator"].set_operator(user if not deposition else deposition.operator, user.is_staff)
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


class FormSet(object):
    u"""Class for holding all forms of the 6-chamber deposition views, and for
    all methods working on these forms.

    :ivar deposition: the deposition to be edited.  If it is ``None``, we
      create a new one.  This is very important because testing ``deposition``
      is the only way to distinguish between editing or creating.

    :type deposition: `models.LargeAreaDeposition` or ``NoneType``
    """

    def __init__(self, request, deposition_number):
        u"""Class constructor.  Note that I don't create the forms here – this
        is done later in `from_post_data` and in `from_database`.

        :Parameters:
          - `request`: the current HTTP Request object
          - `deposition_number`: number of the deposition to be edited/created.
            If this number already exists, *edit* it, if not, *create* it.

        :type request: ``HttpRequest``
        :type deposition_number: unicode
        """
        self.user = request.user
        self.user_details = utils.get_profile(self.user)
        self.deposition = get_object_or_404(SixChamberDeposition, number=deposition_number) if deposition_number else None
        self.deposition_form = None
        self.layer_forms, self.channel_form_lists = [], []
        self.preset_sample = utils.extract_preset_sample(request) if not self.deposition else None
        self.post_data = None
        self.remote_client = utils.is_remote_client(request)

    def from_post_data(self, post_data):
        u"""Interpret the POST data and create bound forms for layers and channels
        from it.  The top-level channel list has the same number of elements as the
        layer list because they correspond to each other.

        :Parameters:
          - `post_data`: the result from ``request.POST``

        :type post_data: ``QueryDict``
        """
        self.post_data, number_of_layers, list_of_number_of_channels = form_utils.normalize_prefixes(post_data)
        self.deposition_form = DepositionForm(self.user, self.post_data, instance=self.deposition)
        self.samples_form = \
            form_utils.DepositionSamplesForm(self.user_details, self.preset_sample, self.deposition, self.post_data)
        self.layer_forms = [LayerForm(self.post_data, prefix=str(layer_index)) for layer_index in range(number_of_layers)]
        self.channel_form_lists = []
        for layer_index in range(number_of_layers):
            self.channel_form_lists.append(
                [ChannelForm(self.post_data, prefix="%d_%d"%(layer_index, channel_index))
                 for channel_index in range(list_of_number_of_channels[layer_index])])
        self.remove_from_my_samples_form = RemoveFromMySamplesForm(self.post_data) if not self.deposition else None
        self.edit_description_form = form_utils.EditDescriptionForm(self.post_data) if self.deposition else None
        self.add_my_layer_form = AddMyLayerForm(user_details=self.user_details, prefix="structural-change")

    def from_database(self, query_dict):
        u"""Take a deposition instance and construct forms from it for its layers
        and their channels.  The top-level channel list has the same number of
        elements as the layer list because they correspond to each other.

        :Parameters:
          - `query_dict`: dictionary with all given URL query string parameters

        :type query_dict: dict mapping unicode to unicode
        """
        def build_layer_and_channel_forms(deposition):
            u"""Construct the layer and channel forms for the given deposition
            according to the data currently stored in the database.  Note that
            this method writes its products directly into the instance.

            :Parameters:
              - `deposition`: the 6-chamber deposition for which the layer and
                channel forms should be generated

            :type deposition: `models.SixChamberDeposition`
            """
            layers = deposition.layers.all()
            self.layer_forms = [LayerForm(prefix=str(layer_index), instance=layer)
                                for layer_index, layer in enumerate(layers)]
            self.channel_form_lists = []
            for layer_index, layer in enumerate(layers):
                self.channel_form_lists.append(
                    [ChannelForm(prefix="%d_%d"%(layer_index, channel_index), instance=channel)
                     for channel_index, channel in enumerate(layer.channels.all())])

        copy_from = query_dict.get("copy_from")
        if not self.deposition and copy_from:
            # Duplication of a deposition
            copy_from_query = models.SixChamberDeposition.objects.filter(number=copy_from)
            if copy_from_query.count() == 1:
                deposition_data = copy_from_query.values()[0]
                deposition_data["timestamp"] = datetime.datetime.now()
                deposition_data["number"] = utils.get_next_deposition_number("B")
                self.deposition_form = DepositionForm(self.user, initial=deposition_data)
                deposition = copy_from_query.all()[0]
                build_layer_and_channel_forms(deposition)
        if not self.deposition_form:
            if self.deposition:
                # Normal edit of existing deposition
                self.deposition_form = DepositionForm(self.user, instance=self.deposition)
                build_layer_and_channel_forms(self.deposition)
            else:
                # New deposition, or duplication has failed
                self.deposition_form = DepositionForm(self.user, initial={"number": utils.get_next_deposition_number("B"),
                                                                          "timestamp": datetime.datetime.now()})
                self.layer_forms, self.channel_form_lists = [], []
        self.samples_form = form_utils.DepositionSamplesForm(self.user_details, self.preset_sample, self.deposition)
        self.remove_from_my_samples_form = RemoveFromMySamplesForm() if not self.deposition else None
        self.edit_description_form = form_utils.EditDescriptionForm() if self.deposition else None
        self.add_my_layer_form = AddMyLayerForm(user_details=self.user_details, prefix="structural-change")

    def __change_structure(self):
        u"""Add or delete layers and channels in the form.  While changes in
        form fields are performed by the form objects themselves, they can't
        change the *structure* of the view.  This is performed here.

        :Return:
          whether the structure was changed, i.e. whether layers/channels were
          add or deleted

        :rtype: bool
        """
        # Attention: `post_data` doesn't contain the normalised prefixes, so it
        # must not be used for anything except the `change_params`.  (The
        # structural-change prefixes needn't be normalised!)
        structure_changed = False
        change_params = dict([(key, self.post_data[key]) for key in self.post_data if key.startswith("structural-change-")])
        biggest_layer_number = max([utils.int_or_zero(layer.uncleaned_data("number")) for layer in self.layer_forms] + [0])
        new_layers = []
        new_channel_lists = []

        # First step: Duplicate layers
        for i, layer_form in enumerate(self.layer_forms):
            if layer_form.is_valid() and all([channel.is_valid() for channel in self.channel_form_lists[i]]) and \
                    "structural-change-duplicate-layerindex-%d" % i in change_params:
                structure_changed = True
                layer_data = layer_form.cleaned_data
                layer_data["number"] = biggest_layer_number + 1
                biggest_layer_number += 1
                layer_index = len(self.layer_forms) + len(new_layers)
                new_layers.append(LayerForm(initial=layer_data, prefix=str(layer_index)))
                new_channel_lists.append(
                    [ChannelForm(initial=channel.cleaned_data, prefix="%d_%d"%(layer_index, channel_index))
                     for channel_index, channel in enumerate(self.channel_form_lists[i])])

        # Second step: Add layers
        to_be_added_layers = utils.int_or_zero(change_params.get("structural-change-add-layers"))
        if to_be_added_layers < 0:
            to_be_added_layers = 0
        structure_changed = structure_changed or to_be_added_layers > 0
        for i in range(to_be_added_layers):
            layer_index = len(self.layer_forms) + len(new_layers)
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
                    layer_index = len(self.layer_forms) + len(new_layers)
                    new_layers.append(LayerForm(initial=layer_data, prefix=str(layer_index)))
                    new_channels = []
                    for channel_index, channel_data in enumerate(layer.channels.values()):
                        new_channels.append(ChannelForm(initial=channel_data, prefix="%d_%d"%(layer_index, channel_index)))
                    new_channel_lists.append(new_channels)

        # Forth and fifth steps: Add and delete channels
        for layer_index, channels in enumerate(self.channel_form_lists):
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
        to_be_deleted_layers = [layer_index for layer_index in range(len(self.layer_forms))
                                if "structural-change-delete-layerindex-%d" % layer_index in change_params]
        structure_changed = structure_changed or bool(to_be_deleted_layers)
        for layer_index in reversed(to_be_deleted_layers):
            del self.layer_forms[layer_index]

        # Apply changes
        self.layer_forms.extend(new_layers)
        self.channel_form_lists.extend(new_channel_lists)
        return structure_changed

    def __is_all_valid(self):
        u"""Tests the “inner” validity of all forms belonging to this view.  This
        function calls the ``is_valid()`` method of all forms, even if one of them
        returns ``False`` (and makes the return value clear prematurely).

        :Return:
          whether all forms are valid, i.e. their ``is_valid`` method returns
          ``True``.

        :rtype: bool
        """
        valid = self.deposition_form.is_valid()
        if self.remove_from_my_samples_form:
            valid = self.remove_from_my_samples_form.is_valid() and valid
        valid = (self.edit_description_form.is_valid() if self.edit_description_form else True) and valid
        if self.samples_form.is_bound:
            valid = self.samples_form.is_valid() and valid
        # Don't use a generator expression here because I want to call ``is_valid``
        # for every form
        valid = valid and all([layer_form.is_valid() for layer_form in self.layer_forms])
        for forms in self.channel_form_lists:
            valid = valid and all([channel_form.is_valid() for channel_form in forms])
        return valid

    def __is_referentially_valid(self):
        u"""Test whether all forms are consistent with each other and with the
        database.  For example, no layer number must occur twice, and the
        deposition number must not exist within the database.

        :Return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if self.deposition_form.is_valid():
            if (not self.deposition or self.deposition.number != self.deposition_form.cleaned_data["number"]) and \
                    models.Deposition.objects.filter(number=self.deposition_form.cleaned_data["number"]).count():
                form_utils.append_error(self.deposition_form, _(u"This deposition number exists already."))
                referentially_valid = False
            if self.samples_form.is_valid():
                dead_samples = form_utils.dead_samples(self.samples_form.cleaned_data["sample_list"],
                                                       self.deposition_form.cleaned_data["timestamp"])
                if dead_samples:
                    error_message = ungettext(u"The sample %s is already dead at this time.",
                                              u"The samples %s are already dead at this time.", len(dead_samples))
                    error_message %= utils.format_enumeration([sample.name for sample in dead_samples])
                    form_utils.append_error(self.deposition_form, error_message, "timestamp")
                    referentially_valid = False
        if not self.layer_forms:
            form_utils.append_error(self.deposition_form, _(u"No layers given."))
            referentially_valid = False
        layer_numbers = set()
        for layer_form, channel_forms in zip(self.layer_forms, self.channel_form_lists):
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

    def save_to_database(self):
        u"""Save the forms to the database.  Only the deposition is just updated if
        it already existed.  However, layers and channels are completely deleted
        and re-constructed from scratch.

        Additionally, this method removed deposited samples from „My Samples“
        if appropriate, and it generates the feed entries.

        :Return:
          The saved deposition object, or ``None`` if validation failed

        :rtype: `models.SixChamberDeposition` or ``NoneType``
        """
        database_ready = not self.__change_structure() if not self.remote_client else True
        database_ready = self.__is_all_valid() and database_ready
        database_ready = self.__is_referentially_valid() and database_ready
        if database_ready:
            deposition = self.deposition_form.save()
            if self.samples_form.is_bound:
                deposition.samples = self.samples_form.cleaned_data["sample_list"]
            deposition.layers.all().delete()  # deletes channels, too
            for layer_form, channel_forms in zip(self.layer_forms, self.channel_form_lists):
                layer = layer_form.save(commit=False)
                layer.deposition = deposition
                layer.save()
                for channel_form in channel_forms:
                    channel = channel_form.save(commit=False)
                    channel.layer = layer
                    channel.save()
            if self.remove_from_my_samples_form and \
                    self.remove_from_my_samples_form.cleaned_data["remove_deposited_from_my_samples"]:
                utils.remove_samples_from_my_samples(deposition.samples.all(), self.user_details)
            feed_utils.Reporter(self.user).report_physical_process(
                deposition, self.edit_description_form.cleaned_data if self.edit_description_form else None)
            return deposition

    def get_context_dict(self):
        u"""Retrieve the context dictionary to be passed to the template.  This
        context dictionary contains all forms in an easy-to-use format for the
        template code.

        :Return:
          context dictionary

        :rtype: dict mapping str to various types
        """
        return {"deposition": self.deposition_form, "samples": self.samples_form,
                "layers_and_channels": zip(self.layer_forms, self.channel_form_lists),
                "add_my_layer": self.add_my_layer_form, "remove_from_my_samples": self.remove_from_my_samples_form,
                "edit_description": self.edit_description_form}


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
    form_set = FormSet(request, deposition_number)
    permissions.assert_can_add_edit_physical_process(request.user, form_set.deposition, SixChamberDeposition)
    if request.method == "POST":
        form_set.from_post_data(request.POST)
        deposition = form_set.save_to_database()
        if deposition:
            if deposition_number:
                return utils.successful_response(
                    request, _(u"Deposition %s was successfully changed in the database.") % deposition.number)
            else:
                return utils.successful_response(
                    request, _(u"Deposition %s was successfully added to the database.") % deposition.number,
                    "samples.views.split_after_deposition.split_and_rename_after_deposition",
                    {"deposition_number": deposition.number},
                    forced=True, remote_client_response=deposition.number)
    else:
        form_set.from_database(utils.parse_query_string(request))
    title = _(u"6-chamber deposition “%s”") % deposition_number if deposition_number else _(u"New 6-chamber deposition")
    context_dict = {"title": title}
    context_dict.update(form_set.get_context_dict())
    return render_to_response("edit_six_chamber_deposition.html", context_dict, context_instance=RequestContext(request))


@login_required
def show(request, deposition_number):
    u"""Show an existing 6-chamber_deposision.  You must be a 6-chamber
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
