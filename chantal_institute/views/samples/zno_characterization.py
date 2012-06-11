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

from __future__ import unicode_literals
import datetime, re
from django import forms
from django.forms.util import ValidationError
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django.template import RequestContext
from chantal_common.utils import append_error
from chantal_institute import models as ipv_models
from samples import models, permissions
from samples.views import utils, feed_utils, form_utils
from django.utils.text import capfirst


deposition_number_pattern = re.compile("\d\dV-\d{3,4}([ab]|-[12])?$")
class DepositionForm(forms.Form):
    """Form for the sputter deposition number.
    """
    _ = ugettext_lazy
    deposition = forms.CharField(label=capfirst(_("sputter deposition number")))

    def __init__(self, data=None, **kwargs):
        super(DepositionForm, self).__init__(data, **kwargs)
        self.fields["deposition"].widget.attrs["size"] = "10"

    def clean_deposition(self):
        deposition_number = self.cleaned_data.get("deposition")
        if deposition_number:
            deposition_number = deposition_number.upper()
            if not deposition_number_pattern.match(deposition_number):
                # Translators: “YY” is year, “L” is letter, and “NNN” is number
                raise ValidationError(_("Invalid deposition number. It must be of the form YYL-NNN."))
            try:
                return ipv_models.LargeSputterDeposition.objects.get(number=deposition_number)
            except ipv_models.LargeSputterDeposition.DoesNotExist:
                raise ValidationError(_("Invalid deposition number. Deposition does not exists."))
        return deposition_number


class CharacterizationForm(form_utils.ProcessForm):
    """Model form for a single characterization.
    """
    _ = ugettext_lazy
    sample = forms.CharField(label=_("Sample"))
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, data=None, **kwargs):
        prefix = kwargs["prefix"]
        super(CharacterizationForm, self).__init__(data, **kwargs)
        self.sample = models.Sample.objects.get(name=data.get(prefix + "-sample")) if data else None
        self.fields["sample"].widget.attrs.update({"readonly": "readonly", "style": "font-size: large", "size": "8"})
        self.fields["thickness"].widget.attrs["size"] = self.fields["r_square"].widget.attrs["size"] = "10"
        self.fields["operator"].set_operator(user, user.is_staff)
        self.fields["operator"].initial = user.pk

    def clean_sample(self):
        return models.Sample.objects.get(name=self.cleaned_data["sample"])

    class Meta:
        model = ipv_models.SputterCharacterization
        exclude = ("large_sputter_deposition", "samples", "rho",
                   "external_operator", "new_cluster_tool_deposition")


class FormSet(object):
    """Class for holding all forms, and for
    all methods working on these forms.
    """
    def __init__(self, request):
        self.user = request.user
        self.deposition_form = None
        self.characterization_forms = []
        self.remove_from_my_samples_form = None

    def from_post_data(self, post_data):
        """Generate all forms from the post data submitted by the user.

        :Parameters:
          - `post_data`: the result from ``request.POST``

        :type post_data: ``QueryDict``
        """
        self.deposition_form = DepositionForm(post_data)
        indices = form_utils.collect_subform_indices(post_data)
        if indices:
            self.characterization_forms = [CharacterizationForm(self.user, post_data, prefix=str(layer_index))
                                           for layer_index in indices]

    def save_to_database(self, suptter_deposition):
        """Saves all zno_characterization_forms into the database.

        :Parameters:
         - `suptter_deposition`: the large sputter deposition to which the characterization was made.

        :type suptter_deposition: `ipv_models.LargeSputterDeposition`
        """
        for characterization_form in self.characterization_forms:
            characterization = characterization_form.save(commit=False)
            # FixMe: It is better to do this evaluation in a specialised
            # ``save`` method of ``CharacterizationForm``.
            characterization.large_sputter_deposition = suptter_deposition
            if characterization.r_square and characterization.thickness:
                characterization.rho = \
                        float(characterization.r_square * characterization.thickness) * 1e-7
            if characterization.thickness and suptter_deposition.layers.count() == 1:
                layer = suptter_deposition.layers.all()[0]
                if layer.feed_rate and layer.steps:
                    characterization.deposition_rate = \
                        characterization.thickness * layer.feed_rate / layer.steps * 60 / 1000
                elif layer.static_time:
                    characterization.deposition_rate = characterization.thickness / layer.static_time
            characterization.save()
            characterization.samples = [characterization_form.sample]

    def create_characterization_forms(self, suptter_deposition):
        """Takes all samples from the large suptter deposition and
        creates a characterization form for each of them.

        :Parameters:
         - `suptter_deposition`: the large sputter deposition to which the characterization was made.

        :type suptter_deposition: `ipv_models.LargeSputterDeposition`
        """
        if not self.characterization_forms or \
        not self.characterization_forms[0].sample in suptter_deposition.samples.all():
            self.characterization_forms = [CharacterizationForm(self.user, prefix=index + 1,
                                           initial={"timestamp": datetime.datetime.now(), "sample": sample.name})
                                           for index, sample in enumerate(suptter_deposition.samples.iterator())]

    def is_all_valid(self):
        """Tests the “inner” validity of all forms belonging to this view.  This
        function calls the ``is_valid()`` method of all forms, even if one of them
        returns ``False`` (and makes the return value clear prematurely).

        :Return:
          whether all forms are valid, i.e. their ``is_valid`` method returns
          ``True``.

        :rtype: bool
        """
        return self.deposition_form.is_valid() and \
            all([characterization_form.is_valid() for characterization_form in self.characterization_forms])

    def get_context_dict(self):
        """Retrieve the context dictionary to be passed to the template.  This
        context dictionary contains all forms in an easy-to-use format for the
        template code.

        :Return:
          context dictionary

        :rtype: dict mapping str to various types
        """
        return {"deposition": self.deposition_form,
                "characterizations": self.characterization_forms,
                "remove_from_my_samples": self.remove_from_my_samples_form}

@login_required
def add(request):
    """Add ZnO characterizations for a complete sputter deposition run.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_add_physical_process(request.user, ipv_models.SputterCharacterization)
    form_set = FormSet(request)
    if request.method == "POST":
        form_set.from_post_data(request.POST)
        if form_set.deposition_form.is_valid():
            sputter_deposition = form_set.deposition_form.cleaned_data["deposition"]
            form_set.create_characterization_forms(sputter_deposition)
            if form_set.is_all_valid():
                form_set.save_to_database(sputter_deposition)
                return utils.successful_response(request,
                        _("ZnO characterizations of sputter deposition {number} was successfully added to the database."). \
                        format(number=form_set.deposition_form.cleaned_data["deposition"]))
    else:
        form_set.deposition_form = DepositionForm()
    title = _("Add ZnO characterizations")
    context_dict = {"title": title}
    context_dict.update(form_set.get_context_dict())
    return render_to_response("samples/add_zno_characterization.html", context_dict, context_instance=RequestContext(request))
