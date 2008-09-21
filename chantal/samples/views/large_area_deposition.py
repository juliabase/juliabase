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

deposition_number_pattern = re.compile(ur"(?P<prefix>%02dL-)(?P<number>\d+)$" % (datetime.date.today().year % 100))
def change_structure(deposition_form, layer_forms, change_layer_forms, add_layer_form):
    structure_changed = False
    new_layers = [("original", layer_form) for layer_form in layer_forms]
    
    # Duplicate layers
    for layer_form, change_layer_form in zip(layer_forms, change_layer_forms):
        if layer_form.is_valid() and change_layer_form.is_valid() and change_layer_form.cleaned_data["duplicate_this_layer"]:
            new_layers.append(("duplicate", layer_form))
            structure_changed = True

    # Add layers
    if add_layer_form.is_valid():
        for i in range(add_layer_form.cleaned_data["number_of_layers_to_add"]):
            new_layers.append(("new", None))
            structure_changed = True
        add_layer_form = AddLayerForm()

    # Delete layers
    for i in range(len(layer_forms)-1, -1, -1):
        if change_layer_forms[i].is_valid() and change_layer_forms[i].cleaned_data["remove_this_layer"]:
            del new_layers[i]
            structure_changed = True

    if structure_changed:
        next_full_number = utils.get_next_deposition_number("L-")
        deposition_number_match = deposition_number_pattern.match(next_full_number)
        next_layer_number = int(deposition_number_match.group("number"))
        old_prefixes = [int(layer_form.prefix) for layer_form in layer_forms if layer_form.is_bound]
        next_prefix = max(old_prefixes) + 1 if old_prefixes else 0
        layer_forms = []
        for new_layer in new_layers:
            if new_layer[0] == "original":
                post_data = new_layer[1].data.copy()
                prefix = new_layer[1].prefix
                post_data[prefix+"-number"] = utils.three_digits(next_layer_number)
                next_layer_number += 1
                layer_forms.append(LayerForm(post_data, prefix=prefix))
            elif new_layer[0] == "duplicate":
                original_layer = layer_forms[new_layer[1]]
                if original_layer.is_valid():
                    layer_data = original_layer.cleaned_data
                    layer_data["number"] = utils.three_digits(next_layer_number)
                    next_layer_number += 1
                    layer_forms.append(LayerForm(initial=layer_data, prefix=str(next_prefix)))
                    next_prefix += 1
            elif new_layer[0] == "new":
                layer_forms.append(LayerForm(initial={"number": utils.three_digits(next_layer_number)},
                                             prefix=str(next_prefix)))
                next_layer_number += 1
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_layers structure: " + new_layer[0])
        post_data = deposition_form.data.copy()
        post_data["number"] = deposition_number_match.group("prefix") + \
            utils.three_digits(next_layer_number - 1 if layer_forms else next_layer_number)
        deposition_form = DepositionForm(post_data)

        change_layer_forms = []
        for layer_form in layer_forms:
            change_layer_forms.append(ChangeLayerForm(prefix=layer_form.prefix))

    return structure_changed, deposition_form, layer_forms, change_layer_forms, add_layer_form

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
        structure_changed, deposition_form, layer_forms, change_layer_forms, add_layer_form = \
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
