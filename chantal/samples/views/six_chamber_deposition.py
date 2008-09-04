#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.forms import ModelForm, Form
from django.forms.util import ValidationError
from django import forms
from django.contrib.auth.decorators import login_required
from chantal.samples.models import SixChamberDeposition, SixChamberLayer, SixChamberChannel
from chantal.samples import models
from . import utils
from .utils import check_permission, DataModelForm
from django.utils.translation import ugettext as _, ugettext_lazy
from django.conf import settings
import django.contrib.auth.models
from django.db.models import Q

class RemoveFromMySamples(Form):
    _ = ugettext_lazy
    remove_deposited_from_my_samples = forms.BooleanField(label=_(u"Remove deposited samples from My Samples"),
                                                          required=False, initial=True)

class AddMyLayerForm(Form):
    _ = ugettext_lazy
    my_layer_to_be_added = forms.ChoiceField(label=_(u"Nickname of My Layer to be added"), required=False)
    def __init__(self, data=None, **keyw):
        user_details = keyw.pop("user_details")
        super(AddMyLayerForm, self).__init__(data, **keyw)
        self.fields["my_layer_to_be_added"].choices = utils.get_my_layers(user_details, SixChamberDeposition, required=False)

class DepositionForm(ModelForm):
    _ = ugettext_lazy
    sample_list = forms.ModelMultipleChoiceField(label=_(u"Samples"), queryset=None)
    operator = utils.OperatorChoiceField(label=_(u"Operator"), queryset=django.contrib.auth.models.User.objects.all())
    def __init__(self, user_details, data=None, **keyw):
        deposition = keyw.get("instance")
        initial = keyw.get("initial", {})
        if deposition:
            initial.update({"sample_list": [sample._get_pk_val() for sample in deposition.samples.all()]})
        keyw["initial"] = initial
        super(DepositionForm, self).__init__(data, **keyw)
        split_widget = forms.SplitDateTimeWidget()
        split_widget.widgets[0].attrs = {'class': 'vDateField'}
        split_widget.widgets[1].attrs = {'class': 'vTimeField'}
        self.fields["timestamp"].widget = split_widget
        self.fields["sample_list"].queryset = \
            models.Sample.objects.filter(Q(processes=deposition) | Q(watchers=user_details)).distinct() if deposition \
            else user_details.my_samples
        self.fields["sample_list"].widget.attrs.update({"size": "15", "style": "vertical-align: top"})
    def clean_sample_list(self):
        sample_list = list(set(self.cleaned_data["sample_list"]))
        if not sample_list:
            raise ValidationError(_(u"You must mark at least one sample."))
        return sample_list
    def save(self, *args, **keyw):
        deposition = super(DepositionForm, self).save(*args, **keyw)
        deposition.samples = self.cleaned_data["sample_list"]
        return deposition
    class Meta:
        model = SixChamberDeposition

class LayerForm(DataModelForm):
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
            raise ValidationError(_(u"Name is unknown."))
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
            raise ValidationError(_(u"Gas type is unknown."))
        return self.cleaned_data["gas"]
    class Meta:
        model = SixChamberChannel
        exclude = ("layer",)

def is_all_valid(deposition_form, layer_forms, channel_form_lists, remove_from_my_samples_form):
    valid = deposition_form.is_valid() and remove_from_my_samples_form.is_valid()
    # Don't use a generator expression here because I want to call ``is_valid``
    # for every form
    valid = valid and all([layer_form.is_valid() for layer_form in layer_forms])
    for forms in channel_form_lists:
        valid = valid and all([channel_form.is_valid() for channel_form in forms])
    return valid

def change_structure(layer_forms, channel_form_lists, post_data):
    # Attention: `post_data` doesn't contain the normalised prefixes, so it
    # must not be used for anything except the `change_params`.  (The
    # structural-change prefixes are normalised always!)
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
    to_be_added_layers = utils.int_or_zero(change_params["structural-change-add-layers"])
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
    referentially_valid = True
    if deposition_form.is_valid() and (
        not deposition or deposition.number != deposition_form.cleaned_data["number"]):
        if models.Deposition.objects.filter(number=deposition_form.cleaned_data["number"]).count():
            utils.append_error(deposition_form, "__all__", _(u"This deposition number exists already."))
            referentially_valid = False
    if not layer_forms:
        utils.append_error(deposition_form, "__all__", _(u"No layers given."))
        referentially_valid = False
    layer_numbers = set()
    for layer_form, channel_forms in zip(layer_forms, channel_form_lists):
        if layer_form.is_valid():
            if layer_form.cleaned_data["number"] in layer_numbers:
                utils.append_error(layer_form, "__all__", _(u"Number is a duplicate."))
            else:
                layer_numbers.add(layer_form.cleaned_data["number"])
        channel_numbers = set()
        for channel_form in channel_forms:
            if channel_form.is_valid():
                if channel_form.cleaned_data["number"] in channel_numbers:
                    utils.append_error(channel_form, "__all__", _(u"Number is a duplicate."))
                else:
                    channel_numbers.add(channel_form.cleaned_data["number"])
    return referentially_valid
    
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

def remove_samples_from_my_samples(samples, user_details):
    for sample in samples:
        user_details.my_samples.remove(sample)

def forms_from_post_data(post_data):
    post_data, number_of_layers, list_of_number_of_channels = utils.normalize_prefixes(post_data)
    layer_forms = [LayerForm(post_data, prefix=str(layer_index)) for layer_index in range(number_of_layers)]
    channel_form_lists = []
    for layer_index in range(number_of_layers):
        channel_form_lists.append(
            [ChannelForm(post_data, prefix="%d_%d"%(layer_index, channel_index))
             for channel_index in range(list_of_number_of_channels[layer_index])])
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

query_string_pattern = re.compile(r"^copy_from=(?P<copy_from>.+)$")

@login_required
@check_permission("change_sixchamberdeposition")
def edit(request, deposition_number):
    deposition = get_object_or_404(SixChamberDeposition, number=deposition_number) if deposition_number else None
    user_details = request.user.get_profile()
    if request.method == "POST":
        deposition_form = DepositionForm(user_details, request.POST, instance=deposition)
        layer_forms, channel_form_lists = forms_from_post_data(request.POST)
        remove_from_my_samples_form = RemoveFromMySamples(request.POST)
        all_valid = is_all_valid(deposition_form, layer_forms, channel_form_lists, remove_from_my_samples_form)
        structure_changed = change_structure(layer_forms, channel_form_lists, request.POST)
        referentially_valid = is_referentially_valid(deposition, deposition_form, layer_forms, channel_form_lists)
        if all_valid and referentially_valid and not structure_changed:
            deposition = save_to_database(deposition_form, layer_forms, channel_form_lists)
            if remove_from_my_samples_form.cleaned_data["remove_deposited_from_my_samples"]:
                remove_samples_from_my_samples(deposition.samples.all(), user_details)
            if deposition_number:
                request.session["success_report"] = \
                    _(u"Deposition %s was successfully changed in the database.") % deposition.number
                return utils.HttpResponseSeeOther("../../")
            else:
                request.session["success_report"] = \
                    _(u"Deposition %s was successfully added to the database.") % deposition.number
                return utils.HttpResponseSeeOther("../../processes/split_and_rename_samples/%d" % deposition.id)
    else:
        deposition_form = None
        match = query_string_pattern.match(request.META["QUERY_STRING"] or "")
        if not deposition and match:
            # Duplication of a deposition
            copy_from_query = models.SixChamberDeposition.objects.filter(number=match.group("copy_from"))
            if copy_from_query.count() == 1:
                deposition_data = copy_from_query.values()[0]
                del deposition_data["timestamp"]
                deposition_data["number"] = utils.get_next_deposition_number("B")
                deposition_form = DepositionForm(user_details, initial=deposition_data)
                layer_forms, channel_form_lists = forms_from_database(copy_from_query.all()[0])
        if not deposition_form:
            # Normal edit of existing deposition, or new deposition, or duplication has failed
            initial = {"number": utils.get_next_deposition_number("B")} if not deposition else {}
            deposition_form = DepositionForm(user_details, initial=initial, instance=deposition)
            layer_forms, channel_form_lists = forms_from_database(deposition)
        remove_from_my_samples_form = RemoveFromMySamples(initial={"remove_deposited_from_my_samples": not deposition})
    add_my_layer_form = AddMyLayerForm(user_details=user_details, prefix="structural-change")
    title = _(u"6-chamber deposition “%s”") % deposition_number if deposition_number else _(u"New 6-chamber deposition")
    return render_to_response("edit_six_chamber_deposition.html",
                              {"title": title, "deposition": deposition_form,
                               "layers_and_channels": zip(layer_forms, channel_form_lists),
                               "add_my_layer": add_my_layer_form,
                               "remove_from_my_samples": remove_from_my_samples_form},
                              context_instance=RequestContext(request))

@login_required
def show(request, deposition_number):
    deposition = get_object_or_404(SixChamberDeposition, number=deposition_number)
    samples = deposition.samples
    if all(not utils.has_permission_for_sample_or_series(request.user, sample) for sample in samples.all()) \
            and not request.user.has_perm("change_sixchamberdeposition"):
        return utils.HttpResponseSeeOther("permission_error")
    template_context = {"title": _(u"6-chamber deposition “%s”") % deposition.number, "samples": samples.all()}
    template_context.update(utils.ProcessContext(request.user).digest_process(deposition))
    return render_to_response("show_process.html", template_context, context_instance=RequestContext(request))
