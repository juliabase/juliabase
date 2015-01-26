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

from django import forms
from django.forms import widgets
from django.forms.util import ValidationError
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _, ugettext
import jb_common.utils.base
from samples import models
import samples.utils.views as utils
import institute.utils.views as form_utils
import institute.utils.base
import institute.models as institute_models


class SimpleRadioSelectRenderer(widgets.RadioFieldRenderer):
    def render(self):
        return mark_safe("""<ul class="radio-select">\n{0}\n</ul>""".format("\n".join(
                    "<li>{0}</li>".format(force_text(w)) for w in self)))


class AddMultipleTypeLayersForm(utils.AddMyLayersForm):
    """Form for adding a new layer.  The user can choose between hot-wire
    layer, PECVD layer, Sputter layer and no layer, using a radio button.

    Alternatively, the user can give a layer nickname from “My Layers”.
    """
    layer_to_be_added = forms.ChoiceField(label=_("Layer to be added"), required=False,
                                          widget=forms.RadioSelect(renderer=SimpleRadioSelectRenderer))

    def __init__(self, view, data=None, **kwargs):
        super(AddMultipleTypeLayersForm, self).__init__(view, data, **kwargs)
        # Translators: No further layer
        self.fields["layer_to_be_added"].choices = view.new_layer_choices + (("none", _("none")),)
        self.new_layer_choices = view.new_layer_choices

    def change_structure(self, structure_changed, new_layers):
        structure_changed, new_layers = super(AddMultipleTypeLayersForm, self).change_structure(structure_changed, new_layers)
        new_layer_type = self.cleaned_data["layer_to_be_added"]
        if new_layer_type:
            new_layers.append(("new " + new_layer_type, {}))
            structure_changed = True
        return structure_changed, new_layers


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
        cleaned_data = super(DepositionForm, self).clean()
        if "number" in cleaned_data and "timestamp" in cleaned_data:
            if cleaned_data["number"][:2] != cleaned_data["timestamp"].strftime("%y"):
                self.add_error("number", _("The first two digits must match the year of the deposition."))
        return cleaned_data


class HotWireLayerForm(forms.ModelForm):
    """Model form for a hot-wire layer in the cluster tool."""

    layer_type = forms.CharField(widget=forms.HiddenInput, initial="clustertoolhotwirelayer")
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
        self.type = "clustertoolhotwirelayer"
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
        ``"clustertoolhotwirelayer"``.  When using a working browser, this should always be
        the case, no matter what the user does.  However, it must be checked
        nevertheless because other clients may send wrong data.
        """
        if self.cleaned_data["layer_type"] != "clustertoolhotwirelayer":
            raise ValidationError("Layer type must be “hot-wire”.")
        return self.cleaned_data["layer_type"]


class PECVDLayerForm(forms.ModelForm):
    """Model form for a PECVD layer in a cluster tool deposition."""

    layer_type = forms.CharField(widget=forms.HiddenInput, initial="clustertoolpecvdlayer")
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
        self.type = "clustertoolpecvdlayer"
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
        ``"clustertoolpecvdlayer"``.  When using a working browser, this should always be the
        case, no matter what the user does.  However, it must be checked
        nevertheless because other clients may send wrong data.
        """
        if self.cleaned_data["layer_type"] != "clustertoolpecvdlayer":
            raise ValidationError("Layer type must be “PECVD”.")
        return self.cleaned_data["layer_type"]


class EditView(utils.RemoveFromMySamplesMixin, utils.DepositionView):
    model = institute_models.ClusterToolDeposition
    form_class = DepositionForm
    layer_form_classes = (HotWireLayerForm, PECVDLayerForm)
    short_labels = {HotWireLayerForm: _("hot-wire"), PECVDLayerForm: _("PECVD")}
    add_layers_form_class = AddMultipleTypeLayersForm

    class LayerForm(forms.Form):
        """Dummy form class for detecting the actual layer type.  It is used
        only in `from_post_data`."""
        layer_type = forms.CharField()

    def __init__(self, **kwargs):
        super(EditView, self).__init__(**kwargs)
        if not self.short_labels:
            self.short_labels = {cls: cls.Meta.model._meta.verbose_name for cls in self.layer_form_classes}
        self.new_layer_choices = tuple((cls.Meta.model.__name__.lower(), self.short_labels[cls])
                                       for cls in self.layer_form_classes)
        self.layer_types = {cls.Meta.model.__name__.lower(): cls for cls in self.layer_form_classes}

    def _read_layer_forms(self, source_deposition):
        self.forms["layers"] = []
        for index, layer in enumerate(source_deposition.layers.all()):
            LayerFormClass = self.layer_types[layer.content_type.model_class().__name__.lower()]
            self.forms["layers"] = LayerFormClass(prefix=str(layer_index), instance=layer,
                                                  initial={"number": layer_index + 1})

    def get_layer_form(self, prefix):
        layer_form = self.LayerForm(self.data, prefix=prefix)
        LayerFormClass = self.layer_form_classes[0]   # default
        if layer_form.is_valid():
            layer_type = layer_form.cleaned_data["layer_type"]
            try:
                LayerFormClass = self.layer_types[layer_type]
            except KeyError:
                pass
        return LayerFormClass(self.request.user, self.data, prefix=prefix)

    def _apply_changes(self, new_layers):
        old_prefixes = [int(layer_form.prefix) for layer_form in self.forms["layers"] if layer_form.is_bound]
        next_prefix = max(old_prefixes) + 1 if old_prefixes else 0
        self.forms["layers"] = []
        self.forms["change_layers"] = []
        for i, new_layer in enumerate(new_layers):
            if new_layer[0] == "original":
                original_layer = new_layer[1]
                LayerFormClass = self.layer_types[original_layer.type]
                post_data = self.data.copy() if self.data else {}
                prefix = new_layer[1].prefix
                post_data[prefix + "-number"] = str(i + 1)
                self.forms["layers"].append(LayerFormClass(self.request.user, post_data, prefix=prefix))
                self.forms["change_layers"].append(new_layer[2])
            elif new_layer[0] == "duplicate":
                original_layer = new_layer[1]
                if original_layer.is_valid():
                    LayerFormClass = self.layer_types[original_layer.type]
                    layer_data = original_layer.cleaned_data
                    layer_data["number"] = i + 1
                    self.forms["layers"].append(LayerFormClass(self.request.user, initial=layer_data,
                                                               prefix=str(next_prefix)))
                    self.forms["change_layers"].append(utils.ChangeLayerForm(prefix=str(next_prefix)))
                    next_prefix += 1
            elif new_layer[0] == "new":
                # New MyLayer
                initial = {}
                id_ = new_layer[1]["id"]
                layer_class = models.Layer.objects.get(id=id_).content_type.model_class()
                LayerFormClass = self.layer_types[layer_class.__name__.lower()]
                initial = layer_class.objects.filter(id=id_).values()[0]
                initial["number"] = i + 1
                self.forms["layers"].append(LayerFormClass(self.request.user, initial=initial, prefix=str(next_prefix)))
                self.forms["change_layers"].append(utils.ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            elif new_layer[0].startswith("new "):
                LayerFormClass = self.layer_types[new_layer[0][len("new "):]]
                self.forms["layers"].append(LayerFormClass(self.request.user, initial={"number": "{0}".format(i + 1)},
                                                           prefix=str(next_prefix)))
                self.forms["change_layers"].append(utils.ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_layers structure: " + new_layer[0])

    def get_next_id(self):
        return institute.utils.base.get_next_deposition_number("C")


_ = ugettext
