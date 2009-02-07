#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""All views and helper routines directly connected with the small cluster
tool deposition system.  This includes adding, editing, and viewing such
processes.
"""

class RemoveFromMySamplesForm(forms.Form):
    u"""Form class for one single checkbox for removing deposited samples from
    “My Samples”.
    """
    _ = ugettext_lazy
    remove_deposited_from_my_samples = forms.BooleanField(label=_(u"Remove deposited samples from My Samples"),
                                                          required=False, initial=True)


new_layer_choices = (
    ("hotwire", _(u"hotwire")),
    ("PECVD", _(u"PECVD")),
    ("none", _(u"none")),
    )
    
class AddLayersForm(forms.Form):
    u"""Form for adding a new layer.  The user can choose between hotwire
    layer, PECVD layer, and no layer, using a radio button.

    Alternatively, the user can give a layer nickname from “My Layers”.
    """
    _ = ugettext_lazy
    layer_to_be_added = forms.ChoiceField(label=_(u"Layer to be added"), required=False, widget=forms.RadioSelect,
                                          choices=new_layer_choices)
    my_layer_to_be_added = forms.ChoiceField(label=_(u"Nickname of My Layer to be added"), required=False)

    def __init__(self, user_details, model, data=None, **kwargs):
        super(AddLayersForm, self).__init__(data, **kwargs)
        self.fields["my_layer_to_be_added"].choices = form_utils.get_my_layers(user_details, model)
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
                    layer = layer_query.all()[0]
                    result["layer_type"] = \
                        {"layer_type": "hotwire" if hasattr(layer, "smallclustertoolhotwirelayer") else "PECVD"}
                    return result

    
class DepositionForm(form_utils.ProcessForm):
    u"""Model form for the basic deposition data.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_(u"Operator"))

    def __init__(self, user, data=None, **kwargs):
        u"""Form constructor.  I have to initialise a couple of things here,
        especially ``operator`` because I overrode it.
        """
        deposition = kwargs.get("instance")
        super(DepositionForm, self).__init__(data, **kwargs)
        self.fields["operator"].set_operator(user if not deposition else deposition.operator, user.is_staff)
        self.fields["operator"].initial = deposition.operator.pk if deposition else user.pk

    def clean_number(self):
        return form_utils.clean_deposition_number_field(self.cleaned_data["number"], "C")

    def clean(self):
        _ = ugettext
        if "number" in self.cleaned_data and "timestamp" in self.cleaned_data:
            if int(self.cleaned_data["number"][:2]) != self.cleaned_data["timestamp"].year % 100:
                form_utils.append_error(self, _(u"The first two digits must match the year of the deposition."), "number")
                del self.cleaned_data["number"]
        return self.cleaned_data

    class Meta:
        model = SmallClusterToolDeposition


class HotwireLayerForm(forms.ModelForm):
    u"""Model form for a hotwire layer in the small cluster tool."""

    layer_type = forms.CharField(widget=forms.HiddenInput, initial=u"hotwire")
    u"""This is for being able to distinguish the form types; it is not given
    by the user, however, it is given by the remote client."""

    def __init__(self, data=None, **kwargs):
        u"""Model form constructor.  I do additional initialisation here, but
        very harmless: It's only about visual appearance and numerical limits.
        """
        super(HotwireLayerForm, self).__init__(data, **kwargs)
        self.fields["number"].widget.attrs.update({"size": "2", "style": "text-align: center; font-size: xx-large"})
        self.fields["comments"].widget.attrs["cols"] = "30"
        for fieldname in ["pressure", "time", "substrate_wire_distance", "transfer_in_chamber", "pre_heat",
                          "gas_pre_heat_gas", "gas_pre_heat_pressure", "gas_pre_heat_time", "heating_temperature",
                          "transfer_out_of_chamber", "filament_temperature", "current", "voltage", "wire_material",
                          "base_pressure"]:
            self.fields[fieldname].widget.attrs["size"] = "10"
        # FixMe: Min/Max values?

    def clean_time(self):
        return form_utils.clean_time_field(self.cleaned_data["time"])

    def clean_pre_heat(self):
        return form_utils.clean_time_field(self.cleaned_data["pre_heat"])

    def clean_gas_pre_heat_time(self):
        return form_utils.clean_time_field(self.cleaned_data["gas_pre_heat_time"])

    def clean_pressure(self):
        return form_utils.clean_quantity_field(self.cleaned_data["pressure"], ["mTorr", "mbar", "Torr", "hPa"])

    def clean_gas_pre_heat_pressure(self):
        return form_utils.clean_quantity_field(self.cleaned_data["gas_pre_heat_pressure"], ["Torr"])

    def clean_comments(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        form_utils.check_markdown(comments)
        return comments

    def clean_layer_type(self):
        u"""Assure that the hidden fixed string ``layer_type`` truely is
        ``"hotwire"``.  When using a working browser, this should always be the
        case, no matter what the user does.  However, it must be checked
        nevertheless because other clients may send wrong data.
        """
        if self.cleaned_data["layer_type"] != u"hotwire":
            raise ValidationError(u"Layer type must be “hotwire”.")

    class Meta:
        model = models.SmallClusterToolHotwireLayer
        exclude = ("deposition", "number")


class PECVDLayerForm(forms.ModelForm):
    u"""Model form for a PECVD layer in a small cluster tool deposition."""

    layer_type = forms.CharField(widget=forms.HiddenInput, initial="PECVD")
    u"""This is for being able to distinguish the form types; it is not given
    by the user, however, it is given by the remote client."""

    def __init__(self, data=None, **kwargs):
        u"""Model form constructor.  I do additional initialisation here, but
        very harmless: It's only about visual appearance and numerical limits.
        """
        super(PECVDLayerForm, self).__init__(data, **kwargs)
        self.fields["number"].widget.attrs.update({"size": "2", "style": "text-align: center; font-size: xx-large"})
        self.fields["comments"].widget.attrs["cols"] = "30"
        for fieldname in ["pressure", "time", "substrate_electrode_distance", "transfer_in_chamber", "pre_heat",
                          "gas_pre_heat_gas", "gas_pre_heat_pressure", "gas_pre_heat_time", "heating_temperature",
                          "transfer_out_of_chamber", "plasma_start_power",
                          "deposition_frequency", "deposition_power", "base_pressure"]:
            self.fields[fieldname].widget.attrs["size"] = "10"
        for fieldname, min_value, max_value in [("deposition_frequency", 13, 150), ("plasma_start_power", 0, 1000),
                                                ("deposition_power", 0, 1000)]:
            self.fields[fieldname].min_value = min_value
            self.fields[fieldname].max_value = max_value

    def clean_time(self):
        return form_utils.clean_time_field(self.cleaned_data["time"])

    def clean_pre_heat(self):
        return form_utils.clean_time_field(self.cleaned_data["pre_heat"])

    def clean_gas_pre_heat_time(self):
        return form_utils.clean_time_field(self.cleaned_data["gas_pre_heat_time"])

    def clean_pressure(self):
        return form_utils.clean_quantity_field(self.cleaned_data["pressure"], ["mTorr", "mbar", "Torr", "hPa"])

    def clean_gas_pre_heat_pressure(self):
        return form_utils.clean_quantity_field(self.cleaned_data["gas_pre_heat_pressure"], ["Torr"])

    def clean_comments(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        form_utils.check_markdown(comments)
        return comments

    def clean_layer_type(self):
        u"""Assure that the hidden fixed string ``layer_type`` truely is
        ``"PECVD"``.  When using a working browser, this should always be the
        case, no matter what the user does.  However, it must be checked
        nevertheless because other clients may send wrong data.
        """
        if self.cleaned_data["layer_type"] != u"PECVD":
            raise ValidationError(u"Layer type must be “PECVD”.")

    class Meta:
        model = models.SmallClusterToolPECVDLayer
        exclude = ("deposition", "number")


class ChangeLayerForm(forms.Form):
    u"""Form for manipulating a layer.  Duplicating it (appending the
    duplicate), deleting it, and moving it up- or downwards.
    """
    _ = ugettext_lazy
    duplicate_this_layer = forms.BooleanField(label=_(u"duplicate this layer"), required=False)
    remove_this_layer = forms.BooleanField(label=_(u"remove this layer"), required=False)
    move_this_layer = forms.ChoiceField(label=_(u"move this layer"), required=False,
                                        choices=(("", _(9*u"-")), ("up", _(u"up")), ("down", _(u"down"))))

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
    u"""Class for holding all forms of the small cluster tool deposition views,
    and for all methods working on these forms.

    :ivar deposition: the deposition to be edited.  If it is ``None``, we
      create a new one.  This is very important because testing ``deposition``
      is the only way to distinguish between editing or creating.

    :type deposition: `models.SmallClusterToolDeposition` or ``NoneType``
    """

    class LayerForm(forms.ModelForm):
        u"""Dummy form class for detecting the actual layer type.  It is used
        only in `from_post_data`."""
        layer_type = forms.CharField()

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
            get_object_or_404(models.SmallClusterToolDeposition, number=deposition_number) if deposition_number else None
        self.deposition_form = None
        self.layer_forms = []
        self.edit_description_form = None
        self.preset_sample = utils.extract_preset_sample(request) if not self.deposition else None
        self.post_data = None
        self.remote_client = utils.is_remote_client(request)

    def from_post_data(self, post_data):
        u"""Interpret the POST data and create bound forms for the layers.

        :Parameters:
          - `post_data`: the result from ``request.POST``

        :type post_data: ``QueryDict``
        """
        def get_layer_form(index):
            prefix = str(index)
            layer_form = self.LayerForm(self.post_data, prefix=prefix)
            if layer_form.is_valid() and layer_form.cleaned_data["layer_type"] == "hotwire":
                return HotwireLayerForm(self.post_data, prefix=prefix)
            else:
                # Note that all error cases (e.g. no ``layer_type`` given) also
                # ends up here.  I let the form class handle all further
                # errors.
                return PECVDLayerForm(self.post_data, prefix=prefix)

        self.post_data = post_data
        self.deposition_form = DepositionForm(self.user, self.post_data, instance=self.deposition)
        self.add_layers_form = form_utils.AddLayersForm(self.user_details, models.SmallClusterToolDeposition, self.post_data)
        if not self.deposition:
            self.remove_from_my_samples_form = RemoveFromMySamplesForm(self.post_data)
        self.samples_form = \
            form_utils.DepositionSamplesForm(self.user_details, self.preset_sample, self.deposition, self.post_data)
        indices = form_utils.collect_subform_indices(self.post_data)
        self.layer_forms = [get_layer_form(layer_index) for layer_index in indices]
        self.change_layer_forms = [ChangeLayerForm(self.post_data, prefix=str(change_layer_index))
                                   for change_layer_index in indices]
        self.edit_description_form = form_utils.EditDescriptionForm(self.post_data) if self.deposition else None

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
        def build_layer_and_channel_forms(deposition):
            u"""Construct the layer forms for the given deposition according to
            the data currently stored in the database.  Note that this method
            writes its products directly into the instance.

            :Parameters:
              - `deposition`: the small cluster tool deposition for which the
                layer and channel forms should be generated

            :type deposition: `models.SmallClusterToolDeposition`
            """
            self.layer_forms = []
            for index, layer in enumerate(deposition.layers.all()):
                if hasattr(layer, "smallclustertoolhotwirelayer"):
                    self.layer_forms.append(HotwireLayerForm(prefix=str(index), instance=layer.smallclustertoolhotwirelayer))
                else:
                    self.layer_forms.append(PECVDLayerForm(prefix=str(index), instance=layer.smallclustertoolpecvdlayer))

        copy_from = query_dict.get("copy_from")
        if not self.deposition and copy_from:
            # Duplication of a deposition
            source_deposition_query = models.SmallClusterToolDeposition.objects.filter(number=copy_from)
            if source_deposition_query.count() == 1:
                deposition_data = source_deposition_query.values()[0]
                deposition_data["timestamp"] = datetime.datetime.now()
                deposition_data["operator"] = self.user.pk
                deposition_data["number"] = utils.get_next_deposition_number("C")
                self.deposition_form = DepositionForm(self.user, initial=deposition_data)
                self.build_layer_and_channel_forms(source_deposition_query.all()[0])
        if not self.deposition_form:
            if self.deposition:
                # Normal edit of existing deposition
                self.deposition_form = DepositionForm(self.user, instance=self.deposition)
                self.build_layer_and_channel_forms(self.deposition)
            else:
                # New deposition, or duplication has failed
                self.deposition_form = DepositionForm(
                    self.user, initial={"operator": self.user.pk, "timestamp": datetime.datetime.now(),
                                        "number": utils.get_next_deposition_number("C")})
                self.layer_forms, self.change_layer_forms = [], []
        self.samples_form = form_utils.DepositionSamplesForm(self.user_details, self.preset_sample, self.deposition)
        self.add_layers_form = form_utils.AddLayersForm(self.user_details, models.SmallClusteToolDeposition)
        self.change_layer_forms = [ChangeLayerForm(prefix=str(index)) for index in range(len(self.layer_forms))]
        if not self.deposition:
            self.remove_from_my_samples_form = RemoveFromMySamplesForm()
        self.edit_description_form = form_utils.EditDescriptionForm() if self.deposition else None

    def _change_structure(self):
        u"""Apply any layer-based rearrangements the user has requested.  This
        is layer duplication, appending of layers, and deletion.

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
        `_is_all_valid` is called *after* this routine in `save_to_database`.

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
            new_layer_type = self.add_layers_form.cleaned_data["layer_to_be_added"]
            if new_layer_type == "hotwire":
                new_layers.append(("new hotwire", {}))
                structure_changed = True
            elif new_layer_type == "PECVD":
                new_layers.append(("new PECVD", {}))
                structure_changed = True

            # Add MyLayer
            my_layer_data = self.add_layers_form.cleaned_data["my_layer_to_be_added"]
            if my_layer_data is not None:
                new_layers.append(("new", my_layer_data))
                structure_changed = True
            self.add_layers_form = form_utils.AddLayersForm(self.user_details, models.SmallClusterToolDeposition)

        # Delete layers
        for i in range(len(new_layers)-1, -1, -1):
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
        for new_layer in new_layers:
            if new_layer[0] == "original":
                self.layer_forms.append(LayerForm(post_data, prefix=prefix))
                self.change_layer_forms.append(new_layer[2])
            elif new_layer[0] == "duplicate":
                original_layer = new_layer[1]
                if original_layer.is_valid():
                    layer_data = original_layer.cleaned_data
                    self.layer_forms.append(LayerForm(initial=layer_data, prefix=str(next_prefix)))
                    self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                    next_prefix += 1
            elif new_layer[0] == "new":
                # New MyLayer
                initial = new_layer[1]
                FormClass = HotwireLayerForm if initial.layer_type == "hotwire" else PECVDLayerForm
                self.layer_forms.append(FormClass(initial=initial, prefix=str(next_prefix)))
                self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            elif new_layer[0] == "new hotwire":
                self.layer_forms.append(HotwireLayerForm(prefix=str(next_prefix)))
                self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            elif new_layer[0] == "new PECVD":
                self.layer_forms.append(PECVDLayerForm(prefix=str(next_prefix)))
                self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_layers structure: " + new_layer[0])
        return structure_changed

    def __is_all_valid(self):
        u"""Tests the “inner” validity of all forms belonging to this view.  This
        function calls the ``is_valid()`` method of all forms, even if one of them
        returns ``False`` (and makes the return value clear prematurely).

        :Return:
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
        valid = valid and all([layer_form.is_valid() for layer_form in self.layer_forms])
        return valid

    def __is_referentially_valid(self):
        u"""Test whether all forms are consistent with each other and with the
        database.  For example, the deposition number must not exist within the
        database.

        :Return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if self.deposition_form.is_valid():
            # FixMe: Doesn't the ModelForm check already for duplicates here?
            # (Or does overriding "clean_deposition_number" spoil it?)
            if (not self.deposition or self.deposition.number != self.deposition_form.cleaned_data["number"]) and \
                    models.Deposition.objects.filter(number=self.deposition_form.cleaned_data["number"]).count():
                form_utils.append_error(self.deposition_form, _(u"This deposition number exists already."))
                referentially_valid = False
            if self.samples_form.is_valid():
                dead_samples = form_utils.dead_samples(self.samples_form.cleaned_data["sample_list"],
                                                       self.deposition_form.cleaned_data["timestamp"])
                if dead_samples:
                    error_message = ungettext(u"The sample %s is already dead at this time.",
                                              u"The samples %s are already dead at this time.", len(dead_samples))
                    error_message %= utils.format_enumeration([sample.name for sample in dead_samples])
                    form_utils.append_error(self.deposition_form, error_message, "timestamp")
                    referentially_valid = False
        if not self.layer_forms:
            form_utils.append_error(self.deposition_form, _(u"No layers given."))
            referentially_valid = False
        return referentially_valid

    def save_to_database(self):
        u"""Save the forms to the database.  Only the deposition is just
        updated if it already existed.  However, the layers are completely
        deleted and re-constructed from scratch.

        Additionally, this method removed deposited samples from „My Samples“
        if appropriate, and it generates the feed entries.

        :Return:
          The saved deposition object, or ``None`` if validation failed

        :rtype: `models.SmallClusterToolDeposition` or ``NoneType``
        """
        database_ready = not self.__change_structure() if not self.remote_client else True
        database_ready = self.__is_all_valid() and database_ready
        database_ready = self.__is_referentially_valid() and database_ready
        if database_ready:
            deposition = self.deposition_form.save()
            if self.samples_form.is_bound:
                deposition.samples = self.samples_form.cleaned_data["sample_list"]
            deposition.layers.all().delete()
            for i, layer_form in enumerate(self.layer_forms):
                layer = layer_form.save(commit=False)
                layer.number = i + 1
                layer.deposition = deposition
                layer.save()
            if self.remove_from_my_samples_form and \
                    self.remove_from_my_samples_form.cleaned_data["remove_deposited_from_my_samples"]:
                utils.remove_samples_from_my_samples(deposition.samples.all(), self.user_details)
            feed_utils.Reporter(self.user).report_physical_process(
                deposition, self.edit_description_form.cleaned_data if self.edit_description_form else None)
            return deposition

    def get_context_dict(self):
        u"""Retrieve the context dictionary to be passed to the template.  This
        context dictionary contains all forms in an easy-to-use format for the
        template code.

        :Return:
          context dictionary

        :rtype: dict mapping str to various types
        """
        return {"deposition": self.deposition_form, "samples": self.samples_form, "layers": self.layer_forms,
                "add_my_layer": self.add_my_layer_form, "remove_from_my_samples": self.remove_from_my_samples_form,
                "edit_description": self.edit_description_form}
