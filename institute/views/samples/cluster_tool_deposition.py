#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""All views and helper routines directly connected with the cluster
tool deposition system.  This includes adding, editing, and viewing such
processes.
"""

from __future__ import absolute_import, unicode_literals

import datetime
from django.shortcuts import get_object_or_404
from django import forms
from django.forms import widgets
from django.forms.util import ValidationError
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext, ungettext, ugettext_lazy
import jb_common.utils.base
from samples import models
import samples.utils.views as utils
import institute.utils.views as form_utils
import institute.utils.base
import institute.models as institute_models

_ = ugettext

class SimpleRadioSelectRenderer(widgets.RadioFieldRenderer):
    def render(self):
        return mark_safe("""<ul class="radio-select">\n{0}\n</ul>""".format("\n".join(
                    "<li>{0}</li>".format(force_text(w)) for w in self)))

new_layer_choices = (
    ("hot-wire", _("hot-wire")),
    ("PECVD", _("PECVD")),
    ("none", _("none")),
    )

class AddLayersForm(forms.Form):
    """Form for adding a new layer.  The user can choose between hot-wire
    layer, PECVD layer, Sputter layer and no layer, using a radio button.

    Alternatively, the user can give a layer nickname from “My Layers”.
    """
    _ = ugettext_lazy
    layer_to_be_added = forms.ChoiceField(label=_("Layer to be added"), required=False,
                                          widget=forms.RadioSelect(renderer=SimpleRadioSelectRenderer),
                                          choices=new_layer_choices)
    my_layer_to_be_added = forms.ChoiceField(label=_("Nickname of My Layer to be added"), required=False)

    def __init__(self, user_details, model, data=None, **kwargs):
        super(AddLayersForm, self).__init__(data, **kwargs)
        self.fields["my_layer_to_be_added"].choices = utils.get_my_layers(user_details, model)
        self.model = model

    def clean_my_layer_to_be_added(self):
        nickname = self.cleaned_data["my_layer_to_be_added"]
        if nickname and "-" in nickname:
            deposition_id, layer_number = self.cleaned_data["my_layer_to_be_added"].split("-")
            deposition_id, layer_number = int(deposition_id), int(layer_number)
            try:
                deposition = self.model.objects.get(pk=deposition_id)
            except self.model.DoesNotExist:
                pass
            else:
                layer_query = deposition.layers.filter(number=layer_number)
                if layer_query.count() == 1:
                    result = layer_query.values()[0]
                    layer = layer_query[0]
                    if hasattr(layer, "clustertoolhotwirelayer"):
                        result["layer_type"] = {"layer_type": "hot-wire"}
                    elif hasattr(layer, "clustertoolpecvdlayer"):
                        result["layer_type"] = {"layer_type": "PECVD"}
                    return result


class DepositionForm(utils.DepositionForm):
    """Model form for the basic deposition data.
    """
    class Meta:
        model = institute_models.ClusterToolDeposition
        fields = "__all__"

    def __init__(self, user, data=None, **kwargs):
        super(DepositionForm, self).__init__(user, data, **kwargs)

    def clean_number(self):
        number = super(DepositionForm, self).clean_number()
        return form_utils.clean_deposition_number_field(number, "C")

    def clean(self):
        _ = ugettext
        cleaned_data = super(DepositionForm, self).clean()
        if "number" in cleaned_data and "timestamp" in cleaned_data:
            if cleaned_data["number"][:2] != cleaned_data["timestamp"].strftime("%y"):
                self.add_error("number", _("The first two digits must match the year of the deposition."))
        return cleaned_data


class HotWireLayerForm(forms.ModelForm):
    """Model form for a hot-wire layer in the cluster tool."""

    layer_type = forms.CharField(widget=forms.HiddenInput, initial="hot-wire")
    """This is for being able to distinguish the form types; it is not given
    by the user, however, it is given by the remote client."""

    class Meta:
        model = institute_models.ClusterToolHotWireLayer
        exclude = ("deposition",)

    def __init__(self, user, data=None, **kwargs):
        """I do additional initialisation here, but very harmless: It's only about
        visual appearance and numerical limits.
        """
        super(HotWireLayerForm, self).__init__(data, **kwargs)
        self.type = "hot-wire"
        self.fields["comments"].widget.attrs["cols"] = "70"
        self.fields["comments"].widget.attrs["rows"] = "18"
        self.fields["number"].widget.attrs.update({"readonly": "readonly" , "size": "2",
                                                   "style": "text-align: center; font-size: xx-large"})
        for fieldname in ["time", "base_pressure"]:
            self.fields[fieldname].widget.attrs["size"] = "10"
        for fieldname in ["h2", "sih4"]:
            self.fields[fieldname].help_text = ""
            self.fields[fieldname].widget.attrs["size"] = "15"
        if not user.is_staff:
            self.fields["wire_material"].choices = \
                [choice for choice in self.fields["wire_material"].choices if choice[0] != "unknown"]
        # FixMe: Min/Max values?

    def clean_time(self):
        return utils.clean_time_field(self.cleaned_data["time"])

    def clean_comments(self):
        """Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        jb_common.utils.base.check_markdown(comments)
        return comments

    def clean_layer_type(self):
        """Assure that the hidden fixed string ``layer_type`` truely is
        ``"hot-wire"``.  When using a working browser, this should always be
        the case, no matter what the user does.  However, it must be checked
        nevertheless because other clients may send wrong data.
        """
        if self.cleaned_data["layer_type"] != "hot-wire":
            raise ValidationError("Layer type must be “hot-wire”.")
        return self.cleaned_data["layer_type"]


class PECVDLayerForm(forms.ModelForm):
    """Model form for a PECVD layer in a cluster tool deposition."""

    layer_type = forms.CharField(widget=forms.HiddenInput, initial="PECVD")
    """This is for being able to distinguish the form types; it is not given
    by the user, however, it is given by the remote client."""

    class Meta:
        model = institute_models.ClusterToolPECVDLayer
        exclude = ("deposition",)

    def __init__(self, user, data=None, **kwargs):
        """I do additional initialisation here, but very harmless: It's only about
        visual appearance and numerical limits.

        Note that the `user` parameter is not used here but this constructor
        must share its signature with that of :py:class:`HotWireLayerForm`.
        """
        super(PECVDLayerForm, self).__init__(data, **kwargs)
        self.type = "PECVD"
        self.fields["comments"].widget.attrs["cols"] = "70"
        self.fields["comments"].widget.attrs["rows"] = "18"
        self.fields["number"].widget.attrs.update({"readonly": "readonly" , "size": "2",
                                                   "style": "text-align: center; font-size: xx-large"})
        for fieldname in ["time", "deposition_power"]:
            self.fields[fieldname].widget.attrs["size"] = "10"

        for fieldname in ["h2", "sih4"]:
            self.fields[fieldname].help_text = ""
            self.fields[fieldname].widget.attrs["size"] = "15"

        for fieldname, min_value, max_value in [("deposition_power", 0, 1000)]:
            self.fields[fieldname].min_value = min_value
            self.fields[fieldname].max_value = max_value

    def clean_time(self):
        return utils.clean_time_field(self.cleaned_data["time"])

    def clean_comments(self):
        """Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        jb_common.utils.base.check_markdown(comments)
        return comments

    def clean_layer_type(self):
        """Assure that the hidden fixed string ``layer_type`` truely is
        ``"PECVD"``.  When using a working browser, this should always be the
        case, no matter what the user does.  However, it must be checked
        nevertheless because other clients may send wrong data.
        """
        if self.cleaned_data["layer_type"] != "PECVD":
            raise ValidationError("Layer type must be “PECVD”.")
        return self.cleaned_data["layer_type"]


class ChangeLayerForm(forms.Form):
    """Form for manipulating a layer.  Duplicating it (appending the
    duplicate), deleting it, and moving it up- or downwards.
    """
    _ = ugettext_lazy
    duplicate_this_layer = forms.BooleanField(label=_("duplicate this layer"), required=False)
    remove_this_layer = forms.BooleanField(label=_("remove this layer"), required=False)
    move_this_layer = forms.ChoiceField(label=_("move this layer"), required=False,
                                        choices=(("", "---------"), ("up", _("up")), ("down", _("down"))))

    def clean(self):
        _ = ugettext
        cleaned_data = super(ChangeLayerForm, self).clean()
        operations = 0
        if cleaned_data["duplicate_this_layer"]:
            operations += 1
        if cleaned_data["remove_this_layer"]:
            operations += 1
        if cleaned_data.get("move_this_layer"):
            operations += 1
        if operations > 1:
            raise ValidationError(_("You can't duplicate, move, or remove a layer at the same time."))
        return cleaned_data


class FormSet(object):
    """Class for holding all forms of the cluster tool deposition views,
    and for all methods working on these forms.

    :ivar deposition: the deposition to be edited.  If it is ``None``, we
      create a new one.  This is very important because testing ``deposition``
      is the only way to distinguish between editing or creating.

    :type deposition: `institute.models.ClusterToolDeposition` or NoneType
    """

    class LayerForm(forms.Form):
        """Dummy form class for detecting the actual layer type.  It is used
        only in `from_post_data`."""
        layer_type = forms.CharField()

    def __init__(self, request, deposition_number):
        """Note that I don't create the forms here – this is done later in
        `from_post_data` and in `from_database`.

        :param request: the current HTTP Request object
        :param deposition_number: number of the deposition to be edited/created.
            If this number already exists, *edit* it, if not, *create* it.

        :type request: HttpRequest
        :type deposition_number: unicode
        """
        self.user = request.user
        self.user_details = self.user.samples_user_details
        self.deposition = \
            get_object_or_404(institute_models.ClusterToolDeposition, number=deposition_number) if deposition_number else None
        self.deposition_form = None
        self.layer_forms = []
        self.remove_from_my_samples_form = None
        self.edit_description_form = None
        self.preset_sample = utils.extract_preset_sample(request) if not self.deposition else None
        self.post_data = None
        self.json_client = jb_common.utils.base.is_json_requested(request)

    def from_post_data(self, post_data):
        """Interpret the POST data and create bound forms for the layers.

        :param post_data: the result from ``request.POST``

        :type post_data: QueryDict
        """
        def get_layer_form(index):
            prefix = str(index)
            layer_form = self.LayerForm(self.post_data, prefix=prefix)
            # PECVDLayerForm is default.  This means that I let it handle all
            # errors.
            LayerFormClass = PECVDLayerForm
            if layer_form.is_valid() and layer_form.cleaned_data["layer_type"] == "hot-wire":
                LayerFormClass = HotWireLayerForm
            return LayerFormClass(self.user, self.post_data, prefix=prefix)

        self.post_data = post_data
        self.deposition_form = DepositionForm(self.user, self.post_data, instance=self.deposition)
        self.add_layers_form = AddLayersForm(self.user_details, institute_models.ClusterToolDeposition, self.post_data)
        if not self.deposition:
            self.remove_from_my_samples_form = utils.RemoveFromMySamplesForm(self.post_data)
        self.samples_form = \
            utils.DepositionSamplesForm(self.user, self.deposition, self.preset_sample, self.post_data)
        indices = utils.collect_subform_indices(self.post_data)
        self.layer_forms = [get_layer_form(layer_index) for layer_index in indices]
        self.change_layer_forms = [ChangeLayerForm(self.post_data, prefix=str(change_layer_index))
                                   for change_layer_index in indices]
        self.edit_description_form = utils.EditDescriptionForm(self.post_data) if self.deposition else None

    def from_database(self, query_dict):
        """Create all forms from database data.  This is used if the view was
        retrieved from the user with the HTTP GET method, so there hasn't been
        any post data submitted.

        I have to distinguish all three cases in this method: editing, copying,
        and duplication.

        :param query_dict: dictionary with all given URL query string parameters

        :type query_dict: dict mapping unicode to unicode
        """
        def build_layer_forms(deposition):
            """Construct the layer forms for the given deposition according to
            the data currently stored in the database.  Note that this method
            writes its products directly into the instance.

            :param deposition: the cluster tool deposition for which the
                layer and channel forms should be generated

            :type deposition: `institute.models.ClusterToolDeposition`
            """
            self.layer_forms = []
            for index, layer in enumerate(deposition.layers.all()):
                if hasattr(layer, "clustertoolhotwirelayer"):
                    self.layer_forms.append(HotWireLayerForm(self.user, prefix=str(index),
                                                             instance=layer.clustertoolhotwirelayer))
                else:
                    self.layer_forms.append(PECVDLayerForm(self.user, prefix=str(index),
                                                           instance=layer.clustertoolpecvdlayer))

        copy_from = query_dict.get("copy_from")
        if not self.deposition and copy_from:
            # Duplication of a deposition
            source_deposition_query = institute_models.ClusterToolDeposition.objects.filter(number=copy_from)
            if source_deposition_query.count() == 1:
                deposition_data = source_deposition_query.values()[0]
                deposition_data["timestamp"] = datetime.datetime.now()
                deposition_data["timestamp_inaccuracy"] = 0
                deposition_data["operator"] = self.user.pk
                deposition_data["number"] = institute.utils.base.get_next_deposition_number("C")
                self.deposition_form = DepositionForm(self.user, initial=deposition_data)
                build_layer_forms(source_deposition_query[0])
        if not self.deposition_form:
            if self.deposition:
                # Normal edit of existing deposition
                self.deposition_form = DepositionForm(self.user, instance=self.deposition)
                build_layer_forms(self.deposition)
            else:
                # New deposition, or duplication has failed
                self.deposition_form = DepositionForm(
                    self.user, initial={"number": institute.utils.base.get_next_deposition_number("C")})
                self.layer_forms, self.change_layer_forms = [], []
        self.samples_form = utils.DepositionSamplesForm(self.user, self.deposition, self.preset_sample)
        self.add_layers_form = AddLayersForm(self.user_details, institute_models.ClusterToolDeposition)
        self.change_layer_forms = [ChangeLayerForm(prefix=str(index)) for index in range(len(self.layer_forms))]
        if not self.deposition:
            self.remove_from_my_samples_form = utils.RemoveFromMySamplesForm()
        self.edit_description_form = utils.EditDescriptionForm() if self.deposition else None

    def _change_structure(self):
        """Apply any layer-based rearrangements the user has requested.  This
        is layer duplication, appending of layers, and deletion.

        The method has two parts: First, the changes are collected in a data
        structure called ``new_layers``.  Then, I walk through ``new_layers``
        and build a new list ``self.layer_forms`` from it.

        ``new_layers`` is a list of old lists.  Every old list has a string
        as its zeroth element which may be ``"original"``, ``"duplicate"``, or
        ``"new"``, denoting the origin of that layer form.  The remainding
        elements are parameters: the (old) layer and change-layer form for
        ``"original"``; the source layer form for ``"duplicate"``; and the
        initial layer form data for ``"new"``.

        Of course, the new layer forms are not validated.  Therefore,
        `_is_all_valid` is called *after* this routine in `save_to_database`.

        Note that – as usual – the numbers of depositions and layers are called
        *number*, whereas the internal numbers used as prefixes in the HTML
        names are called *indices*.  The index (and thus prefix) of a layer
        form does never change (in contrast to the 6-chamber deposition, see
        `samples.views.form_utils.normalize_prefixes`), not even across many
        “post cycles”.  Only the layer numbers are used for determining the
        order of layers.

        :return:
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
                        temp = new_layers[i - 1]
                        new_layers[i - 1] = new_layers[i]
                        new_layers[i] = temp
                    elif movement == "down" and i < len(new_layers) - 1:
                        temp = new_layers[i]
                        new_layers[i] = new_layers[i + 1]
                        new_layers[i + 1] = temp

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
            new_layer_type = self.add_layers_form.cleaned_data["layer_to_be_added"]
            if new_layer_type == "hot-wire":
                new_layers.append(("new hot-wire", {}))
                structure_changed = True
            elif new_layer_type == "PECVD":
                new_layers.append(("new PECVD", {}))
                structure_changed = True

            # Add MyLayer
            my_layer_data = self.add_layers_form.cleaned_data["my_layer_to_be_added"]
            if my_layer_data is not None:
                new_layers.append(("new", my_layer_data))
                structure_changed = True
            self.add_layers_form = AddLayersForm(self.user_details, institute_models.ClusterToolDeposition)

        # Delete layers
        for i in range(len(new_layers) - 1, -1, -1):
            if len(new_layers[i]) == 3:
                change_layer_form = new_layers[i][2]
                if change_layer_form.is_valid() and change_layer_form.cleaned_data["remove_this_layer"]:
                    del new_layers[i]
                    structure_changed = True

        # Apply changes
        old_prefixes = [int(layer_form.prefix) for layer_form in self.layer_forms if layer_form.is_bound]
        next_prefix = max(old_prefixes) + 1 if old_prefixes else 0
        self.layer_forms = []
        self.change_layer_forms = []
        for i, new_layer in enumerate(new_layers):
            if new_layer[0] == "original":
                original_layer = new_layer[1]
                if original_layer.type == "hot-wire":
                    LayerFormClass = HotWireLayerForm
                else:
                    LayerFormClass = PECVDLayerForm
                post_data = self.post_data.copy()
                prefix = new_layer[1].prefix
                post_data[prefix + "-number"] = str(i + 1)
                self.layer_forms.append(LayerFormClass(self.user, post_data, prefix=prefix))
                self.change_layer_forms.append(new_layer[2])
            elif new_layer[0] == "duplicate":
                original_layer = new_layer[1]
                if original_layer.is_valid():
                    if original_layer.type == "hot-wire":
                        LayerFormClass = HotWireLayerForm
                    else:
                        LayerFormClass = PECVDLayerForm
                    layer_data = original_layer.cleaned_data
                    layer_data["number"] = i + 1
                    self.layer_forms.append(LayerFormClass(self.user, initial=layer_data, prefix=str(next_prefix)))
                    self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                    next_prefix += 1
            elif new_layer[0] == "new":
                # New MyLayer
                initial = {}
                id_ = new_layer[1]["id"]
                layer_class = institute_models.ClusterToolLayer.objects.get(id=id_).content_type.model_class()
                if layer_class == institute_models.ClusterToolHotWireLayer:
                    LayerFormClass = HotWireLayerForm
                    initial = institute_models.ClusterToolHotWireLayer.objects.filter(id=id_).values()[0]
                else:
                    LayerFormClass = PECVDLayerForm
                    initial = institute_models.ClusterToolPECVDLayer.objects.filter(id=id_).values()[0]
                initial["number"] = i + 1
                self.layer_forms.append(LayerFormClass(self.user, initial=initial, prefix=str(next_prefix)))
                self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            elif new_layer[0] == "new hot-wire":
                self.layer_forms.append(HotWireLayerForm(self.user, initial={"number": "{0}".format(i + 1)}, prefix=str(next_prefix)))
                self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            elif new_layer[0] == "new PECVD":
                self.layer_forms.append(PECVDLayerForm(self.user, initial={"number": "{0}".format(i + 1)}, prefix=str(next_prefix)))
                self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_layers structure: " + new_layer[0])
        return structure_changed

    def _is_all_valid(self):
        """Tests the “inner” validity of all forms belonging to this view.  This
        function calls the ``is_valid()`` method of all forms, even if one of them
        returns ``False`` (and makes the return value clear prematurely).

        :return:
          whether all forms are valid, i.e. their ``is_valid`` method returns
          ``True``.

        :rtype: bool
        """
        valid = self.deposition_form.is_valid()
        if self.remove_from_my_samples_form:
            valid = self.remove_from_my_samples_form.is_valid() and valid
        valid = (self.edit_description_form.is_valid() if self.edit_description_form else True) and valid
        if self.samples_form.is_bound:
            valid = self.samples_form.is_valid() and valid
        # Don't use a generator expression here because I want to call ``is_valid``
        # for every form
        valid = all([layer_form.is_valid() for layer_form in self.layer_forms]) and valid
        return valid

    def _is_referentially_valid(self):
        """Test whether all forms are consistent with each other and with the
        database.

        :return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if self.deposition_form.is_valid() and self.samples_form.is_valid():
            dead_samples = utils.dead_samples(self.samples_form.cleaned_data["sample_list"],
                                              self.deposition_form.cleaned_data["timestamp"])
            if dead_samples:
                error_message = ungettext(
                    "The sample {samples} is already dead at this time.",
                    "The samples {samples} are already dead at this time.", len(dead_samples)).format(
                    samples=jb_common.utils.base.format_enumeration([sample.name for sample in dead_samples]))
                self.deposition_form.add_error("timestamp", error_message)
                referentially_valid = False
        if not self.layer_forms:
            self.deposition_form.add_error(None, _("No layers given."))
            referentially_valid = False
        return referentially_valid

    def save_to_database(self):
        """Save the forms to the database.  Only the deposition is just
        updated if it already existed.  However, the layers are completely
        deleted and re-constructed from scratch.

        Additionally, this method removed deposited samples from „My Samples“
        if appropriate, and it generates the feed entries.

        :return:
          The saved deposition object, or ``None`` if validation failed

        :rtype: `institute.models.ClusterToolDeposition` or NoneType
        """
        database_ready = not self._change_structure() if not self.json_client else True
        database_ready = self._is_all_valid() and database_ready
        database_ready = self._is_referentially_valid() and database_ready
        if database_ready:
            deposition = self.deposition_form.save()
            if self.samples_form.is_bound:
                deposition.samples = self.samples_form.cleaned_data["sample_list"]
            deposition.layers.all().delete()
            for layer_form in self.layer_forms:
                layer = layer_form.save(commit=False)
                layer.deposition = deposition
                layer.save()
            if self.remove_from_my_samples_form and \
                    self.remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(deposition.samples.all(), self.user)
            utils.Reporter(self.user).report_physical_process(
                deposition, self.edit_description_form.cleaned_data if self.edit_description_form else None)
            return deposition

    def get_context_dict(self):
        """Retrieve the context dictionary to be passed to the template.  This
        context dictionary contains all forms in an easy-to-use format for the
        template code.

        :return:
          context dictionary

        :rtype: dict mapping str to various types
        """
        return {"deposition": self.deposition_form, "samples": self.samples_form,
                "layers_and_change_layers": list(zip(self.layer_forms, self.change_layer_forms)),
                "add_layers": self.add_layers_form, "remove_from_my_samples": self.remove_from_my_samples_form,
                "edit_description": self.edit_description_form}


@login_required
def edit(request, number):
    """Central view for editing, creating, and duplicating cluster tool
    depositions.  If ``number`` is ``None``, a new depositon is
    created (possibly by duplicating another one).

    :param request: the HTTP request object
    :param number: the number (=name) or the deposition

    :type request: QueryDict
    :type number: unicode or NoneType

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    return form_utils.edit_depositions(request, number, FormSet(request, number), institute_models.ClusterToolDeposition,
                                       "samples/edit_cluster_tool_deposition.html")
