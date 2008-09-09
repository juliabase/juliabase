#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from django.utils.translation import ugettext as _, ugettext_lazy
from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.forms.util import ValidationError
from chantal.samples import models
from chantal.samples.views import utils

class MyLayerForm(forms.Form):
    _ = ugettext_lazy
    nickname = forms.CharField(label=_(u"Nickname"))
    deposition_and_layer = forms.CharField(label=_(u"Layer identifier"),
                                           help_text=_(u"in the form \"deposition number\"-\"layer number\""))
    delete = forms.BooleanField(label=_(u"Delete"), required=False)
    def clean_deposition_and_layer(self):
        if "-" not in self.cleaned_data["deposition_and_layer"]:
            raise ValidationError(_(u"Deposition and layer number must be separated by \"-\"."))
        deposition_number, layer_number = self.cleaned_data["deposition_and_layer"].rsplit("-", 1)
        try:
            deposition = models.Deposition.objects.get(number=deposition_number).find_actual_instance()
        except models.Deposition.DoesNotExist:
            raise ValidationError(_(u"Deposition number doesn't exist."))
        try:
            layer_number = int(layer_number)
        except ValueError:
            raise ValidationError(_(u"Layer number isn't a number."))
        # FixMe: Handle the case when there is no "layers" attribute
        if not deposition.layers.filter(number=layer_number).count():
            raise ValidationError(_(u"This layer does not exist in this deposition."))
        return u"%d-%s" % (deposition.id, layer_number)

layer_item_pattern = re.compile(ur"\s*(?P<nickname>.+?)\s*:\s*(?P<raw_layer_identifier>.+?)\s*(?:,\s*|\Z)")
def forms_from_database(user):
    my_layer_forms = []
    my_layers_serialized = user.get_profile().my_layers
    while my_layers_serialized:
        next_match = layer_item_pattern.match(my_layers_serialized)
        nickname, raw_layer_identifier = next_match.group("nickname"), next_match.group("raw_layer_identifier")
        process_id, layer_number = raw_layer_identifier.rsplit("-", 1)
        process_id, layer_number = int(process_id), int(layer_number)
        deposition_number = models.Process.objects.get(pk=process_id).find_actual_instance().number
        deposition_and_layer = u"%s-%d" % (deposition_number, layer_number)
        my_layer_forms.append(MyLayerForm(initial={"nickname": nickname, "deposition_and_layer": deposition_and_layer},
                                          prefix=str(len(my_layer_forms))))
        my_layers_serialized = my_layers_serialized[next_match.end():]
    return my_layer_forms

def forms_from_post_data(post_data):
    my_layer_forms = []
    structure_changed = False
    index = 0
    while True:
        if "%d-nickname" % index not in post_data:
            break
        if "%d-delete" % index in post_data:
            structure_changed = True
        else:
            my_layer_forms.append(MyLayerForm(post_data, prefix=str(index)))
        index += 1
    if my_layer_forms and not post_data["%d-nickname"%(index-1)]:
        del my_layer_forms[-1]
    else:
        structure_changed = True
    return my_layer_forms, structure_changed

def is_referentially_valid(my_layer_forms):
    referentially_valid = True
    nicknames = set()
    for my_layer_form in my_layer_forms:
        if my_layer_form.is_valid():
            nickname = my_layer_form.cleaned_data["nickname"]
            if nickname in nicknames:
                utils.append_error(my_layer_form, "__all__", _(u"Nickname is already given."))
                referentially_valid = False
            else:
                nicknames.add(nickname)
    return referentially_valid

def save_to_database(my_layer_forms, user):
    user_details = user.get_profile()
    user_details.my_layers = \
        u", ".join(["%s: %s" % (form.cleaned_data["nickname"], form.cleaned_data["deposition_and_layer"])
                    for form in my_layer_forms])
    user_details.save()
    
@login_required
def edit(request):
    if request.method == "POST":
        my_layer_forms, structure_changed = forms_from_post_data(request.POST)
        all_valid = all([my_layer_form.is_valid() for my_layer_form in my_layer_forms])
        referentially_valid = is_referentially_valid(my_layer_forms)
        if all_valid and referentially_valid and not structure_changed:
            save_to_database(my_layer_forms, request.user)
            return utils.http_response_go_next(request)
    else:
        my_layer_forms = forms_from_database(request.user)
    my_layer_forms.append(MyLayerForm(prefix=str(len(my_layer_forms))))
    return render_to_response("edit_my_layers.html", {"title": _(u"My Layers"), "my_layers": my_layer_forms},
                              context_instance=RequestContext(request))

