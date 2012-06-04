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


"""All views and helper routines directly connected with the 6-chamber
deposition.  This includes adding, editing, and viewing such processes.

In principle, you can copy the code here to implement other deposition systems,
however, this is not implemented perfectly: If done again, *all* form data
should be organised in a real form instead of being hard-coded in the template.
Additionally, `DataModelForm` was a sub-optimal idea: Instead, their data
should be exported into forms of their own, so that I needn't rely on the
validity of the main forms.
"""

from __future__ import absolute_import, unicode_literals

import re, datetime
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.forms import ModelForm, Form
from django.forms.util import ValidationError
from django import forms
import django.core.urlresolvers
from django.contrib.auth.decorators import login_required
import chantal_common.utils
from chantal_common.utils import append_error, is_json_requested
from samples import models, permissions
from samples.views import utils, feed_utils
from chantal_ipv.views import form_utils
from samples.views.form_utils import DataModelForm
from django.utils.translation import ugettext as _, ugettext, ugettext_lazy, ungettext
from django.conf import settings
import django.contrib.auth.models
import chantal_ipv.models as ipv_models


class AddMyLayerForm(Form):
    """Form class for a choice field for appending nicknamed layers from “My
    Layers” to the current deposition.
    """
    _ = ugettext_lazy
    my_layer_to_be_added = forms.ChoiceField(label=_("Nickname of My Layer to be added"), required=False)
    def __init__(self, data=None, **kwargs):
        user_details = kwargs.pop("user_details")
        super(AddMyLayerForm, self).__init__(data, **kwargs)
        self.fields["my_layer_to_be_added"].choices = form_utils.get_my_layers(user_details, ipv_models.SixChamberDeposition)


class DepositionForm(form_utils.ProcessForm):
    """Model form for the basic deposition data.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, data=None, **kwargs):
        """Form constructor.  I have to initialise a couple of things here,
        especially ``operator`` because I overrode it.
        """
        deposition = kwargs.get("instance")
        if not deposition:
            kwargs.setdefault("initial", {}).update({"finished": False})
        super(DepositionForm, self).__init__(data, **kwargs)
        self.fields["operator"].set_operator(user if not deposition else deposition.operator, user.is_staff)
        self.fields["operator"].initial = deposition.operator.pk if deposition else user.pk
        self.already_finished = deposition and deposition.finished
        self.previous_deposition_number = deposition.number if deposition else None
        if self.already_finished:
            self.fields["number"].widget.attrs.update({"readonly": "readonly"})

    def clean_number(self):
        number = self.cleaned_data["number"]
        if self.already_finished and self.previous_deposition_number != number:
            raise ValidationError(_("The deposition number must not be changed."))
        number = form_utils.clean_deposition_number_field(number, "B")
        if (not self.previous_deposition_number or self.previous_deposition_number != number) and \
                models.Deposition.objects.filter(number=number).exists():
            raise ValidationError(_("This deposition number exists already."))
        return number

    def clean_finished(self):
        """Assume ``True`` for ``finished`` if the process is an already
        existing, finished deposition.
        """
        return self.cleaned_data["finished"] if not self.process or not self.process.finished else True

    def clean(self):
        _ = ugettext
        if "number" in self.cleaned_data and "timestamp" in self.cleaned_data:
            if int(self.cleaned_data["number"][:2]) != self.cleaned_data["timestamp"].year % 100:
                append_error(self, _("The first two digits must match the year of the deposition."), "number")
                del self.cleaned_data["number"]
        return self.cleaned_data

    class Meta:
        model = ipv_models.SixChamberDeposition


class LayerForm(DataModelForm):
    """Model form for a 6-chamber layer."""

    def __init__(self, data=None, **kwargs):
        """Model form constructor.  I do additional initialisation here, but
        very harmless: It's only about visual appearance and numerical limits.
        """
        super(LayerForm, self).__init__(data, **kwargs)
        self.fields["number"].widget.attrs.update({"size": "2", "style": "text-align: center; font-size: xx-large"})
        self.fields["comments"].widget.attrs["cols"] = "70"
        self.fields["comments"].widget.attrs["rows"] = "16"
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
        """Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        chantal_common.utils.check_markdown(comments)
        return comments

    class Meta:
        model = ipv_models.SixChamberLayer
        exclude = ("deposition",)


class ChannelForm(ModelForm):
    """Model form for channels in 6-chamber depositions."""

    def __init__(self, data=None, **kwargs):
        """Model form constructor.  I do additional initialisation here, but
        very harmless: It's only about visual appearance.
        """
        super(ChannelForm, self).__init__(data, **kwargs)
        self.fields["number"].widget = forms.TextInput(attrs={"size": "3", "style": "text-align: center"})
        self.fields["flow_rate"].widget = forms.TextInput(attrs={"size": "7"})

    class Meta:
        model = ipv_models.SixChamberChannel
        exclude = ("layer",)

class FormSet(object):
    """Class for holding all forms of the 6-chamber deposition views, and for
    all methods working on these forms.

    :ivar deposition: the deposition to be edited.  If it is ``None``, we
      create a new one.  This is very important because testing ``deposition``
      is the only way to distinguish between editing or creating.

    :type deposition: `models.SixChamberDeposition` or ``NoneType``
    """

    def __init__(self, request, deposition_number):
        """Class constructor.  Note that I don't create the forms here – this
        is done later in `from_post_data` and in `from_database`.

        :Parameters:
          - `request`: the current HTTP Request object
          - `deposition_number`: number of the deposition to be edited/created.
            If this number already exists, *edit* it, if not, *create* it.

        :type request: ``HttpRequest``
        :type deposition_number: unicode
        """
        self.user = request.user
        self.user_details = self.user.samples_user_details
        self.deposition = get_object_or_404(ipv_models.SixChamberDeposition, number=deposition_number) if deposition_number \
            else None
        self.unfinished = self.deposition and not self.deposition.finished
        self.deposition_form = None
        self.layer_forms, self.channel_form_lists = [], []
        self.preset_sample = utils.extract_preset_sample(request) if not self.deposition else None
        self.post_data = None
        self.json_client = chantal_common.utils.is_json_requested(request)

    def from_post_data(self, post_data):
        """Interpret the POST data and create bound forms for layers and channels
        from it.  The top-level channel list has the same number of elements as the
        layer list because they correspond to each other.

        :Parameters:
          - `post_data`: the result from ``request.POST``

        :type post_data: ``QueryDict``
        """
        self.post_data, number_of_layers, list_of_number_of_channels = form_utils.normalize_prefixes(post_data)
        self.deposition_form = DepositionForm(self.user, self.post_data, instance=self.deposition)
        self.samples_form = \
            form_utils.DepositionSamplesForm(self.user, self.preset_sample, self.deposition, self.post_data)
        self.layer_forms = [LayerForm(self.post_data, prefix=str(layer_index)) for layer_index in range(number_of_layers)]
        self.channel_form_lists = []
        for layer_index in range(number_of_layers):
            self.channel_form_lists.append(
                [ChannelForm(self.post_data, prefix="{0}_{1}".format(layer_index, channel_index))
                 for channel_index in range(list_of_number_of_channels[layer_index])])
        self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(self.post_data) if not self.deposition \
            else None
        self.edit_description_form = form_utils.EditDescriptionForm(self.post_data) \
            if self.deposition and self.deposition.finished else None
        self.add_my_layer_form = AddMyLayerForm(user_details=self.user_details, prefix="structural-change")

    def from_database(self, query_dict):
        """Take a deposition instance and construct forms from it for its layers
        and their channels.  The top-level channel list has the same number of
        elements as the layer list because they correspond to each other.

        :Parameters:
          - `query_dict`: dictionary with all given URL query string parameters

        :type query_dict: dict mapping unicode to unicode
        """
        def build_layer_and_channel_forms(deposition):
            """Construct the layer and channel forms for the given deposition
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
                    [ChannelForm(prefix="{0}_{1}".format(layer_index, channel_index), instance=channel)
                     for channel_index, channel in enumerate(layer.channels.all())])

        copy_from = query_dict.get("copy_from")
        if not self.deposition and copy_from:
            # Duplication of a deposition
            copy_from_query = ipv_models.SixChamberDeposition.objects.filter(number=copy_from)
            if copy_from_query.count() == 1:
                deposition_data = copy_from_query.values()[0]
                deposition_data["timestamp"] = datetime.datetime.now()
                deposition_data["timestamp_inaccuracy"] = 0
                deposition_data["number"] = utils.get_next_deposition_number("B")
                self.deposition_form = DepositionForm(self.user, initial=deposition_data)
                deposition = copy_from_query[0]
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
        self.samples_form = form_utils.DepositionSamplesForm(self.user, self.preset_sample, self.deposition)
        self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm() if not self.deposition else None
        self.edit_description_form = form_utils.EditDescriptionForm() \
            if self.deposition and self.deposition.finished else None
        self.add_my_layer_form = AddMyLayerForm(user_details=self.user_details, prefix="structural-change")

    def __change_structure(self):
        """Add or delete layers and channels in the form.  While changes in
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
                    "structural-change-duplicate-layerindex-{0}".format(i) in change_params:
                structure_changed = True
                layer_data = layer_form.cleaned_data
                layer_data["number"] = biggest_layer_number + 1
                biggest_layer_number += 1
                layer_index = len(self.layer_forms) + len(new_layers)
                new_layers.append(LayerForm(initial=layer_data, prefix=str(layer_index)))
                new_channel_lists.append(
                    [ChannelForm(initial=channel.cleaned_data, prefix="{0}_{1}".format(layer_index, channel_index))
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
                # FixMe: "actual_instance" should be "sixchamberdeposition".
                # However, I don't know which exceptions are possible then.
                deposition = models.Deposition.objects.get(pk=deposition_id).actual_instance
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
                        new_channels.append(
                            ChannelForm(initial=channel_data, prefix="{0}_{1}".format(layer_index, channel_index)))
                    new_channel_lists.append(new_channels)

        # Forth and fifth steps: Add and delete channels
        for layer_index, channels in enumerate(self.channel_form_lists):
            # Add channels
            to_be_added_channels = utils.int_or_zero(change_params.get(
                    "structural-change-add-channels-for-layerindex-{0}".format(layer_index)))
            if to_be_added_channels < 0:
                to_be_added_channels = 0
            structure_changed = structure_changed or to_be_added_channels > 0
            number_of_channels = len(channels)
            for channel_index in range(number_of_channels, number_of_channels+to_be_added_channels):
                channels.append(ChannelForm(prefix="{0}_{1}".format(layer_index, channel_index)))
            # Delete channels
            to_be_deleted_channels = [channel_index for channel_index in range(number_of_channels)
                                      if "structural-change-delete-channelindex-{0}-for-layerindex-{1}".
                                          format(channel_index, layer_index) in change_params]
            structure_changed = structure_changed or bool(to_be_deleted_channels)
            for channel_index in reversed(to_be_deleted_channels):
                del channels[channel_index]

        # Sixth step: Delete layers
        to_be_deleted_layers = [layer_index for layer_index in range(len(self.layer_forms))
                                if "structural-change-delete-layerindex-{0}".format(layer_index) in change_params]
        structure_changed = structure_changed or bool(to_be_deleted_layers)
        for layer_index in reversed(to_be_deleted_layers):
            del self.layer_forms[layer_index], self.channel_form_lists[layer_index]

        # Apply changes
        self.layer_forms.extend(new_layers)
        self.channel_form_lists.extend(new_channel_lists)
        return structure_changed

    def __is_all_valid(self):
        """Tests the “inner” validity of all forms belonging to this view.  This
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
        valid = all([layer_form.is_valid() for layer_form in self.layer_forms]) and valid
        for forms in self.channel_form_lists:
            valid = all([channel_form.is_valid() for channel_form in forms]) and valid
        return valid

    def __is_referentially_valid(self):
        """Test whether all forms are consistent with each other and with the
        database.  For example, no layer number must occur twice.

        :Return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if self.deposition_form.is_valid() and self.samples_form.is_valid():
            dead_samples = form_utils.dead_samples(self.samples_form.cleaned_data["sample_list"],
                                                   self.deposition_form.cleaned_data["timestamp"])
            if dead_samples:
                error_message = ungettext(
                    "The sample {samples} is already dead at this time.",
                    "The samples {samples} are already dead at this time.", len(dead_samples)).format(
                    samples=utils.format_enumeration([sample.name for sample in dead_samples]))
                append_error(self.deposition_form, error_message, "timestamp")
                referentially_valid = False
        if not self.layer_forms:
            append_error(self.deposition_form, _("No layers given."))
            referentially_valid = False
        layer_numbers = set()
        for layer_form, channel_forms in zip(self.layer_forms, self.channel_form_lists):
            if layer_form.is_valid():
                if layer_form.cleaned_data["number"] in layer_numbers:
                    append_error(layer_form, _("Number is a duplicate."))
                    referentially_valid = False
                else:
                    layer_numbers.add(layer_form.cleaned_data["number"])
            channel_numbers = set()
            for channel_form in channel_forms:
                if channel_form.is_valid():
                    if channel_form.cleaned_data["number"] in channel_numbers:
                        append_error(channel_form, _("Number is a duplicate."))
                        referentially_valid = False
                    else:
                        channel_numbers.add(channel_form.cleaned_data["number"])
        return referentially_valid

    def save_to_database(self):
        """Save the forms to the database.  Only the deposition is just updated if
        it already existed.  However, layers and channels are completely deleted
        and re-constructed from scratch.

        Additionally, this method removed deposited samples from „My Samples“
        if appropriate, and it generates the feed entries.

        :Return:
          The saved deposition object, or ``None`` if validation failed

        :rtype: `models.SixChamberDeposition` or ``NoneType``
        """
        database_ready = not self.__change_structure() if not self.json_client else True
        database_ready = self.__is_all_valid() and database_ready
        database_ready = self.__is_referentially_valid() and database_ready
        if database_ready:
            deposition = self.deposition_form.save()
            if self.unfinished and deposition.finished and self.user != deposition.operator:
                deposition.operator = self.user
                deposition.save()
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
            feed_utils.Reporter(self.user).report_physical_process(
                deposition, self.edit_description_form.cleaned_data if self.edit_description_form else None)
            return deposition

    def get_context_dict(self):
        """Retrieve the context dictionary to be passed to the template.  This
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
    """Central view for editing, creating, and duplicating 6-chamber
    depositions.  If ``deposition_number`` is ``None``, a new depositon is
    created (possibly by duplicating another one).

    :Parameters:
      - `request`: the HTTP request object
      - `deposition_number`: the number (=name) of the deposition

    :type request: ``QueryDict``
    :type deposition_number: unicode or ``NoneType``

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return form_utils.edit_depositions(request, deposition_number, FormSet(request, deposition_number),
                                       ipv_models.SixChamberDeposition, "samples/edit_six_chamber_deposition.html")

@login_required
def show(request, deposition_number):
    """Show an existing 6-chamber deposision.  You must be a 6-chamber
    supervisor *or* be able to view one of the samples affected by this
    deposition in order to be allowed to view it.

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: the number (=name) or the deposition

    :type request: ``HttpRequest``
    :type deposition_number: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return form_utils.show_depositions(request, deposition_number, ipv_models.SixChamberDeposition)
