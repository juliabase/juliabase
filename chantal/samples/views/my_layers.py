#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from django.utils.translation import ugettext as _, ugettext_lazy
from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.template import RequestContext
from . import utils

class MyLayerForm(forms.Form):
    nickname = forms.CharField(label=_(u"nickname"))
    deposition_and_layer = forms.CharField(label=_(u"layer identifier"),
                                           help_text=_(u"in the form \"deposition number\"-\"layer number\""))
    delete = forms.BooleanField(label=_(u"delete"), required=False)
    def clean_deposition_and_layer(self):
        if "-" not in self.cleaned_data["deposition_and_layer"]:
            raise ValidationError(_(u"Deposition and layer number must be separated by \"-\"."))
        deposition_name, layer = self.cleaned_data["deposition_and_layer"].rsplit("-", 1)
        deposition = utils.get_deposition(deposition_name)
        # Start work here

layer_item_pattern = re.compile(ur"\s*(?P<nickname>.+?)\s*:\s*(?P<raw_layer_identifier>.+?)\s*(?:,\s*|\Z)")
def forms_from_database(user):
    my_layer_forms = []
    my_layers_serialized = user.get_profile().my_layers
    while my_layers_serialized:
        next_match = layer_item_pattern.match(my_layers_serialized)
        nickname, raw_layer_identifier = next_match.group("nickname"), next_match.group("raw_layer_identifier")
        process_id, layer_number = raw_layer_identifier.rsplit("-", 1)
        process_id = int(process_id)
        deposition_number = models.Process.objects.get(pk=process_id).find_actual_instance().deposition_number
        deposition_and_layer = u"%s-%s" % (deposition_number, layer_number)
        my_layer_forms.append(MyLayerForm(initial={"nickname": nickname, "deposition_and_layer": deposition_and_layer},
                                          prefix=str(len(my_layer_forms))))
        my_layers_serialized = my_layers_serialized[next_match.end():]
    return my_layer_forms

def forms_from_post_data(post_data):
    my_layer_forms = []
    structure_changed = False
    while True:
        index = len(my_layer_forms)
        if "%d-nickname" % index not in post_data:
            break
        if "%d-delete" % index in post_data:
            structure_changed = True
        else:
            my_layer_forms.append(MyLayerForm(post_data, prefix=str(index)))
    if index > 0 and not post_data["%d-nickname"%(index-1)]:
        del my_layer_forms[-1]
    return my_layer_forms, structure_changed

def is_referencially_valid(my_layer_forms):
    for my_layer_form in my_layer_forms:
        
    
@login_required
def edit(request):
    if request.method == "POST":
        my_layer_forms, structure_changed = forms_from_post_data(request.POST)
        all_valid = all([my_layer_form.is_valid() for my_layer_form in my_layer_forms])
        referencially_valid = is_referencially_valid(my_layer_forms)
        
    else:
        my_layer_forms = forms_from_database(request.user)
    my_layer_forms.append(MyLayerForm(prefix=str(len(my_layer_forms))))
    return render_to_response("edit_my_layers.html", {"my_layers": my_layer_forms},
                              context_instance=RequestContext(request))

