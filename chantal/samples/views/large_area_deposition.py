#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re, datetime
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.shortcuts import render_to_response
from chantal.samples import models
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
import django.contrib.auth.models
from chantal.samples.views.utils import check_permission
from chantal.samples.views import utils

class DepositionForm(forms.ModelForm):
    _ = ugettext_lazy
    operator = utils.OperatorChoiceField(label=_(u"Operator"), queryset=django.contrib.auth.models.User.objects.all())
    class Meta:
        model = models.LargeAreaDeposition
        exclude = ("external_operator",)

class LayerForm(forms.ModelForm):
    _ = ugettext_lazy
    class Meta:
        model = models.LargeAreaLayer
        exclude = ("deposition",)

class AddLayerForm(forms.Form):
    _ = ugettext_lazy
    number_of_layers_to_add = forms.IntegerField(label=_(u"Number of layers to be added"), min_value=0, required=False)
    def clean_number_of_layers_to_add(self):
        return utils.int_or_zero(self.cleaned_data["number_of_layers_to_add"])

class ChangeLayerForm(forms.Form):
    _ = ugettext_lazy
    duplicate_this_layer = forms.BooleanField(label=_(u"duplicate this layer"), required=False)
    remove_this_layer = forms.BooleanField(label=_(u"remove this layer"), required=False)
    def clean(self):
        if self.cleaned_data["duplicate_this_layer"] and self.cleaned_data["remove_this_layer"]:
            raise ValidationError(_(u"You can't duplicate and remove a layer at the same time."))
        return self.cleaned_data

def forms_from_database(deposition):
    pass

def forms_from_post_data(post_data):
    post_data, number_of_layers, __ = utils.normalize_prefixes(post_data)
    layer_forms = [LayerForm(post_data, prefix=str(layer_index)) for layer_index in range(number_of_layers)]
    change_layer_forms = [ChangeLayerForm(post_data, prefix=str(change_layer_index))
                          for change_layer_index in range(number_of_layers)]
    return layer_forms, change_layer_forms

def change_structure(deposition_form, layer_forms, change_layer_forms, add_layer_form):
    deposition_number_pattern = re.compile(ur"(?P<prefix>%02dL-)(?P<number>\d+)$" % (datetime.date.today().year % 100))
    structure_changed = False
    layer_numbers = [layer_form.cleaned_data["number"] for layer_form in layer_forms if layer_form.is_valid()]
    if layer_numbers:
        next_layer_number = max(layer_numbers) + 1
    elif deposition_form.is_valid():
        match = deposition_number_pattern.match(deposition_form.cleaned_data["number"])
        next_layer_number = int(match.group("number")) if match else 1
    else:
        next_layer_number = None
    next_layer_number = max(next_layer_number, 1)

    # Duplicate layers
    old_layer_length = len(layer_forms)
    for layer_index in range(old_layer_length):
        layer_form, change_layer_form = layer_forms[layer_index], change_layer_forms[layer_index]
        if layer_form.is_valid() and change_layer_form.is_valid() and change_layer_form.cleaned_data["duplicate_this_layer"]:
            layer_data = layer_form.cleaned_data
            layer_data["number"] = u"%03d" % next_layer_number
            next_layer_number += 1
            layer_forms.append(LayerForm(initial=layer_data, prefix=str(old_layer_length + layer_index)))
            change_layer_forms.append(ChangeLayerForm(prefix=str(old_layer_length + layer_index)))
            change_layer_forms[layer_index] = ChangeLayerForm(prefix=str(layer_index))
            structure_changed = True

    # Add layers
    if add_layer_form.is_valid() and next_layer_number is not None:
        to_be_added_layers = add_layer_form.cleaned_data["number_of_layers_to_add"]
        old_number_of_layers = len(layer_forms)
        for layer_index in range(old_number_of_layers, old_number_of_layers + to_be_added_layers):
            layer_forms.append(LayerForm(initial={"number": u"%03d" % next_layer_number}, prefix=str(layer_index)))
            next_layer_number += 1
            change_layer_forms.append(ChangeLayerForm(prefix=str(layer_index)))
            structure_changed = True
        add_layer_form = AddLayerForm()

    # Delete layers
    for layer_index in range(len(layer_forms)-1, -1, -1):
        if change_layer_forms[layer_index].is_valid() and change_layer_forms[layer_index].cleaned_data["remove_this_layer"]:
            del layer_forms[layer_index], change_layer_forms[layer_index]
            structure_changed = True

    if deposition_form.is_valid():
        match = deposition_number_pattern.match(deposition_form.cleaned_data["number"])
        if match:
            deposition_data = deposition_form.cleaned_data
            deposition_data["operator"] = \
                django.contrib.auth.models.User.objects.get(username=deposition_data["operator"]).pk
            deposition_data["number"] = match.group("prefix") + u"%03d" % (next_layer_number-1)
            deposition_form = DepositionForm(initial=deposition_data)

    return structure_changed, deposition_form, add_layer_form

def is_all_valid(deposition_form, layer_forms, change_layer_forms, add_layer_form):
    all_valid = deposition_form.is_valid()
    all_valid = add_layer_form.is_valid() and all_valid
    all_valid = all([layer_form.is_valid() for layer_form in layer_forms]) and all_valid
    all_valid = all([change_layer_form.is_valid() for change_layer_form in change_layer_forms]) and all_valid
    return all_valid

@login_required
@check_permission("change_largeareadeposition")
def add(request):
    if request.method == "POST":
        deposition_form = DepositionForm(request.POST)
        add_layer_form = AddLayerForm(request.POST)
        layer_forms, change_layer_forms = forms_from_post_data(request.POST)
        all_valid = is_all_valid(deposition_form, layer_forms, change_layer_forms, add_layer_form)
        structure_changed, deposition_form, add_layer_form = \
            change_structure(deposition_form, layer_forms, change_layer_forms, add_layer_form)
    else:
        deposition_form = DepositionForm(initial={"number": utils.get_next_deposition_number("L-")})
        layer_forms, change_layer_forms = [], []
        add_layer_form = AddLayerForm()
    title = _(u"Add large-area deposition")
    return render_to_response("edit_large_area_deposition.html",
                              {"title": title, "deposition": deposition_form,
                               "layer_and_change_layer": zip(layer_forms, change_layer_forms),
                               "add_layer": add_layer_form},
                              context_instance=RequestContext(request))
