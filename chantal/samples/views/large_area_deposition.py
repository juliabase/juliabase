#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""All views and helper routines directly connected with the large-area
deposition.  This includes adding, editing, and viewing such processes.

Note that this implementation differs greatly from the first deposition system
implementation for the 6-chamber deposition.  The main reason is that I have
many forms here, so keeping everything in one class called `FormSet` saved me
from having annoyingly long function signature.  Another reason is the
ideosyncratic way to number depositions for the large-area, which leads to
*calculated* layer and deposition numbers rather than the free, editable
numbers for the 6-chamber deposition.

I recommend to copy from here instead of from the 6-chamber deposition for new
deposition views.
"""

from __future__ import absolute_import

import re, datetime
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from samples import models, permissions
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext, ungettext
import django.core.urlresolvers
import django.contrib.auth.models
from chantal_common.utils import append_error
from samples.views import utils, form_utils
import chantal_ipv.models as ipv_models


class DepositionForm(form_utils.ProcessForm):
    u"""Model form for the deposition main data.  I only overwrite ``operator``
    in order to have full real names.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_(u"Operator"))

    def __init__(self, user, data=None, **kwargs):
        u"""Class constructor just for changing the appearance of the number
        field."""
        super(DepositionForm, self).__init__(data, **kwargs)
        self.fields["number"].widget.attrs.update({"readonly": "readonly", "style": "font-size: large", "size": "8"})
        deposition = kwargs.get("instance")
        self.fields["operator"].set_operator(deposition.operator if deposition else user, user.is_staff)
        self.fields["operator"].initial = deposition.operator.pk if deposition else user.pk

    def clean_number(self):
        return form_utils.clean_deposition_number_field(self.cleaned_data["number"], "L")

    def validate_unique(self):
        u"""Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `FormSet.__is_referentially_valid`.  I cannot use
        Django's built-in test anyway because it leads to an error message in
        wrong German (difficult to fix, even for the Django guys).
        """
        pass

    def clean(self):
        if "number" in self.cleaned_data and "timestamp" in self.cleaned_data:
            if int(self.cleaned_data["number"][:2]) != self.cleaned_data["timestamp"].year % 100:
                append_error(self, _(u"The first two digits must match the year of the deposition."), "number")
                del self.cleaned_data["number"]
        return self.cleaned_data

    class Meta:
        model = ipv_models.LargeAreaDeposition
        exclude = ("external_operator",)


class LayerForm(forms.ModelForm):
    u"""Model form for a single layer.
    """
    _ = ugettext_lazy

    def __init__(self, *args, **kwargs):
        u"""Form constructor.  I only tweak the HTML layout slightly, and I set
        the initial date to today for fresh layers.
        """
        if "instance" not in kwargs:
            # Note that ``initial`` has higher priority than ``instance`` in
            # model forms.
            initial = kwargs.get("initial", {})
            initial["date"] = datetime.date.today()
            kwargs["initial"] = initial
        super(LayerForm, self).__init__(*args, **kwargs)
        self.fields["number"].widget.attrs.update({"readonly": "readonly", "size": "5", "style": "font-size: large"})
        for fieldname in ["date", "sih4", "h2", "tmb", "ch4", "co2", "ph3", "power", "pressure", "temperature",
                          "time", "dc_bias", "electrodes_distance"]:
            self.fields[fieldname].widget.attrs["size"] = "10"

    class Meta:
        model = ipv_models.LargeAreaLayer
        exclude = ("deposition",)


class RemoveFromMySamplesForm(forms.Form):
    u"""Form for the question whether the user wants to remove the deposited
        samples from the “My Samples” list after having created the deposition.
    """
    _ = ugettext_lazy
    remove_deposited_from_my_samples = forms.BooleanField(label=_(u"Remove deposited samples from My Samples"),
                                                          required=False, initial=True)


class ChangeLayerForm(forms.Form):
    u"""Form for manipulating a layer.  Duplicating it (appending the
    duplicate), deleting it, and moving it up- or downwards.
    """
    _ = ugettext_lazy
    duplicate_this_layer = forms.BooleanField(label=_(u"duplicate this layer"), required=False)
    remove_this_layer = forms.BooleanField(label=_(u"remove this layer"), required=False)
    move_this_layer = forms.ChoiceField(label=_(u"move this layer"), required=False,
                                        choices=(("", u"---------"), ("up", _(u"up")), ("down", _(u"down"))))

    def clean(self):
        _ = ugettext
        operations = 0
        if self.cleaned_data["duplicate_this_layer"]:
            operations += 1
        if self.cleaned_data["remove_this_layer"]:
            operations += 1
        if self.cleaned_data.get("move_this_layer"):
            operations += 1
        if operations > 1:
            raise ValidationError(_(u"You can't duplicate, move, or remove a layer at the same time."))
        return self.cleaned_data


class FormSet(object):
    u"""Class for holding all forms of the large-area deposition views, and for
    all methods working on these forms.

    :ivar deposition: the deposition to be edited.  If it is ``None``, we
      create a new one.  This is very important because testing ``deposition``
      is the only way to distinguish between editing or creating.

    :type deposition: `ipv_models.LargeAreaDeposition` or ``NoneType``
    """
    deposition_number_pattern = re.compile(ur"(?P<prefix>\d\dL-)(?P<number>\d+)$")

    def __init__(self, request, deposition_number):
        u"""Class constructor.  Note that I don't create the forms here – this
        is done later in `from_post_data` and in `from_database`.

        :Parameters:
          - `request`: the current HTTP Request object
          - `deposition_number`: number of the deposition to be edited/created.
            If this number already exists, *edit* it, if not, *create* it.

        :type request: ``HttpRequest``
        :type deposition_number: unicode
        """
        self.user = request.user
        self.user_details = utils.get_profile(self.user)
        self.deposition = \
            get_object_or_404(ipv_models.LargeAreaDeposition, number=deposition_number) if deposition_number else None
        self.deposition_form = self.add_layers_form = self.samples_form = self.remove_from_my_samples_form = None
        self.layer_forms, self.change_layer_forms = [], []
        self.preset_sample = utils.extract_preset_sample(request) if not self.deposition else None
        self.post_data = None
        self.remote_client = utils.is_remote_client(request)

    def from_post_data(self, post_data):
        u"""Generate all forms from the post data submitted by the user.

        :Parameters:
          - `post_data`: the result from ``request.POST``

        :type post_data: ``QueryDict``
        """
        self.post_data = post_data
        self.deposition_form = DepositionForm(self.user, self.post_data, instance=self.deposition)
        self.add_layers_form = form_utils.AddLayersForm(self.user_details, ipv_models.LargeAreaDeposition, self.post_data)
        if not self.deposition:
            self.remove_from_my_samples_form = RemoveFromMySamplesForm(self.post_data)
        self.samples_form = \
            form_utils.DepositionSamplesForm(self.user_details, self.preset_sample, self.deposition, self.post_data)
        indices = form_utils.collect_subform_indices(self.post_data)
        self.layer_forms = [LayerForm(self.post_data, prefix=str(layer_index)) for layer_index in indices]
        self.change_layer_forms = [ChangeLayerForm(self.post_data, prefix=str(change_layer_index))
                                   for change_layer_index in indices]

    def __read_layer_forms(self, source_deposition, destination_deposition_number=None):
        u"""Generate a set of layer forms from database data.  Note that the
        layers are not returned – instead, they are written directly into
        ``self.layer_forms``.

        :Parameters:
          - `source_deposition`: the deposition from which the layers should be
            taken.  Note that this may be the deposition which is currently
            edited, or the deposition which is duplicated to create a new
            deposition.
          - `destination_deposition_number`: if given, duplicate into a
            deposition with this number.  If none, ``source_deposition``
            already contains the proper deposition number.

        :type source_deposition: `ipv_models.LargeAreaDeposition`
        :type destination_deposition_number: unicode
        """
        if destination_deposition_number:
            base_number = int(self.deposition_number_pattern.match(destination_deposition_number).group("number")) - \
                source_deposition.layers.count() + 1
        else:
            base_number = int(self.deposition_number_pattern.match(source_deposition.number).group("number")) - \
                source_deposition.layers.count() + 1
        self.layer_forms = [LayerForm(prefix=str(layer_index), instance=layer,
                                      initial={"number": utils.three_digits(base_number + layer_index)})
                            for layer_index, layer in enumerate(source_deposition.layers.all())]

    def from_database(self, query_dict):
        u"""Create all forms from database data.  This is used if the view was
        retrieved from the user with the HTTP GET method, so there hasn't been
        any post data submitted.

        I have to distinguish all three cases in this method: editing, copying,
        and duplication.

        :Parameters:
          - `query_dict`: dictionary with all given URL query string parameters

        :type query_dict: dict mapping unicode to unicode
        """
        copy_from = query_dict.get("copy_from")
        if not self.deposition and copy_from:
            # Duplication of a deposition
            source_deposition_query = ipv_models.LargeAreaDeposition.objects.filter(number=copy_from)
            if source_deposition_query.count() == 1:
                deposition_data = source_deposition_query.values()[0]
                deposition_data["timestamp"] = datetime.datetime.now()
                deposition_data["operator"] = self.user.pk
                deposition_data["number"] = utils.get_next_deposition_number("L")
                self.deposition_form = DepositionForm(self.user, initial=deposition_data)
                self.__read_layer_forms(source_deposition_query.all()[0], deposition_data["number"])
        if not self.deposition_form:
            if self.deposition:
                # Normal edit of existing deposition
                self.deposition_form = DepositionForm(self.user, instance=self.deposition)
                self.__read_layer_forms(self.deposition)
            else:
                # New deposition, or duplication has failed
                self.deposition_form = DepositionForm(
                    self.user, initial={"operator": self.user.pk, "timestamp": datetime.datetime.now(),
                                        "number": utils.get_next_deposition_number("L")})
                self.layer_forms, self.change_layer_forms = [], []
        self.samples_form = form_utils.DepositionSamplesForm(self.user_details, self.preset_sample, self.deposition)
        self.change_layer_forms = [ChangeLayerForm(prefix=str(index)) for index in range(len(self.layer_forms))]
        self.add_layers_form = form_utils.AddLayersForm(self.user_details, ipv_models.LargeAreaDeposition)
        if not self.deposition:
            self.remove_from_my_samples_form = RemoveFromMySamplesForm()

    def __change_structure(self):
        u"""Apply any layer-based rearrangements the user has requested.  This
        is layer duplication, order changes, appending of layers, and deletion.

        The method has two parts: First, the changes are collected in a data
        structure called ``new_layers``.  Then, I walk through ``new_layers``
        and build a new list ``self.layer_forms`` from it.

        ``new_layers`` is a list of small lists.  Every small list has a string
        as its zeroth element which may be ``"original"``, ``"duplicate"``, or
        ``"new"``, denoting the origin of that layer form.  The remainding
        elements are parameters: the (old) layer and change-layer form for
        ``"original"``; the source layer form for ``"duplicate"``; and the
        initial layer form data for ``"new"``.

        Of course, the new layer forms are not validated.  Therefore,
        `__is_all_valid` is called *after* this routine in `save_to_database`.

        Note that – as usual – the numbers of depositions and layers are called
        *number*, whereas the internal numbers used as prefixes in the HTML
        names are called *indices*.  The index (and thus prefix) of a layer
        form does never change (in contrast to the 6-chamber deposition, see
        `form_utils.normalize_prefixes`), not even across many “post cycles”.
        Only the layer numbers are used for determining the order of layers.

        :Return:
          whether the structure was changed in any way.

        :rtype: bool
        """
        structure_changed = False
        new_layers = [["original", layer_form, change_layer_form]
                      for layer_form, change_layer_form in zip(self.layer_forms, self.change_layer_forms)]

        # Move layers
        for i in range(len(new_layers)):
            layer_form, change_layer_form = new_layers[i][1:3]
            if change_layer_form.is_valid():
                movement = change_layer_form.cleaned_data["move_this_layer"]
                if movement:
                    new_layers[i][2] = ChangeLayerForm(prefix=layer_form.prefix)
                    structure_changed = True
                    if movement == "up" and i > 0:
                        temp = new_layers[i-1]
                        new_layers[i-1] = new_layers[i]
                        new_layers[i] = temp
                    elif movement == "down" and i < len(new_layers) - 1:
                        temp = new_layers[i]
                        new_layers[i] = new_layers[i+1]
                        new_layers[i+1] = temp

        # Duplicate layers
        for i in range(len(new_layers)):
            layer_form, change_layer_form = new_layers[i][1:3]
            if layer_form.is_valid() and \
                    change_layer_form.is_valid() and change_layer_form.cleaned_data["duplicate_this_layer"]:
                new_layers.append(("duplicate", layer_form))
                new_layers[i][2] = ChangeLayerForm(prefix=layer_form.prefix)
                structure_changed = True

        # Add layers
        if self.add_layers_form.is_valid():
            for i in range(self.add_layers_form.cleaned_data["number_of_layers_to_add"]):
                new_layers.append(("new", {}))
                structure_changed = True
            # Add MyLayer
            my_layer_data = self.add_layers_form.cleaned_data["my_layer_to_be_added"]
            if my_layer_data is not None:
                new_layers.append(("new", my_layer_data))
                structure_changed = True
            self.add_layers_form = form_utils.AddLayersForm(self.user_details, ipv_models.LargeAreaDeposition)

        # Delete layers
        for i in range(len(new_layers)-1, -1, -1):
            if len(new_layers[i]) == 3:
                change_layer_form = new_layers[i][2]
                if change_layer_form.is_valid() and change_layer_form.cleaned_data["remove_this_layer"]:
                    del new_layers[i]
                    structure_changed = True

        # Apply changes
        next_full_number = None
        if self.deposition:
            next_full_number = self.deposition.number[:4] + utils.three_digits(self.deposition.layers.all()[0].number)
        elif self.deposition_form.is_valid():
            match = self.deposition_number_pattern.match(self.deposition_form.cleaned_data["number"])
            if match:
                number_of_first_layer = int(match.group("number")) - (len(self.layer_forms) - 1 if self.layer_forms else 0)
                next_full_number = match.group("prefix") + utils.three_digits(number_of_first_layer)
        if not next_full_number:
            next_full_number = utils.get_next_deposition_number("L")
        deposition_number_match = self.deposition_number_pattern.match(next_full_number)
        next_layer_number = int(deposition_number_match.group("number"))
        old_prefixes = [int(layer_form.prefix) for layer_form in self.layer_forms if layer_form.is_bound]
        next_prefix = max(old_prefixes) + 1 if old_prefixes else 0
        self.layer_forms = []
        self.change_layer_forms = []
        for new_layer in new_layers:
            if new_layer[0] == "original":
                post_data = self.post_data.copy()
                prefix = new_layer[1].prefix
                post_data[prefix+"-number"] = utils.three_digits(next_layer_number)
                next_layer_number += 1
                self.layer_forms.append(LayerForm(post_data, prefix=prefix))
                self.change_layer_forms.append(new_layer[2])
            elif new_layer[0] == "duplicate":
                original_layer = new_layer[1]
                if original_layer.is_valid():
                    layer_data = original_layer.cleaned_data
                    layer_data["number"] = utils.three_digits(next_layer_number)
                    next_layer_number += 1
                    self.layer_forms.append(LayerForm(initial=layer_data, prefix=str(next_prefix)))
                    self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                    next_prefix += 1
            elif new_layer[0] == "new":
                initial = new_layer[1]
                initial["number"] = utils.three_digits(next_layer_number)
                self.layer_forms.append(LayerForm(initial=initial, prefix=str(next_prefix)))
                self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                next_layer_number += 1
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_layers structure: " + new_layer[0])
        # Finally, adjust the deposition number to the new number of layers.
        post_data = self.post_data.copy()
        post_data["number"] = deposition_number_match.group("prefix") + \
            utils.three_digits(next_layer_number - 1 if self.layer_forms else next_layer_number)
        self.deposition_form = DepositionForm(self.user, post_data, instance=self.deposition)

        return structure_changed

    def __is_all_valid(self):
        u"""Tests the “inner” validity of all forms belonging to this view.
        This function calls the ``is_valid()`` method of all forms, even if one
        of them returns ``False`` (and makes the return value clear
        prematurely).

        :Return:
          whether all forms are valid.

        :rtype: bool
        """
        all_valid = self.deposition_form.is_valid()
        all_valid = (self.add_layers_form.is_valid() or not self.add_layers_form.is_bound) and all_valid
        if not self.deposition:
            all_valid = self.remove_from_my_samples_form.is_valid() and all_valid
        if not self.deposition:
            all_valid = self.samples_form.is_valid() and all_valid
        all_valid = all([layer_form.is_valid() for layer_form in self.layer_forms]) and all_valid
        all_valid = all([(change_layer_form.is_valid() or not change_layer_form.is_bound)
                         for change_layer_form in self.change_layer_forms]) and all_valid
        return all_valid

    def __is_referentially_valid(self):
        u"""Test whether all forms are consistent with each other and with the
        database.  For example, no layer number must occur twice, and the
        deposition number must not exist within the database.

        Note that I test many situations here that cannot be achieved with
        using the browser because all number fields are read-only and thus
        inherently referentially valid.  However, the remote client (or a
        manipulated HTTP client) may be used in a malicious way, thus I have to
        test for *all* cases.

        :Return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if not self.layer_forms:
            append_error(self.deposition_form, _(u"No layers given."))
            referentially_valid = False
        if self.deposition_form.is_valid():
            match = self.deposition_number_pattern.match(self.deposition_form.cleaned_data["number"])
            deposition_prefix = match.group("prefix")
            number_only = int(match.group("number"))
            deposition_numbers = ipv_models.LargeAreaDeposition.objects.filter(
                number__startswith=deposition_prefix).values_list("number", flat=True).all()
            deposition_numbers = [int(number[len(deposition_prefix):]) for number in deposition_numbers]
            max_deposition_number = max(deposition_numbers) if deposition_numbers else 0
            if self.deposition:
                if self.layer_forms and self.layer_forms[0].is_valid() and \
                        self.layer_forms[0].cleaned_data["number"] != self.deposition.layers.all()[0].number:
                    append_error(self.deposition_form, _(u"You can't change the number of the first layer."))
                    referentially_valid = False
                old_number_only = int(self.deposition_number_pattern.match(self.deposition.number).group("number"))
                higher_deposition_numbers = [number for number in deposition_numbers if number > old_number_only]
                if higher_deposition_numbers:
                    next_number = min(higher_deposition_numbers)
                    number_of_next_layers = ipv_models.LargeAreaDeposition.objects.get(
                        number=deposition_prefix+utils.three_digits(next_number)).layers.count()
                    if number_only + number_of_next_layers > next_number:
                        append_error(self.deposition_form, _(u"New layers collide with following deposition."))
                        referentially_valid = False
            else:
                if self.layer_forms and self.layer_forms[0].is_valid() and \
                        self.layer_forms[0].cleaned_data["number"] <= max_deposition_number:
                    append_error(self.deposition_form, _(u"Overlap with previous deposition numbers."))
                    referentially_valid = False
            if self.samples_form.is_valid():
                dead_samples = form_utils.dead_samples(self.samples_form.cleaned_data["sample_list"],
                                                       self.deposition_form.cleaned_data["timestamp"])
                if dead_samples:
                    error_message = ungettext(u"The sample %s is already dead at this time.",
                                              u"The samples %s are already dead at this time.", len(dead_samples))
                    error_message %= utils.format_enumeration([sample.name for sample in dead_samples])
                    append_error(self.deposition_form, error_message, "timestamp")
                    referentially_valid = False
            for i, layer_form in enumerate(self.layer_forms):
                if layer_form.is_valid() and \
                        layer_form.cleaned_data["number"] - i + len(self.layer_forms) - 1 != number_only:
                    append_error(layer_form, _(u"Layer number is not consecutive."))
                    referentially_valid = False
        return referentially_valid

    def save_to_database(self):
        u"""Apply all layer changes, check the whole validity of the data, and
        save the forms to the database.  Only the deposition is just updated if
        it already existed.  However, the layers are completely deleted and
        re-constructed from scratch.

        :Return:
          The saved deposition object, or ``None`` if validation failed

        :rtype: `ipv_models.LargeAreaDeposition` or ``NoneType``
        """
        database_ready = not self.__change_structure() if not self.remote_client else True
        database_ready = self.__is_all_valid() and database_ready
        database_ready = self.__is_referentially_valid() and database_ready
        if database_ready:
            deposition = self.deposition_form.save()
            if not self.deposition:
                # Change sample list only for *new* depositions
                deposition.samples = self.samples_form.cleaned_data["sample_list"]
            deposition.layers.all().delete()
            for layer_form in self.layer_forms:
                layer = layer_form.save(commit=False)
                layer.deposition = deposition
                layer.save()
#             feed_utils.Reporter(self.user).report_physical_process(
#                 deposition, self.edit_description_form.cleaned_data if self.edit_description_form else None)
            return deposition

    def get_context_dict(self):
        u"""Retrieve the context dictionary to be passed to the template.  This
        context dictionary contains all forms in an easy-to-use format for the
        template code.

        :Return:
          context dictionary

        :rtype: dict mapping str to various types
        """
        return {"deposition": self.deposition_form, "samples": self.samples_form,
                "layers_and_change_layers": zip(self.layer_forms, self.change_layer_forms),
                "add_layers": self.add_layers_form, "remove_from_my_samples": self.remove_from_my_samples_form}


@login_required
def edit(request, deposition_number):
    u"""Edit or create a large-area deposition.  In case of creation, starting
    with a duplicate of another deposition is also possible if a ``copy-from``
    query string parameter is present (as for the other depositions).

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: number of the deposition to be edited/created.  If
        this number already exists, *edit* it, if not, *create* it.

    :type request: ``HttpRequest``
    :type deposition_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    form_set = FormSet(request, deposition_number)
    permissions.assert_can_add_edit_physical_process(request.user, form_set.deposition, ipv_models.LargeAreaDeposition)
    if request.method == "POST":
        form_set.from_post_data(request.POST)
        deposition = form_set.save_to_database()
        if deposition:
            if form_set.remove_from_my_samples_form and \
                    form_set.remove_from_my_samples_form.cleaned_data["remove_deposited_from_my_samples"]:
                utils.remove_samples_from_my_samples(deposition.samples.all(), form_set.user_details)
            if deposition_number:
                request.session["success_report"] = \
                    _(u"Deposition %s was successfully changed in the database.") % deposition.number
                return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse("samples.views.main.main_menu"))
            else:
                if utils.is_remote_client(request):
                    return utils.respond_to_remote_client(deposition.number)
                else:
                    request.session["success_report"] = \
                        _(u"Deposition %s was successfully added to the database.") % deposition.number
                    return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse(
                            "samples.views.split_after_deposition.split_and_rename_after_deposition",
                            kwargs={"deposition_number": deposition.number}))
    else:
        form_set.from_database(utils.parse_query_string(request))
    title = _(u"Large-area deposition “%s”") % deposition_number if deposition_number else _(u"Add large-area deposition")
    context_dict = {"title": title}
    context_dict.update(form_set.get_context_dict())
    return render_to_response("samples/edit_large_area_deposition.html",
                              context_dict, context_instance=RequestContext(request))


@login_required
def show(request, deposition_number):
    u"""Show an existing large-area_deposision.  You must be a large-area
    operator *or* be able to view one of the samples affected by this
    deposition in order to be allowed to view it.

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: the number (=name) or the deposition

    :type request: ``HttpRequest``
    :type deposition_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    deposition = get_object_or_404(ipv_models.LargeAreaDeposition, number=deposition_number)
    samples = deposition.samples
    permissions.assert_can_view_physical_process(request.user, deposition)
    template_context = {"title": _(u"Large-area deposition “%s”") % deposition.number, "samples": samples.all(),
                        "process": deposition}
    template_context.update(utils.ProcessContext(request.user).digest_process(deposition))
    return render_to_response("samples/show_process.html", template_context, context_instance=RequestContext(request))
