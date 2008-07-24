#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from django.template import RequestContext
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.newforms import ModelForm, Form
from django.newforms.util import ValidationError
import django.newforms as forms
from django.contrib.auth.decorators import login_required
from chantal.samples.models import SixChamberDeposition, SixChamberLayer, SixChamberChannel
from chantal.samples import models
from . import utils
from .utils import check_permission
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

class DepositionForm(ModelForm):
    sample_list = forms.CharField(label=_("Sample list"), widget=forms.TextInput(attrs={"size": "40"}),
                                  help_text=_("if more than one sample, separate them with commas"))
    def __init__(self, data=None, **keyw):
        deposition = keyw.get("instance")
        initial = keyw.get("initial", {})
        initial["sample_list"] = ", ".join([sample.name for sample in deposition.samples.all()]) if deposition else ""
        keyw["initial"] = initial
        super(DepositionForm, self).__init__(data, **keyw)
        split_widget = forms.SplitDateTimeWidget()
        split_widget.widgets[0].attrs = {'class': 'vDateField'}
        split_widget.widgets[1].attrs = {'class': 'vTimeField'}
        self.fields["timestamp"].widget = split_widget
    def clean_sample_list(self):
        sample_list = [name.strip() for name in self.cleaned_data["sample_list"].split(",")]
        invalid_sample_names = set()
        duplicate_sample_names = set()
        normalized_sample_names = set()
        for sample_name in [name for name in sample_list if name]:
            normalized_sample_name = utils.normalize_sample_name(sample_name)
            if not normalized_sample_name:
                invalid_sample_names.add(sample_name)
            elif normalized_sample_name in normalized_sample_names:
                duplicate_sample_names.add(sample_name)
            else:
                normalized_sample_names.add(normalized_sample_name)
        if invalid_sample_names:
            raise ValidationError(_("I don't know %s.") % ", ".join(invalid_sample_names))
        if duplicate_sample_names:
            raise ValidationError(_("Multiple occurences of %s.") % ", ".join(duplicate_sample_names))
        if not normalized_sample_names:
            raise ValidationError(_("You must give at least one valid sample name."))
        return ",".join(normalized_sample_names)
    def save(self, *args, **keyw):
        deposition = super(DepositionForm, self).save(*args, **keyw)
        samples = [utils.get_sample(sample_name) for sample_name in self.cleaned_data["sample_list"].split(",")]
        deposition.samples = samples
        return deposition
    class Meta:
        model = SixChamberDeposition
        exclude = ("process_ptr",)

class LayerForm(ModelForm):
    chamber_names = set([x[0] for x in models.six_chamber_chamber_choices])
    def __init__(self, data=None, **keyw):
        super(LayerForm, self).__init__(data, **keyw)
        self.fields["number"].widget = \
            forms.TextInput(attrs={"size": "2", "style": "text-align: center; font-size: xx-large"})
        self.fields["comments"].widget = forms.Textarea(attrs={"cols": "30"})
        for fieldname in ["pressure", "time", "substrate_electrode_distance", "transfer_in_chamber", "pre_heat",
                          "gas_pre_heat_gas", "gas_pre_heat_pressure", "gas_pre_heat_time", "heating_temperature",
                          "transfer_out_of_chamber", "plasma_start_power",
                          "deposition_frequency", "deposition_power", "base_pressure"]:
            self.fields[fieldname].widget = forms.TextInput(attrs={"size": "10"})
        for fieldname, min_value, max_value in [("deposition_frequency", 13, 150), ("plasma_start_power", 0, 1000),
                                                ("deposition_power", 0, 1000)]:
            self.fields[fieldname].min_value = min_value
            self.fields[fieldname].max_value = max_value
    def clean_chamber(self):
        if self.cleaned_data["chamber"] not in self.chamber_names:
            raise ValidationError(_("Name is unknown."))
        return self.cleaned_data["chamber"]
    def clean_time(self):
        return utils.clean_time_field(self.cleaned_data["time"])
    def clean_pre_heat(self):
        return utils.clean_time_field(self.cleaned_data["pre_heat"])
    def clean_gas_pre_heat_time(self):
        return utils.clean_time_field(self.cleaned_data["gas_pre_heat_time"])
    def clean_pressure(self):
        return utils.clean_quantity_field(self.cleaned_data["pressure"], ["mTorr", "mbar"])
    def clean_gas_pre_heat_pressure(self):
        return utils.clean_quantity_field(self.cleaned_data["gas_pre_heat_pressure"], ["mTorr", "mbar"])
    class Meta:
        model = SixChamberLayer
        exclude = ("deposition",)

class ChannelForm(ModelForm):
    gas_names = set([x[0] for x in models.six_chamber_gas_choices])
    def __init__(self, data=None, **keyw):
        super(ChannelForm, self).__init__(data, **keyw)
        self.fields["number"].widget = forms.TextInput(attrs={"size": "3", "style": "text-align: center"})
        self.fields["flow_rate"].widget = forms.TextInput(attrs={"size": "7"})
    def clean_gas(self):
        if self.cleaned_data["gas"] not in self.gas_names:
            raise ValidationError(_("Gas type is unknown."))
        return self.cleaned_data["gas"]
    class Meta:
        model = SixChamberChannel
        exclude = ("layer",)

def is_all_valid(deposition_form, layer_forms, channel_forms):
    valid = deposition_form.is_valid()
    valid = valid and all([layer_form.is_valid() for layer_form in layer_forms])
    for forms in channel_forms:
        valid = valid and all([channel_form.is_valid() for channel_form in forms])
    return valid

def change_structure(layer_forms, channel_form_lists, post_data):
    structure_changed = False
    change_params = dict([(key, post_data[key]) for key in post_data if key.startswith("structural-change-")])
    biggest_layer_number = max([utils.int_or_zero(layer.data[layer.prefix+"-number"]) for layer in layer_forms] + [0])
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
    to_be_added_layers = utils.int_or_zero(change_params["structural-change-add-layers"])
    structure_changed = structure_changed or to_be_added_layers > 0
    for i in range(to_be_added_layers):
        layer_index = len(layer_forms) + len(new_layers)
        new_layers.append(LayerForm(initial={"number": biggest_layer_number+1}, prefix=str(layer_index)))
        biggest_layer_number += 1
        new_channel_lists.append([])

    # Third and forth steps: Add and delete channels
    for layer_index, channels in enumerate(channel_form_lists):
        # Add channels
        to_be_added_channels = utils.int_or_zero(change_params.get(
                "structural-change-add-channels-for-layerindex-%d" % layer_index))
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

    # Fifth step: Delete layers
    to_be_deleted_layers = [layer_index for layer_index in range(len(layer_forms))
                            if "structural-change-delete-layerindex-%d" % layer_index in change_params]
    structure_changed = structure_changed or bool(to_be_deleted_layers)
    for layer_index in reversed(to_be_deleted_layers):
        del layer_forms[layer_index]

    # Apply changes
    layer_forms.extend(new_layers)
    channel_form_lists.extend(new_channel_lists)
    return structure_changed

def is_referencially_valid(deposition, deposition_form, layer_forms, channel_form_lists):
    referencially_valid = True
    if deposition_form.is_valid() and (
        not deposition or deposition.deposition_number != deposition_form.cleaned_data["deposition_number"]):
        if models.SixChamberDeposition.objects.filter(deposition_number=
                                                      deposition_form.cleaned_data["deposition_number"]).count():
            utils.append_error(deposition_form, "__all__", _("This deposition number exists already."))
            referencially_valid = False
    if not layer_forms:
        utils.append_error(deposition_form, "__all__", _("No layers given."))
        referencially_valid = False
    layer_numbers = set()
    for layer_form, channel_forms in zip(layer_forms, channel_form_lists):
        if layer_form.is_valid():
            if layer_form.cleaned_data["number"] in layer_numbers:
                utils.append_error(layer_form, "__all__", _("Number is a duplicate."))
            else:
                layer_numbers.add(layer_form.cleaned_data["number"])
        channel_numbers = set()
        for channel_form in channel_forms:
            if channel_form.is_valid():
                if channel_form.cleaned_data["number"] in channel_numbers:
                    utils.append_error(channel_form, "__all__", _("Number is a duplicate."))
                else:
                    channel_numbers.add(channel_form.cleaned_data["number"])
    return referencially_valid
    
def save_to_database(deposition_form, layer_forms, channel_form_lists):
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
    layer_indices = set()
    channel_indices = {}
    for name in post_data:
        match = re.match(ur"(?P<layer_index>\d+)-.+", name)
        if match:
            layer_index = int(match.group("layer_index"))
            layer_indices.add(layer_index)
            channel_indices.setdefault(layer_index, set())
        match = re.match(ur"(?P<layer_index>\d+)_(?P<channel_index>\d+)-.+", name)
        if match:
            layer_index, channel_index = int(match.group("layer_index")), int(match.group("channel_index"))
            channel_indices.setdefault(layer_index, set()).add(channel_index)
    layer_forms = [LayerForm(post_data, prefix=str(layer_index)) for layer_index in layer_indices]
    channel_form_lists = []
    for layer_index in layer_indices:
        channel_form_lists.append(
            [ChannelForm(post_data, prefix="%d_%d"%(layer_index, channel_index))
             for channel_index in channel_indices[layer_index]])
    return layer_forms, channel_form_lists

def forms_from_database(deposition):
    if not deposition:
        return [], []
    layers = deposition.layers.all()
    layer_forms = [LayerForm(prefix=str(layer_index), instance=layer) for layer_index, layer in enumerate(layers)]
    channel_form_lists = []
    for layer_index, layer in enumerate(layers):
        channel_form_lists.append(
            [ChannelForm(prefix="%d_%d"%(layer_index, channel_index), instance=channel)
             for channel_index, channel in enumerate(layer.channels.all())])
    return layer_forms, channel_form_lists

@login_required
@check_permission("change_sixchamberdeposition")
def edit(request, deposition_number):
    deposition = get_object_or_404(SixChamberDeposition, deposition_number=deposition_number) if deposition_number else None
    if request.method == "POST":
        deposition_form = DepositionForm(request.POST, instance=deposition)
        layer_forms, channel_form_lists = forms_from_post_data(request.POST)
        all_valid = is_all_valid(deposition_form, layer_forms, channel_form_lists)
        structure_changed = change_structure(layer_forms, channel_form_lists, request.POST)
        referencially_valid = is_referencially_valid(deposition, deposition_form, layer_forms, channel_form_lists)
        if all_valid and referencially_valid and not structure_changed:
            deposition = save_to_database(deposition_form, layer_forms, channel_form_lists)
            return HttpResponseRedirect("../../" if deposition_number
                                        else "../../processes/split-and-rename-samples/%d" % deposition.id)
    else:
        deposition_form = DepositionForm(instance=deposition)
        layer_forms, channel_form_lists = forms_from_database(deposition)
    title = _(u"6-chamber deposition “%s”") % deposition_number if deposition_number else _("New 6-chamber deposition")
    return render_to_response("edit_six_chamber_deposition.html",
                              {"title": title, "deposition": deposition_form,
                               "layers_and_channels": zip(layer_forms, channel_form_lists)},
                              context_instance=RequestContext(request))
