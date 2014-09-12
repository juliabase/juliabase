#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""This module contains the sample details and associated models.  In
particular, it contains the informal layer stacks.
"""

from __future__ import absolute_import, unicode_literals

import os.path
from django.utils.translation import ugettext_lazy as _, ugettext, pgettext_lazy
from django.conf import settings
from django.db import models
import django.core.urlresolvers
from django import forms
from django.forms.util import ValidationError
from django.forms.models import inlineformset_factory
from jb_common.signals import storage_changed
from jb_common import search
from samples.data_tree import DataNode, DataItem
import samples.models, samples.views.shared_utils


class SampleDetails(models.Model):
    """Model for sample details.  It extends the ``Sample`` model as
    ``UserDetails`` extend ``User``, i.e. through a one-to-one relationship.
    Apart form this, it must contain a `get_context_for_user` method.  The rest
    is optional, however, you must take care of proper cache invalidation so
    that the user doesn't get an outdated sample data sheet when this model or
    depending models are updated.
    """
    sample = models.OneToOneField(samples.models.Sample, verbose_name=_("sample"), related_name="sample_details",
                                  primary_key=True)

    class Meta:
        verbose_name = _("sample details")
        verbose_name_plural = pgettext_lazy("plural", "sample details")

    def __unicode__(self):
        return unicode(self.sample)

    def save(self, *args, **kwargs):
        """Saves the object to the database.  I touch the associated sample,
        too, so that it is marked as updated and the cache is cleaned up
        properly.
        """
        super(SampleDetails, self).save(*args, **kwargs)
        # I cannot use ``self.sample`` because it may be outdated (changed
        # through another instance of it in the view).
        samples.models.Sample.objects.get(id=self.sample.id).save(with_relations=False)

    def get_stack_diagram_locations(self):
        """Returns the locations of the stack diagram files.  This is also
        needed in ``stack.py``, therefore, it is not part of
        `get_context_for_user`.

        :Return:
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
        return {"diagram_file": os.path.join(settings.CACHE_ROOT, "stacks", str(self.pk) + ".pdf"),
                "diagram_url": django.core.urlresolvers.reverse("stack_diagram", kwargs={"sample_id": str(self.pk)}),
                "thumbnail_file": os.path.join(settings.CACHE_ROOT, "stacks", str(self.pk) + ".png"),
                "thumbnail_url": django.core.urlresolvers.reverse("stack_diagram_thumbnail",
                                                                  kwargs={"sample_id": str(self.pk)})}

    def has_producible_stack_diagram(self):
        """Returns whether it is possible to print a stack diagram for this
        sample.  Currently, this is possible if at least one onformal layer is
        verified by a user.  Note that this method hits the database, so cache
        its result if applicable.

        :Return:
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

        :Parameters:
          - `user`: the currently logged-in user
          - `old_context`: the sample context as it was in the cache or newly
            build.  This dictionary will not be touched in this method.

        :type user: ``django.contrib.auth.models.User``
        :type old_context: dict mapping str to ``object``

        :Return:
          the adapted full context for the sample

        :rtype: dict mapping str to ``object``
        """
        _ = ugettext
        context = old_context.copy()
        context["sample_details"] = self
        plot_locations = self.get_stack_diagram_locations()
        if self.has_producible_stack_diagram():
            context["informal_stack_url"] = plot_locations["diagram_url"]
            context["informal_stack_thumbnail_url"] = plot_locations["thumbnail_url"]
        else:
            removed = samples.views.shared_utils.remove_file(plot_locations["diagram_file"])
            removed = samples.views.shared_utils.remove_file(plot_locations["thumbnail_file"]) or removed
            context.pop("informal_stack_url", None)
            context.pop("informal_stack_thumbnail_url", None)
            if removed:
                storage_changed.send(SampleDetails)
        return context

    def process_get(self, user):
        """Returns additional context data of these sample details to be used
        in the “show sample” view.  This is part of the sample details API.
        The data returned here is used in the ``sample_details`` block in the
        template, which is overridden in a derived template.

        :Parameters:
          - `user`: the currently logged-in user

        :type user: ``django.contrib.auth.models.User``

        :Return:
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

        :Parameters:
          - `user`: the currently logged-in user
          - `post_data`: the HTTP POST data
          - `sample_form`: the bound sample form
          - `edit_description_form`: a bound form with description of edit
            changes

        :type user: ``django.contrib.auth.models.User``
        :type sample_form: `samples.views.sample.SampleForm`
        :type edit_description_form: `form_utils.EditDescriptionForm` or
          ``NoneType``

        :Return:
          additional context dictionary for the template, whether the sample
          details data is valid

        :rtype: dict mapping str to object, bool
        """
        informal_layer_forms = InformalLayerFormSet(post_data, instance=self)
        return {"informal_layers": informal_layer_forms}, informal_layer_forms.is_valid()

    def save_form_data(self, sample_details_context):
        """Saves the POST data related to sample details to the database.

        :Parameters:
          - `sample_details_context`: the additional context which was
            generated in `process_get` or `process_post`

        :type sample_details_context: dict mapping str to object
        """
        informal_layers = sample_details_context["informal_layers"].save(commit=False)
        for informal_layer in informal_layers:
            informal_layer.save(with_relations=False)
        self.save()

    def get_data(self):
        data_node = DataNode(self)
        data_node.children.extend(layer.get_data() for layer in self.informal_layers.all())
        return data_node

    def get_data_for_table_export(self):
        _ = ugettext
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

        :Return:
          the tree node for this model instance

        :rtype: ``jb_common.search.SearchTreeNode``
        """
        related_models = {InformalLayer: "informal_layers"}
        return search.SearchTreeNode(cls, related_models, search_fields=search.convert_fields_to_search_fields(cls))


color_choices = (("black", _("black")), ("blue", _("blue")), ("brown", _("brown")), ("darkgray", _("darkgray")),
                 ("green", _("green")), ("lightblue", _("lightblue")),
                 ("lightgreen", _("lightgreen")), ("magenta", _("magenta")),
                 ("orange", _("orange")), ("red", _("red")), ("silver", pgettext_lazy("color", "silver")),
                 ("white", _("white")), ("yellow", _("yellow")))

classification_choices = (("a-Si:H", "a-Si:H"), ("muc-Si:H", "µc-Si:H"), ("si-wafer", _("silicon wafer")),
                          ("SiC", "SiC"), ("glass", _("glass")), ("silver", pgettext_lazy("metall", "silver")),
                          ("ZnO", "ZnO"), ("HF dip", _("HF dip")), ("SiO2", "SiO₂"))

doping_choices = (("p", "p"), ("i", "i"), ("n", "n"))

class InformalLayer(models.Model):
    """Model for one layer in the informal layer stack diagram.
    """
    index = models.PositiveIntegerField(_("index"))
    sample_details = models.ForeignKey(SampleDetails, verbose_name=_("sample details"), related_name="informal_layers")
    doping = models.CharField(_("doping"), max_length=10, null=True, blank=True, choices=doping_choices)
    classification = models.CharField(_("classification"), max_length=30, null=True, blank=True,
                                      choices=classification_choices)
    comments = models.CharField(_("comments"), max_length=100, null=True, blank=True)
    color = models.CharField(_("color"), max_length=30, choices=color_choices)
    thickness = models.DecimalField(_("thickness"), max_digits=8, decimal_places=1, help_text=_("in nm"))
    thickness_reliable = models.BooleanField(_("thickness reliable"), default=False)
    structured = models.BooleanField(_("structured"), default=False)
    textured = models.BooleanField(_("textured"), default=False)
    always_collapsed = models.BooleanField(_("always collapsed"), default=False)
    process = models.ForeignKey(samples.models.Process, verbose_name=_("process"), related_name="informal_layers",
                                null=True, blank=True)
    additional_process_data = models.TextField(_("additional process data"), blank=True)
    verified = models.BooleanField(_("verified"), default=False)

    class Meta:
        ordering = ["sample_details", "index"]
        unique_together = (("index", "sample_details"),)
        verbose_name = _("informal layer")
        verbose_name_plural = _("informal layers")

    def __unicode__(self):
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

        :Parameters:
          - `with_relations`: If ``True`` (default), also touch the related
            sample details (and with it, the sample).

        :type with_relations: bool
        """
        with_relations = kwargs.pop("with_relations", True)
        super(InformalLayer, self).save(*args, **kwargs)
        if with_relations:
            self.sample_details.save()

    def get_data(self):
        data_node = DataNode(self)
        data_node.items = [DataItem("index", self.index),
                           DataItem("doping", self.doping),
                           DataItem("classification", self.classification),
                           DataItem("comments", self.comments),
                           DataItem("thickness", self.thickness),
                           DataItem("thickness reliable", self.thickness_reliable),
                           DataItem("structured", self.structured),
                           DataItem("textured", self.textured),
                           DataItem("verified", self.verified)]
        return data_node

    def get_data_for_table_export(self):
        _ = ugettext
        data_node = DataNode(self)
        data_node.items = [DataItem(_("index"), self.index),
                           DataItem(_("doping"), self.get_doping_display()),
                           DataItem(_("classification"), self.get_classification_display()),
                           DataItem(_("comments"), self.comments),
                           DataItem(_("thickness"), self.thickness),
                           DataItem(_("thickness reliable"), self.thickness_reliable),
                           DataItem(_("structured"), self.structured),
                           DataItem(_("textured"), self.textured),
                           DataItem(_("verified"), self.verified)]
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :Return:
          the tree node for this model instance

        :rtype: ``jb_common.search.SearchTreeNode``
        """
        search_fields = search.convert_fields_to_search_fields(
            cls, excluded_fieldnames=["additional_process_data", "color", "always_collapsed"])
        related_models = {}
        return search.SearchTreeNode(cls, related_models, search_fields)


class InformalLayerForm(forms.ModelForm):
    def clean(self):
        if not self.cleaned_data.get("classification") and not self.cleaned_data.get("comments"):
            raise ValidationError(_("You must give a classification or comments or both."))
        return self.cleaned_data
    class Meta:
        widgets = {
            "index": forms.TextInput(attrs={"size": 5}),
            "comments": forms.TextInput(attrs={"size": 10}),
            "thickness": forms.TextInput(attrs={"size": 10}),
            }

InformalLayerFormSet = inlineformset_factory(SampleDetails, InformalLayer, extra=8, form=InformalLayerForm,
                                             exclude=("process", "additional_process_data"))
"""Form set class for the informal layers.  You cannot shuffle the indices
arbitrarily, though, to inserting a new layer in the middle is a bit tricky.
"""
