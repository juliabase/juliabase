# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2022 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


"""This module contains the sample details and associated models.  In
particular, it contains the informal layer stacks.
"""

import os.path
from django.utils.translation import gettext_lazy as _, gettext, pgettext_lazy
from django.db import models
import django.urls
from django import forms
from django.forms.utils import ValidationError
from django.forms.models import inlineformset_factory
from jb_common import search, model_fields
import jb_common.utils.base
from samples.data_tree import DataNode, DataItem
import samples.models


class SampleDetails(models.Model, samples.models.GraphEntity):
    """Model for sample details.  It extends the ``Sample`` model as
    ``UserDetails`` extends ``User``, i.e. through a one-to-one relationship.
    Apart form this, it must contain a `get_context_for_user` method.  The
    rest is optional, however, you must take care of proper cache invalidation
    so that the user doesn't get an outdated sample data sheet when this model
    or depending models are updated.
    """
    sample = models.OneToOneField(samples.models.Sample, models.CASCADE, verbose_name=_("sample"),
                                  related_name="sample_details", primary_key=True)

    class Meta:
        verbose_name = _("sample details")
        verbose_name_plural = pgettext_lazy("plural", "sample details")

    def __str__(self):
        return str(self.sample)

    def save(self, *args, **kwargs):
        """Saves the object to the database.  I touch the associated sample,
        too, so that it is marked as updated and the cache is cleaned up
        properly.
        """
        super().save(*args, **kwargs)
        # I cannot use ``self.sample`` because it may be outdated (changed
        # through another instance of it in the view).
        samples.models.Sample.objects.get(id=self.sample.id).save(with_relations=False)

    def get_stack_diagram_locations(self):
        """Returns the locations of the stack diagram files.  This is also needed in
        :py:mod:`institute.views.samples.stack`, therefore, it is not part of
        `get_context_for_user`.

        :return:
          a dictionary containing the following keys:

          =========================  =========================================
                 key                           meaning
          =========================  =========================================
          ``"diagram_file"``         full path to the PDF diagram file
          ``"diagram_url"``          full relative URL to the diagram (i.e.,
                                     without domain)
          ``"thumbnail_file"``       full path to the thumbnail file
          ``"thumbnail_url"``        full relative URL to the thumbnail
          =========================  =========================================

        :rtype: dict mapping str to str
        """
        return {"diagram_file": os.path.join("stacks", str(self.pk) + ".pdf"),
                "diagram_url": django.urls.reverse("institute:stack_diagram", kwargs={"sample_id": str(self.pk)}),
                "thumbnail_file": os.path.join("stacks", str(self.pk) + ".png"),
                "thumbnail_url": django.urls.reverse("institute:stack_diagram_thumbnail", kwargs={"sample_id": str(self.pk)})}

    def has_producible_stack_diagram(self):
        """Returns whether it is possible to print a stack diagram for this
        sample.  Currently, this is possible if at least one onformal layer is
        verified by a user.  Note that this method hits the database, so cache
        its result if applicable.

        :return:
          whether a stack diagram should be printed for this sample.

        :rtype: bool
        """
        return self.informal_layers.filter(verified=True).exists()

    def get_context_for_user(self, user, old_context):
        """Create the context dict for these sample details, or fill missing
        fields, or adapt existing fields to the given user.  Note that adaption
        only happens to the current user and not to any settings like
        e.g. language.  In other words, if a non-empty `old_context` is passed,
        the caller must assure that language etc is already correct, just that
        it may be a cached context from another user with different
        permissions.

        A process context has always the following fields: ``sample``,
        ``is_my_sample_form``, ``clearance``, ``can_add_process``,
        ``can_edit``, ``id_for_rename``.  See ``sample.py`` in
        JuliaBase-samples for the related code.

        :param user: the currently logged-in user
        :param old_context: the sample context as it was in the cache or newly
            build.  This dictionary will not be touched in this method.

        :type user: django.contrib.auth.models.User
        :type old_context: dict mapping str to ``object``

        :return:
          the adapted full context for the sample

        :rtype: dict mapping str to ``object``
        """
        context = old_context.copy()
        context["sample_details"] = self
        plot_locations = self.get_stack_diagram_locations()
        if self.has_producible_stack_diagram():
            context["informal_stack_url"] = plot_locations["diagram_url"]
            context["informal_stack_thumbnail_url"] = plot_locations["thumbnail_url"]
        else:
            context.pop("informal_stack_url", None)
            context.pop("informal_stack_thumbnail_url", None)
        return context

    def process_get(self, user):
        """Returns additional context data of these sample details to be used
        in the “show sample” view.  This is part of the sample details API.
        The data returned here is used in the ``sample_details`` block in the
        template, which is overridden in a derived template.

        :param user: the currently logged-in user

        :type user: django.contrib.auth.models.User

        :return:
          additional context dictionary for the template

        :rtype: dict mapping str to object
        """
        return {"informal_layers": InformalLayerFormSet(instance=self)}

    def process_post(self, user, post_data, sample_form, edit_description_form):
        """Processes the HTTP POST data for the sample details.  It returns
        two things: First, it returns additional template context for these
        sample details to be used in the “show sample” view.  Secondly, it
        returns whether the sample details data found in the POST data were
        valid.  This includes the referential validity with the sample and edit
        description data.

        This method is part of the sample details API.  The context dictionary
        returned here is used in the ``sample_details`` block in the template,
        which is overridden in a derived template.

        :param user: the currently logged-in user
        :param post_data: the HTTP POST data
        :param sample_form: the bound sample form
        :param edit_description_form: a bound form with description of edit
            changes

        :type user: django.contrib.auth.models.User
        :type sample_form: `samples.views.sample.SampleForm`
        :type edit_description_form:
          `samples.views.form_utils.EditDescriptionForm` or NoneType

        :return:
          additional context dictionary for the template, whether the sample
          details data is valid

        :rtype: dict mapping str to object, bool
        """
        try:
            informal_layer_forms = InformalLayerFormSet(post_data, instance=self)
            return {"informal_layers": informal_layer_forms}, informal_layer_forms.is_valid()
        except ValidationError:
            return {}, False

    def save_form_data(self, sample_details_context):
        """Saves the POST data related to sample details to the database.

        :param sample_details_context: the additional context which was
            generated in `process_get` or `process_post`

        :type sample_details_context: dict mapping str to object
        """
        self.informal_layers.all().delete()
        informal_layers = sample_details_context["informal_layers"].save(commit=False)
        for informal_layer in informal_layers:
            informal_layer.save(with_relations=False)
        self.save()

    def get_data(self):
        """Extract the data of the sample details as a dictionary, ready to be used for
        general data export.  In contrast to `get_data_for_table_export`, I
        export all fields automatically of the instance, including foreign
        keys.  Moreover, all informal layers are exported together with their
        data in nested dictionaries.  Typically, this data is used when a
        non-browser client retrieves a single resource and expects JSON output.

        :return:
          the content of all fields of these sample details

        :rtype: dict
        """
        data = {field.name: getattr(self, field.name) for field in self._meta.get_fields()
                if field.concrete and not field.name == "sample"}
        data.update(("informal layer #{}".format(layer.index), layer.get_data()) for layer in self.informal_layers.all())
        return data

    def get_data_for_table_export(self):
        """Extract the data of these sample details as a set of nodes with lists of
        key–value pairs, ready to be used for the table data export.  Informal
        layers are added as children to the node.  See the
        :py:mod:`samples.views.table_export` module for all the glory details.

        :return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = DataNode(self)
        data_node.children.extend(layer.get_data_for_table_export() for layer in self.informal_layers.iterator())
        if self.sample.split_origin:
                ancestor_data = self.sample.split_origin.parent.get_data_for_table_export()
                data_node.children.extend(ancestor_data.children)
        for process in self.sample.processes.order_by("timestamp").iterator():
            data_node.children.append(process.actual_instance.get_data_for_table_export())
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        related_models = {InformalLayer: "informal_layers"}
        return search.SearchTreeNode(cls, related_models, search_fields=search.convert_fields_to_search_fields(cls))


class InformalLayer(models.Model, samples.models.GraphEntity):
    """Model for one layer in the informal layer stack diagram.
    """

    class Color(models.TextChoices):
        BLACK = "black", _("black")
        BLUE = "blue", _("blue")
        BROWN = "brown", _("brown")
        DARKGRAY = "darkgray", _("darkgray")
        GREEN = "green", _("green")
        LIGHTBLUE = "lightblue", _("lightblue")
        LIGHTGREEN = "lightgreen", _("lightgreen")
        MAGENTA = "magenta", _("magenta")
        ORANGE = "orange", _("orange")
        RED = "red", _("red")
        SILVER = "silver", pgettext_lazy("color", "silver")
        WHITE = "white", _("white")
        YELLOW = "yellow", _("yellow")

    class Classification(models.TextChoices):
        A_SI_H = "a-Si:H", "a-Si:H"
        MUC_SI_H = "muc-Si:H", "µc-Si:H"
        SI_WAFER = "si-wafer", _("silicon wafer")
        SIC = "SiC", "SiC"
        GLASS = "glass", _("glass")
        SILVER = "silver", pgettext_lazy("metall", "silver")
        ZNO = "ZnO", "ZnO"
        HF_DIP = "HF dip", _("HF dip")
        SIO2 = "SiO2", "SiO₂"

    class Doping(models.TextChoices):
        P = "p", "p"
        I = "i", "i"
        N = "n", "n"

    index = models.PositiveIntegerField(_("index"))
    sample_details = models.ForeignKey(SampleDetails, models.CASCADE, verbose_name=_("sample details"),
                                       related_name="informal_layers")
    doping = models.CharField(_("doping"), max_length=10, null=True, blank=True, choices=Doping.choices)
    classification = models.CharField(_("classification"), max_length=30, null=True, blank=True,
                                      choices=Classification.choices)
    comments = models.CharField(_("comments"), max_length=100, null=True, blank=True)
    color = models.CharField(_("color"), max_length=30, choices=Color.choices)
    thickness = model_fields.DecimalQuantityField(_("thickness"), max_digits=8, decimal_places=1, unit="nm")
    thickness_reliable = models.BooleanField(_("thickness reliable"), default=False)
    structured = models.BooleanField(_("structured"), default=False)
    textured = models.BooleanField(_("textured"), default=False)
    always_collapsed = models.BooleanField(_("always collapsed"), default=False)
    process = models.ForeignKey(samples.models.Process, models.CASCADE, verbose_name=_("process"),
                                related_name="informal_layers", null=True, blank=True)
    additional_process_data = models.TextField(_("additional process data"), blank=True)
    verified = models.BooleanField(_("verified"), default=False)

    class Meta:
        ordering = ["sample_details", "index"]
        unique_together = (("index", "sample_details"),)
        verbose_name = _("informal layer")
        verbose_name_plural = _("informal layers")

    def __str__(self):
        return "{0}-{1} ({2})".format(self.sample_details.sample, self.index, self.classification or self.comments)

    def save(self, *args, **kwargs):
        """Saves the object to the database.  I touch the associated sample,
        too, so that it is marked as updated and the cache is cleaned up
        properly.

        If all informal layers of a particular sample are stored at the same
        type – a typical situation in an edit view – you should pass
        ``with_relations=False`` to the ``save`` method so that not for every
        layer the sample is touched.  Then, you must take care of touching the
        sample once yourself, of course.

        :param with_relations: If ``True`` (default), also touch the related
            sample details (and with it, the sample).

        :type with_relations: bool
        """
        with_relations = kwargs.pop("with_relations", True)
        super().save(*args, **kwargs)
        if with_relations:
            self.sample_details.save()

    def get_data(self):
        """Extract the data of this process as a dictionary, ready to be used for
        general data export.  It is only used in
        :py:meth:`SampleDetails.get_data`.

        :return:
          the content of all fields of this informal layer

        :rtype: dict
        """
        return {field.name: getattr(self, field.name) for field in self._meta.fields}

    def get_data_for_table_export(self):
        """Extract the data of this informal layer as a
        :py:class:`~samples.data_tree.DataNode` with lists of key–value pairs,
        ready to be used for the table data export.  See the
        `samples.views.table_export` module for all the glory details.

        :return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = DataNode(self)
        samples.models.fields_to_data_items(self, data_node, {"sample_details", "color", "always_collapsed", "process",
                                                              "additional_process_data"})
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        search_fields = search.convert_fields_to_search_fields(
            cls, excluded_fieldnames=["additional_process_data", "color", "always_collapsed"])
        related_models = {}
        return search.SearchTreeNode(cls, related_models, search_fields)


class InformalLayerForm(forms.ModelForm):

    class Meta:
        widgets = {
            "index": forms.TextInput(attrs={"size": 5}),
            "comments": forms.TextInput(attrs={"size": 10}),
            "thickness": forms.TextInput(attrs={"size": 10}),
            }

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("classification") and not cleaned_data.get("comments"):
            raise ValidationError(_("You must give a classification or comments or both."), code="invalid")
        return cleaned_data

InformalLayerFormSet = inlineformset_factory(SampleDetails, InformalLayer, extra=8, form=InformalLayerForm,
                                             exclude=("process", "additional_process_data"))
"""Form set class for the informal layers.  You cannot shuffle the indices
arbitrarily, though, to inserting a new layer in the middle is a bit tricky.
"""


_ = gettext
