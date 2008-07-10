#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string
from django.http import HttpResponse, HttpResponseRedirect
from django.template import Context, loader
from django.shortcuts import render_to_response, get_object_or_404
from django.newforms import ModelForm
import django.newforms as forms
import models

def camel_case_to_underscores(name):
    result = []
    for i, character in enumerate(name):
        if i == 0:
            result.append(character.lower())
        elif character in string.ascii_uppercase:
            result.extend(("_", character.lower()))
        else:
            result.append(character)
    return "".join(result)

def digest_process(process):
    process = models.find_actual_process(process)
    template = loader.get_template("show_"+camel_case_to_underscores(process.__class__.__name__)+".html")
    return process, process._meta.verbose_name, template.render(Context({"process": process}))

def show_sample(request, sample_name):
    sample = get_object_or_404(models.Sample, pk=sample_name)
    processes = []
    for process in sample.processes.all():
        process, title, body = digest_process(process)
        processes.append({"timestamp": process.timestamp, "title": title, "operator": process.operator,
                          "body": body})
    return render_to_response("show_sample.html", {"name": sample.name, "processes": processes})

class SixChamberDepositionForm(ModelForm):
    class Meta:
        model = models.SixChamberDeposition
        exclude = ("process_ptr",)

class SixChamberLayerForm(ModelForm):
    def __init__(self, data=None, **keyw):
        super(SixChamberLayerForm, self).__init__(data, **keyw)
        self.fields["number"].widget = \
            forms.TextInput(attrs={"size": "2", "style": "text-align: center; font-size: xx-large"})
        self.fields["chamber"].widget = forms.TextInput(attrs={"size": "3"})
        self.fields["comments"].widget = forms.Textarea(attrs={"cols": "30"})
        for fieldname in ["pressure", "time", "substrate_electrode_distance", "transfer_in_chamber", "pre_heat",
                          "argon_pre_heat", "heating_temperature", "transfer_out_of_chamber", "plasma_start_power",
                          "deposition_frequency", "deposition_power", "base_pressure"]:
            self.fields[fieldname].widget = forms.TextInput(attrs={"size": "10"})
    class Meta:
        model = models.SixChamberLayer
        exclude = ("deposition",)

class SixChamberChannelForm(ModelForm):
    def __init__(self, data=None, **keyw):
        super(SixChamberChannelForm, self).__init__(data, **keyw)
        self.fields["number"].widget = forms.TextInput(attrs={"size": "3", "style": "text-align: center"})
        self.fields["gas"].widget = forms.TextInput(attrs={"size": "10"})
        self.fields["diluted_in"].widget = forms.TextInput(attrs={"size": "10"})
        self.fields["concentration"].widget = forms.TextInput(attrs={"size": "5"})
        self.fields["flow_rate"].widget = forms.TextInput(attrs={"size": "7"})
    class Meta:
        model = models.SixChamberChannel
        exclude = ("layer",)

def edit_six_chamber_deposition(request, deposition_number):
    def is_all_valid(deposition_form, layer_forms, channel_forms):
        if not deposition_form.is_valid():
            return False
        if any([not layer_form.is_valid() for layer_form in layer_forms]):
            return False
        for forms in channel_forms:
            if any([not channel_form.is_valid() for channel_form in forms]):
                return False
        return True
    def change_structure(deposition_form, layer_forms, channel_forms, change_params, deposition):
        structure_changed = False
        layers = deposition.sixchamberlayer_set.all()
        old_number_of_layers = deposition.sixchamberlayer_set.count()
        to_be_duplicated_layernumbers = [layer_forms[index].cleaned_data["number"] for index in range(old_number_of_layers)
                                         if "structural-change-duplicate-layerindex-%d" % index in change_params]
        try:
            to_be_added_layers = int(change_params["structural-change-add-layers"])
        except ValueError:
            to_be_added_layers = 0
        if to_be_duplicated_layernumbers or to_be_added_layers:
            biggest_layer_number = max([layer.number for layer in layers])
        # First step: Duplicate layers
        if to_be_duplicated_layernumbers:
            structure_changed = True
            for number in to_be_duplicated_layernumbers:
                warnings.filterwarnings("ignore", "")
                print number
                layer = layers.get(number=number)
                old_channels = layer.sixchamberchannel_set.all()
                layer.number = biggest_layer_number + 1
                biggest_layer_number += 1
                layer.id = None  # create a new one in the database
                layer.save()
                for channel in old_channels:
                    channel.id = None  # create a new one in the database
                    channel.layer = layer
                    channel.save()
        # Second step: Add layers
        for i in range(to_be_added_layers):
            structure_changed = True
            layer = models.SixChamberLayer(number=biggest_layer_number+1)
            layer.save()
            biggest_layer_number += 1
            deposition.sixchamberlayer_set.add(layer)
        # Third step: Add channels
        layers_with_new_channels = [(layer_forms[index].cleaned_data["number"],
                                     change_params["structural-change-add-channels-for-layerindex-%d" % index])
                                     for index in range(old_number_of_layers)
                                     if "structural-change-add-channels-for-layerindex-%d" % index in change_params]
        for index in range(old_number_of_layers):
            try:
                to_be_added_channels = int(change_params.get("structural-change-add-channels-for-layerindex-%d" % index, 0))
            except ValueError:
                to_be_added_channels = 0
            for i in range(to_be_added_channels):
                pass
        return structure_changed
    
    six_chamber_deposition = get_object_or_404(models.SixChamberDeposition, deposition_number=deposition_number)
    if request.method == "POST":
        deposition_form = SixChamberDepositionForm(request.POST, instance=six_chamber_deposition)
        layer_forms = [SixChamberLayerForm(request.POST, prefix=str(layer.number), instance=layer)
                       for layer in six_chamber_deposition.sixchamberlayer_set.all()]
        channel_forms = []
        for layer in six_chamber_deposition.sixchamberlayer_set.all():
            channel_forms.append(
                [SixChamberChannelForm(request.POST, prefix=str(layer.number)+"_"+str(channel.number), instance=channel)
                 for channel in layer.sixchamberchannel_set.all()])
        change_params = dict([(key, request.POST[key]) for key in request.POST if key.startswith("structural-change-")])
        if is_all_valid(deposition_form, layer_forms, channel_forms):
            # Todo: Write data back into the database
            if not change_structure(deposition_form, layer_forms, channel_forms, change_params, six_chamber_deposition):
                return HttpResponseRedirect("/admin")
    else:
        deposition_form = SixChamberDepositionForm(instance=six_chamber_deposition)
        layer_forms = [SixChamberLayerForm(prefix=str(layer.number), instance=layer)
                       for layer in six_chamber_deposition.sixchamberlayer_set.all()]
        channel_forms = []
        for layer in six_chamber_deposition.sixchamberlayer_set.all():
            channel_forms.append(
                [SixChamberChannelForm(prefix=str(layer.number)+"_"+str(channel.number), instance=channel)
                 for channel in layer.sixchamberchannel_set.all()])
    return render_to_response("edit_six_chamber_deposition.html",
                              {"title": deposition_number,
                               "deposition": deposition_form,
                               "layers_and_channels": zip(layer_forms, channel_forms)})
