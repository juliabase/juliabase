#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.newforms import ModelForm
from django.newforms.util import ErrorList
import django.newforms as forms
from chantal.samples.models import SixChamberDeposition, SixChamberLayer, SixChamberChannel

class DepositionForm(ModelForm):
    class Meta:
        model = SixChamberDeposition
        exclude = ("process_ptr",)

class LayerForm(ModelForm):
    def __init__(self, data=None, **keyw):
        super(LayerForm, self).__init__(data, **keyw)
        self.fields["number"].widget = \
            forms.TextInput(attrs={"size": "2", "style": "text-align: center; font-size: xx-large"})
        self.fields["chamber"].widget = forms.TextInput(attrs={"size": "3"})
        self.fields["comments"].widget = forms.Textarea(attrs={"cols": "30"})
        for fieldname in ["pressure", "time", "substrate_electrode_distance", "transfer_in_chamber", "pre_heat",
                          "argon_pre_heat", "heating_temperature", "transfer_out_of_chamber", "plasma_start_power",
                          "deposition_frequency", "deposition_power", "base_pressure"]:
            self.fields[fieldname].widget = forms.TextInput(attrs={"size": "10"})
    class Meta:
        model = SixChamberLayer
        exclude = ("deposition",)

class ChannelForm(ModelForm):
    def __init__(self, data=None, **keyw):
        super(ChannelForm, self).__init__(data, **keyw)
        self.fields["number"].widget = forms.TextInput(attrs={"size": "3", "style": "text-align: center"})
        self.fields["gas"].widget = forms.TextInput(attrs={"size": "10"})
        self.fields["diluted_in"].widget = forms.TextInput(attrs={"size": "10"})
        self.fields["concentration"].widget = forms.TextInput(attrs={"size": "5"})
        self.fields["flow_rate"].widget = forms.TextInput(attrs={"size": "7"})
    class Meta:
        model = SixChamberChannel
        exclude = ("layer",)

def is_all_valid(deposition_form, layer_forms, channel_forms):
    valid = deposition_form.is_valid()
    valid = valid and all([layer_form.is_valid() for layer_form in layer_forms])
    for forms in channel_forms:
        valid = valid and all([channel_form.is_valid() for channel_form in forms])
    return valid

def int_or_zero(number):
    try:
        return int(number)
    except ValueError:
        return 0

def prefix_dict(dictionary, prefix):
    return dict([(prefix+"-"+key, dictionary[key]) for key in dictionary])

def change_structure(layer_forms, channel_form_lists, post_data):
    structure_changed = False
    change_params = dict([(key, post_data[key]) for key in post_data if key.startswith("structural-change-")])
    biggest_layer_number = max([int_or_zero(layer.data[layer.prefix+"-number"]) for layer in layer_forms])
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
            layer_data = prefix_dict(layer_data, str(layer_index))
            new_layers.append(LayerForm(layer_data, prefix=str(layer_index)))
            new_channel_lists.append(
                    [ChannelForm(prefix_dict(channel.cleaned_data, "%d_%d"%(layer_index, channel_index)),
                                           prefix="%d_%d"%(layer_index, channel_index))
                     for channel_index, channel in enumerate(channel_form_lists[i])])

    # Second step: Add layers
    to_be_added_layers = int_or_zero(change_params["structural-change-add-layers"])
    structure_changed = structure_changed or to_be_added_layers
    for i in range(to_be_added_layers):
        layer_index = len(layer_forms) + len(new_layers)
        new_layers.append(LayerForm({"%d-number"%layer_index: biggest_layer_number+1}, prefix=str(layer_index)))
        biggest_layer_number += 1
        new_channel_lists.append([])

    # Third and forth steps: Add and delete channels
    for layer_index, channels in enumerate(channel_form_lists):
        # Add channels
        to_be_added_channels = int_or_zero(change_params.get(
                "structural-change-add-channels-for-layerindex-%d" % layer_index))
        structure_changed = structure_changed or to_be_added_channels
        number_of_channels = len(channels)
        for channel_index in range(number_of_channels, number_of_channels+to_be_added_channels):
            channels.append(ChannelForm(prefix="%d_%d"%(layer_index, channel_index)))
        # Delete channels
        to_be_deleted_channels = [channel_index for channel_index in range(number_of_channels)
                                  if "structural-change-delete-channelindex-%d-for-layerindex-%d" %
                                  (channel_index, layer_index) in change_params]
        structure_changed = structure_changed or to_be_deleted_channels
        for channel_index in reversed(to_be_deleted_channels):
            del channels[channel_index]

    # Fifth step: Delete layers
    to_be_deleted_layers = [layer_index for layer_index in range(len(layer_forms))
                            if "structural-change-delete-layerindex-%d" % layer_index in change_params]
    structure_changed = structure_changed or to_be_deleted_layers
    for layer_index in reversed(to_be_deleted_layers):
        del layer_forms[layer_index]

    # Apply changes
    layer_forms.extend(new_layers)
    channel_form_lists.extend(new_channel_lists)
    return structure_changed

def append_error(form, fieldname, error_message):
    form._errors.setdefault(fieldname, ErrorList()).append(error_message)

def is_referencially_valid(deposition_form, layer_forms, channel_form_lists):
    referencially_valid = True
    if not layer_forms:
        append_error(deposition_form, "__all__", "No layers given")
        referencially_valid = False
    layer_numbers = set()
    for layer_form, channel_forms in zip(layer_forms, channel_form_lists):
        if layer_form.is_valid():
            if layer_form.cleaned_data["number"] in layer_numbers:
                append_error(layer_form, "__all__", "Number is a duplicate")
            else:
                layer_numbers.add(layer_form.cleaned_data["number"])
        channel_numbers = set()
        for channel_form in channel_forms:
            if channel_form.is_valid():
                print channel_form.cleaned_data["number"]
                if channel_form.cleaned_data["number"] in channel_numbers:
                    append_error(channel_form, "__all__", "Number is a duplicate")
                else:
                    channel_numbers.add(channel_form.cleaned_data["number"])
    return referencially_valid
    
def save_to_database(deposition_form, layer_forms, channel_form_lists):
    deposition = deposition_form.save()
    deposition.sixchamberlayer_set.all().delete()  # deletes channels, too
    for layer_form, channel_forms in zip(layer_forms, channel_form_lists):
        layer = layer_form.save(commit=False)
        layer.deposition = deposition
        layer.save()
        for channel_form in channel_forms:
            channel = channel_form.save(commit=False)
            channel.layer = layer
            channel.save()

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
    layers = deposition.sixchamberlayer_set.all()
    layer_forms = [LayerForm(prefix=str(layer_index), instance=layer) for layer_index, layer in enumerate(layers)]
    channel_form_lists = []
    for layer_index, layer in enumerate(layers):
        channel_form_lists.append(
            [ChannelForm(prefix="%d_%d"%(layer_index, channel_index), instance=channel)
             for channel_index, channel in enumerate(layer.sixchamberchannel_set.all())])
    return layer_forms, channel_form_lists

def edit(request, deposition_number):
    deposition = get_object_or_404(SixChamberDeposition, deposition_number=deposition_number)
    if request.method == "POST":
        deposition_form = DepositionForm(request.POST, instance=deposition)
        layer_forms, channel_form_lists = forms_from_post_data(request.POST)
        all_valid = is_all_valid(deposition_form, layer_forms, channel_form_lists)
        structure_changed = change_structure(layer_forms, channel_form_lists, request.POST)
        referencially_valid = is_referencially_valid(deposition_form, layer_forms, channel_form_lists)
        if all_valid and referencially_valid and not structure_changed:
            save_to_database(deposition_form, layer_forms, channel_form_lists)
            return HttpResponseRedirect("/admin")
    else:
        deposition_form = DepositionForm(instance=deposition)
        layer_forms, channel_form_lists = forms_from_database(deposition)
    return render_to_response("edit_six_chamber_deposition.html",
                              {"title": deposition_number,
                               "deposition": deposition_form,
                               "layers_and_channels": zip(layer_forms, channel_form_lists)})
