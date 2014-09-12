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


"""The most basic models like ``Sample``, ``SampleSeries``, ``UserDetails``
etc.  It is important to see that this module is imported by almost all other
models modules.  Therefore, you *must* *not* import any JuliaBase models module
here, in particular not ``models.py``.  Otherwise, you'd end up with
irresolvable cyclic imports.
"""

from __future__ import absolute_import, division, unicode_literals

import hashlib, os.path, datetime, json
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext, pgettext_lazy, get_language
from django.template import defaultfilters, Context, TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.http import urlquote, urlquote_plus
import django.core.urlresolvers
from django.conf import settings
from django.db import models
from django.core.cache import cache
from chantal_common.utils import get_really_full_name, cache_key_locked
from chantal_common.models import Topic, PolymorphicModel, Department
from samples import permissions
from samples.views import shared_utils
from chantal_common import search
from samples.data_tree import DataNode, DataItem
from django.contrib.contenttypes.models import ContentType
import collections


class ExternalOperator(models.Model):
    """Some samples and processes are not made in our institute but in external
    institutions.  This is realised by setting the `Process.external_operator`
    field, which in turn contains `ExternalOperator`.
    """
    name = models.CharField(_("name"), max_length=30)
    institution = models.CharField(_("institution"), max_length=255)
    email = models.EmailField(_("email"))
    alternative_email = models.EmailField(_("alternative email"), blank=True)
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    contact_persons = models.ManyToManyField(django.contrib.auth.models.User, related_name="external_contacts",
                                       verbose_name=_("contact persons in the institute"))
        # Translators: Topic which is not open to senior members
    confidential = models.BooleanField(_("confidential"), default=False)

    class Meta:
        verbose_name = _("external operator")
        verbose_name_plural = _("external operators")
        _ = lambda x: x
        permissions = (("add_external_operator", _("Can add an external operator")),
                       ("view_all_external_operators", _("Can view all external operators")))

    def save(self, *args, **kwargs):
        super(ExternalOperator, self).save(*args, **kwargs)
        for process in self.processes.all():
            process.actual_instance.save()

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.external_operator.show", [self.pk])


timestamp_inaccuracy_choices = (
        # Translators: It's about timestamps
    (0, _("totally accurate")),
    (1, _("accurate to the minute")),
    (2, _("accurate to the hour")),
    (3, _("accurate to the day")),
    (4, _("accurate to the month")),
    (5, _("accurate to the year")),
    (6, _("not even accurate to the year")),
    )

class Process(PolymorphicModel):
    """This is the parent class of all processes and measurements.  Actually,
    it is an *abstract* base class, i.e. there are no processes in the database
    that are *just* processes.  However, it is not marked as ``abstract=True``
    in the ``Meta`` subclass because I must be able to link to it with
    ``ForeignKey``.

    If you retrieve a `Process`, you may read (inherited) field
    `actual_instance` to get the actual object, e.g. a `SixChamberDeposition`::

        process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id))
        process = process.actual_instance
    """
    timestamp = models.DateTimeField(_("timestamp"))
    timestamp_inaccuracy = models.PositiveSmallIntegerField(_("timestamp inaccuracy"), choices=timestamp_inaccuracy_choices,
                                                            default=0)
    operator = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("operator"), related_name="processes")
    external_operator = models.ForeignKey(ExternalOperator, verbose_name=_("external operator"), null=True, blank=True,
                                          related_name="processes")
    comments = models.TextField(_("comments"), blank=True)
    last_modified = models.DateTimeField(_("last modified"), auto_now=True, auto_now_add=True, editable=False)
    finished = models.BooleanField(_("finished"), default=True)
    """Whether the process is complete and can be displayed in sample data
    sheets.  Not every process needs to implement it; you can as well leave it
    ``True``.  However, depositions that are a work-in-progress, possibly by
    more than one person, profit from it.  If ``finished`` is ``False``,
    everyone who can add such a process can edit it; no edit descriptions must
    be given; the process cannot be used in a clearance; the process doesn't
    appear on data sheets but it does appear in the lab notebook.
    """

    class Meta:
        ordering = ["timestamp"]
        get_latest_by = "timestamp"
        verbose_name = _("process")
        verbose_name_plural = _("processes")

    def save(self, *args, **kwargs):
        """Saves the instance and clears stalled cache items.

        :Parameters:
          - `with_relations`: If ``True`` (default), also touch the related
            samples.  Should be set to ``False`` if called from another
            ``save`` method in order to avoid endless recursion.

        :type with_relations: bool
        """
        keys_list_key = "process-keys:{0}".format(self.pk)
        with cache_key_locked("process-lock:{0}".format(self.pk)):
            keys = cache.get(keys_list_key)
            if keys:
                cache.delete_many(keys)
            cache.delete(keys_list_key)
        with_relations = kwargs.pop("with_relations", True)
        super(Process, self).save(*args, **kwargs)
        if with_relations:
            for sample in self.samples.all():
                sample.save(with_relations=False)

    def __unicode__(self):
        actual_instance = self.actual_instance
        if actual_instance == self:
            return _("process #{0}").format(self.pk)
        else:
            return unicode(actual_instance)

    @models.permalink
    def get_absolute_url(self):
        """Returns the relative URL (ie, without the domain name) of the
        database object.  Django calls this method ``get_absolute_url`` to make
        clear that *only* the domain part is missing.  Apart from that, it
        includes the full URL path to where the object can be seen.

        Note that Django itself uses this method in its built-in syndication
        framework.  However currently, JuliaBase uses it only explicitly in
        re-directions and links in templates.

        :Return:
          Relative URL, however, starting with a “/”, to the page where one can
          view the object.

        :rtype: str
        """
        return ("samples.views.main.show_process", [str(self.pk)])

    def calculate_plot_locations(self, plot_id=""):
        """Get the location of a plot in the local filesystem as well as on
        the webpage.

        :Parameters:
          - `plot_id`: the unique ID of the image.  This is mostly ``""``
            because most measurement models have only one graphics.

        :type plot_id: unicode

        :Return:
          a dictionary containing the following keys:

          =========================  =========================================
                 key                           meaning
          =========================  =========================================
          ``"plot_file"``            full path to the original plot file
          ``"plot_url"``             full relative URL to the plot
          ``"thumbnail_file"``       full path to the thumbnail file
          ``"thumbnail_url"``        full relative URL to the thumbnail (i.e.,
                                     without domain)
          =========================  =========================================

        :rtype: dict mapping str to str
        """
        if not plot_id:
            # We give this a nicer URL because this case is so common
            plot_url = django.core.urlresolvers.reverse("default_process_plot", kwargs={"process_id": str(self.pk)})
            thumbnail_url = django.core.urlresolvers.reverse("default_process_plot_thumbnail",
                                                             kwargs={"process_id": str(self.pk)})
        else:
            plot_url = django.core.urlresolvers.reverse("process_plot",
                                                        kwargs={"process_id": str(self.pk), "plot_id": plot_id})
            thumbnail_url = django.core.urlresolvers.reverse("process_plot_thumbnail",
                                                             kwargs={"process_id": str(self.pk), "plot_id": plot_id})
        basename = "{0}-{1}-{2}-{3}-{4}".format(
            self.content_type.app_label, self.content_type.model, get_language(), self.pk, plot_id)
        return {"plot_file": os.path.join(settings.CACHE_ROOT, "plots", basename + ".pdf"),
                "plot_url": plot_url,
                "thumbnail_file": os.path.join(settings.CACHE_ROOT, "plots", basename + ".png"),
                "thumbnail_url": thumbnail_url}

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        """Generate a plot using Matplotlib commands.  You may do whatever you
        want here – but eventually, there must be a savable Matplotlib plot in
        the `axes`.  The ``filename`` parameter is not really necessary but it
        makes things a little bit faster and easier.

        This method must be overridden in derived classes that wish to offer
        plots.

        :Parameters:
          - `axes`: The Matplotlib axes to which the plot must be drawn.  You
            call methods of this parameter to draw the plot,
            e.g. ``axes.plot(x_values, y_values)``.
          - `plot_id`: The ID of the plot.  For most models offering plots,
            this can only be the empty string and as such is not used it all in
            this method.
          - `filename`: the filename of the original data file; it may also be
            a list of filenames if more than one file lead to the plot
          - `for_thumbnail`: whether we do a plot for the thumbnail bitmap; for
            simple plots, this can be ignored

        :type axes: ``matplotlib.axes.Axes``
        :type plot_id: unicode
        :type filename: str or list of str
        :type for_thumbnail: bool

        :Exceptions:
          - `PlotError`: if anything went wrong during the generation of the
            plot
        """
        raise NotImplementedError

    def get_datafile_name(self, plot_id):
        """Get the name of the file with the original data for the plot with
        the given ``plot_id``.  It may also be a list of filenames if more than
        one file lead to the plot.

        This method must be overridden in derived classes that wish to offer
        plots.

        :Parameters:
          - `plot_id`: the ID of the plot.  For most models offering plots,
            this can only be the empty string and as such is not used it all in
            this method.  Note that you must not assume that its value is
            valid.

        :type plot_id: unicode

        :Return:
          The absolute path of the file(s) with the original data for this plot
          in the local filesystem.  It's ``None`` if there is no plot available
          for this process.  If there are no raw datafile but you want to draw
          a plot nevertheless (e.g. from process data), return an empty list.

        :rtype: list of str, str, or ``NoneType``
        """
        raise NotImplementedError

    def get_plotfile_basename(self, plot_id):
        """Get the name of the plot files with the given ``plot_id``.  For
        example, for the PDS measurement for the sample 01B410, this may be
        ``"pds_01B410"``.  It should be human-friendly and reasonable
        descriptive since this is the name that is used if the user wishes to
        download a plot to their local filesystem.  It need not be unique in
        any way (although mostly it is).

        The default behaviour is a basename which consists of the process class
        name, the process ID, and – if given – the plot ID.

        :Parameters:
          - `plot_id`: the ID of the plot.  For most models offering plots,
            this can only be the empty string and as such is not used it all in
            this method then.

        :type plot_id: unicode

        :Return:
          the base name for the plot files, without directories or extension

        :rtype: unicode
        """
        basename = "{0}_{1}".format(shared_utils.camel_case_to_underscores(self.__class__.__name__), self.pk)
        if plot_id:
            basename += "_" + plot_id
        return basename

    def get_data(self):
        """Extract the data of this process as a tree of nodes (or a single
        node) with lists of key–value pairs, ready to be used for general data
        export.  In contrast to `get_data_for_table_export`, I export *all*
        attributes that may be interesting for the user, and even some related
        data.  Typically, this data is used if a non-browser client retrieves a
        single resource (*not* its table export!) and expects JSON output.

        Additionaly, nothing is translated here.  This is in order to have
        stable keys and values.  Otherwise, interpretation of the extracted
        data would be a nightmare.  This also means that you must pass a
        unicode to ``DataNode`` instead of an instance because an instance gets
        translated.

        :Return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = DataNode("process #{0}".format(self.pk))
        data_node.items = [DataItem("type", shared_utils.camel_case_to_human_text(self.__class__.__name__), "process"),
                           DataItem("timestamp", self.timestamp, "process"),
                           DataItem("timestamp inaccuracy", self.timestamp_inaccuracy, "process"),
                           DataItem("operator", self.operator, "process"),
                           DataItem("external operator", self.external_operator, "process"),
                           DataItem("finished", self.finished, "process"),
                           DataItem("comments", self.comments.strip(), "process"),
                           DataItem("sample IDs", self.samples.values_list("id", flat=True), "process")]
        return data_node

    def get_data_for_table_export(self):
        """Extract the data of this process as a tree of nodes (or a single
        node) with lists of key–value pairs, ready to be used for the table
        data export.  See the `samples.views.table_export` module for all the
        glory details.

        Note that ``_`` must get ``ugettext`` in these methods because
        otherwise, subsequent modifications in derived classes break.

        :Return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        _ = ugettext
        data_node = DataNode(self)
        data_node.items = [DataItem(_("timestamp"), self.timestamp, "process"),
                           DataItem(_("operator"), get_really_full_name(self.operator), "process"),
                           DataItem(_("comments"), self.comments.strip(), "process")]
        return data_node

    @classmethod
    def get_lab_notebook_context(cls, year, month):
        processes = cls.objects.filter(timestamp__year=year, timestamp__month=month).select_related()
        return {"processes": processes}

    def get_cache_key(self, user_settings_hash, local_context):
        """Calculate a cache key for this context instance of the process.
        Note that there may be many cache items to one process, e. g. one for
        every language.  Each of them needs a unique cache key.  The only this
        that is *never* included in a cache key is the user himself because
        then, the cache would lose much of its effectiveness.  Instead, the
        purpose of the sample cache is to fetch the whole sample which was
        calculated for another user and simply adapt it to the current one.
        This is important because this is a frequent use case.

        :Parameters:
          - `user_settings_hash`: hash over all settings which affect the
            rendering of processes, e. g. language
          - `local_context`: the local sample context; currently, this is only
            relevant to `SampleSplit`, see `SampleSplit.get_cache_key`.

        :type user_settings_hash: str
        :type local_context: dict mapping str to ``object``

        :Return:
          the cache key for this process instance

        :rtype: str
        """
        return "process:{0}-{1}".format(self.pk, user_settings_hash)

    def get_context_for_user(self, user, old_context):
        """Create the context dict for this process, or fill missing fields,
        or adapt existing fields to the given user.  Note that adaption only
        happens to the current user and not to any settings like e.g. language.
        In other words, if a non-empty `old_context` is passed, the caller must
        assure that language etc is already correct, just that it may be a
        cached context from another user with different permissions.

        A process context has always the following fields: ``process``,
        ``html_body``, ``name``, ``operator``, ``timestamp``, and
        ``timestamp_inaccuracy``.  Optional standard fields are ``edit_url``,
        ``export_url``, and ``duplicate_url``.  It may also have further
        fields, which must be interpreted by the respective ``"show_…"``
        template.

        It is very important to see that ``html_body`` (the result of the
        ``show_<process name>.html`` template) must not depend on sample data!
        Otherwise, you see outdated process data after having changed sample
        data.  (There is only one exception: sample splits.)  If you really
        need this dependency, then expire the cached sample items yourself in a
        signal function.

        Note that it is necessary that ``self`` is the actual instance and not
        a parent class.

        :Parameters:
          - `user`: the current user
          - `old_context`: The present context for the process.  This may be
             only the sample context (i. e. ``sample``, ``original_sample``
             etc) if the process hasn't been found in the cache. Otherwise, it
             is the full process context, although (possibly) for another user,
             so it needs to be adapted.  This dictionary will not be touched in
             this method.

        :type user: ``django.contrib.auth.models.User``
        :type old_context: dict mapping str to ``object``

        :Return:
          the adapted full context for the process

        :rtype: dict mapping str to ``object``
        """
        context = old_context.copy()
        if "browser_system" not in context:
            context["browser_system"] = user.jb_user_details.browser_system
        if "process" not in context:
            context["process"] = self
        if "name" not in context:
            name = unicode(self._meta.verbose_name) if not isinstance(self, Result) else self.title
            context["name"] = name[:1].upper() + name[1:]
        if "html_body" not in context:
            context["html_body"] = render_to_string(
                "samples/show_" + shared_utils.camel_case_to_underscores(self.__class__.__name__) + ".html",
                context_instance=Context(context))
            if "short_html_body" not in context:
                try:
                    context["short_html_body"] = render_to_string(
                        "samples/show-short_{0}.html". \
                            format(shared_utils.camel_case_to_underscores(self.__class__.__name__)),
                        context_instance=Context(context))
                except TemplateDoesNotExist:
                    context["short_html_body"] = None
            if "extend_html_body" not in context:
                try:
                    context["extended_html_body"] = render_to_string(
                        "samples/show-extended_{0}.html". \
                            format(shared_utils.camel_case_to_underscores(self.__class__.__name__)),
                        context_instance=Context(context))
                except TemplateDoesNotExist:
                    context["extended_html_body"] = None
        if "operator" not in context:
            context["operator"] = self.external_operator or self.operator
        if "timestamp" not in context:
            context["timestamp"] = self.timestamp
        if "timestamp_inaccuracy" not in context:
            context["timestamp_inaccuracy"] = self.timestamp_inaccuracy
        return context

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.  This particular method is an example for generating this
        node automatically for this and all derived models.  If it raises a
        `NotImplementedError` or if the method doesn't exist at all, the
        respective model cannot be searched for.

        :Return:
          the tree node for this model instance

        :rtype: ``chantal_common.search.SearchTreeNode``
        """
        if cls == Process:
            raise NotImplementedError
        search_fields = [search.TextSearchField(cls, "operator", "username"),
                         search.TextSearchField(cls, "external_operator", "name")]
        search_fields.extend(
            search.convert_fields_to_search_fields(cls, ["timestamp_inaccuracy", "last_modified", "finished"]))
        related_models = {Sample: "samples"}
        related_models.update(
            (related_object.model, related_object.get_accessor_name()) for related_object
            in cls._meta.get_all_related_objects() if not related_object.model.__name__.startswith("Feed"))
        return search.SearchTreeNode(cls, related_models, search_fields)


class PhysicalProcess(Process):
    """Abstract class for physical processes.  These processes are “real”
    processes such as depositions, etching processes, measurements etc.  This
    class doesn't define anything.  Its main purpose is to bring structure to
    the class hierarchy by pooling all physical processes.

    Such processes can have permissions of the form ``"add_model_name"``,
    ``"view_every_model_name"`` and ``"edit_permissions_for_model_name"`` where
    the model name is in lowercase with underscores.

    Normally, all three permissions are available.  However, you may omit
    ``"add_model_name"`` if *every* user should be allowed to add such
    processes (and edit their own).

    You can omit ``"view_every_model_name"`` if no-one should be allowed to see
    all processes (or see the lab notebook, which shouldn't even exist in this
    case for obvious reasons).

    If you omit ``"edit_permissions_for_model_name"``, no email is sent if a
    particular user adds it first process of this kind.

    If neiter ``"add_model_name"`` nor ``"edit_permissions_for_model_name"`` is
    included, the process won't show up on the permissions list page.
    """
    class Meta(Process.Meta):
        abstract = True
        # FixMe: The following line is necessary as long as
        # http://code.djangoproject.com/ticket/11369 is not fixed.  But check
        # ordering nevertheless.
        ordering = ["timestamp"]

    @classmethod
    def get_add_link(cls):
        """Returns the URL to the “add” view for this process.  This should be
        implemented in derived model classes which is actually instantiated
        unless this process class should not be explicitly added by users (but
        is created by the program somehow).

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        raise NotImplementedError

    @classmethod
    def get_lab_notebook_data(cls, year, month):
        """Returns the data tree for all processes in the given month.  This
        is a default implementation which may be overridden in derived classes,
        in particular in classes with sub-objects.
        """
        measurements = cls.get_lab_notebook_context(year, month)["processes"]
        data = DataNode(_("lab notebook for {process_name}").format(process_name=cls._meta.verbose_name_plural))
        data.children.extend(measurement.get_data_for_table_export() for measurement in measurements)
        return data


all_searchable_physical_processes = None
def get_all_searchable_physical_processes():
    """Returns all physical processes which have a ``get_search_tree_node``
    method.

    :Return:
      all physical process classes that are searchable

    :rtype: tuple of ``class``
    """
    global all_searchable_physical_processes
    if all_searchable_physical_processes is None:
        all_searchable_physical_processes = tuple(cls for cls in search.get_all_searchable_models()
                                                  if issubclass(cls, PhysicalProcess))
    return all_searchable_physical_processes


class Sample(models.Model):
    """The model for samples.
    """
    name = models.CharField(_("name"), max_length=30, unique=True, db_index=True)
    watchers = models.ManyToManyField(django.contrib.auth.models.User, blank=True, related_name="my_samples",
                                      verbose_name=_("watchers"))
        # Translators: location of a sample
    current_location = models.CharField(_("current location"), max_length=50)
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, related_name="samples",
                                                     verbose_name=_("currently responsible person"))
    purpose = models.CharField(_("purpose"), max_length=80, blank=True)
        # Translators: keywords for samples
    tags = models.CharField(_("tags"), max_length=255, blank=True, help_text=_("separated with commas, no whitespace"))
    split_origin = models.ForeignKey("SampleSplit", null=True, blank=True, related_name="pieces",
                                     # Translators: ID of mother sample
                                     verbose_name=_("split origin"))
    processes = models.ManyToManyField(Process, blank=True, related_name="samples", verbose_name=_("processes"))
    topic = models.ForeignKey(Topic, null=True, blank=True, related_name="samples", verbose_name=_("topic"))
    last_modified = models.DateTimeField(_("last modified"), auto_now=True, auto_now_add=True, editable=False)

    class Meta:
        verbose_name = _("sample")
        verbose_name_plural = _("samples")
        ordering = ["name"]
        _ = lambda x: x
        permissions = (("view_all_samples", _("Can view all samples from his/her department")),
                       ("adopt_samples", _("Can adopt samples from his/her department")),
                       ("rename_samples", _("Can rename samples from his/her department")))

    def save(self, *args, **kwargs):
        """Saves the instance and clears stalled cache items.

        It also touches all ancestors and children and the associated split
        processes.

        :Parameters:
          - `with_relations`: If ``True`` (default), also touch the related
            samples.  Should be set to ``False`` if called from another
            ``save`` method in order to avoid endless recursion.
          - `from_split`: When walking through the decendents, this is set to
            the originating split so that the child sample knows which of its
            splits should be followed, too.  Thus, only the timestamp of
            ``from_split`` is actually used.  It must be ``None`` (default)
            when this method is called from outside this method, or while
            walking through the ancestors.

        :type with_relations: bool
        :type from_split: `SampleSplit` or ``NoneType``
        """
        keys_list_key = "sample-keys:{0}".format(self.pk)
        with cache_key_locked("sample-lock:{0}".format(self.pk)):
            keys = cache.get(keys_list_key)
            if keys:
                cache.delete_many(keys)
            cache.delete(keys_list_key)
        with_relations = kwargs.pop("with_relations", True)
        from_split = kwargs.pop("from_split", None)
        super(Sample, self).save(*args, **kwargs)
        if with_relations:
            for series in self.series.all():
                series.save()
        # Now we touch the decendents ...
        if from_split:
            splits = SampleSplit.objects.filter(parent=self, timestamp__gt=from_split.timestamp)
        else:
            splits = SampleSplit.objects.filter(parent=self)
        for split in splits:
            split.save(with_relations=False)
            for child in split.pieces.all():
                child.save(from_split=split, with_relations=False)
        # ... and the ancestors
        if not from_split and self.split_origin:
            self.split_origin.save(with_relations=False)
            self.split_origin.parent.save(with_relations=False)

    def __unicode__(self):
        """Here, I realise the peculiar naming scheme of provisional sample
        names.  Provisional samples names always start with ``"*"``, followed
        by a number.  The problem is ordering:  This way, ``"*2"`` and
        ``"*10"`` are ordered ``("*10", "*2")``.  Therefore, I make all numbers
        five-digit numbers.  However, for the sake of readability, I remove the
        leading zeroes in this routine.

        Thus be careful how to access the sample name.  If you want to get a
        human-readable name, use ``unicode(sample)`` or simply ``{{ sample }}``
        in templates.  If you need the *real* sample name in the database
        (e.g. for creating a hyperlink), access it by ``sample.name``.
        """
        name = self.name
        if name.startswith("*"):
            return "*" + name.lstrip("*0")
        else:
            return name

    def tags_suffix(self, user):
        """Returns the shortened tags of the sample in parenthesis with a
        non-breaking space before, of the empty string if the sample doesn't
        have tags.  The tags are pruned to 10 characters if necessary.

        :Parameters:
          - `user`: The user for which the tags should be displayed.  If the
            user is not allowed to view the sample fully, no tags are
            returned.

        :type user: ``django.contrib.auth.models.User``

        :Return:
          the shortened tags in parentheses

        :rtype: unicode
        """
        if self.tags and permissions.has_permission_to_fully_view_sample(user, self):
            tags = self.tags if len(self.tags) <= 12 else self.tags[:10] + "…"
            return " ({0})".format(tags)
        else:
            return ""

    def name_with_tags(self, user):
        """Returns the sample's name with possible tags attached.  This is a
        convenience method which simply combines `__unicode__` and
        `tags_suffix`.

        :Parameters:
          - `user`: The user for which the tags should be displayed.  If the
            user is not allowed to view the sample fully, no tags are
            returned.

        :type user: ``django.contrib.auth.models.User``

        :Return:
          the name of the sample, possibly with shortened tags

        :rtype: unicode
        """
        return unicode(self) + self.tags_suffix(user)

    @models.permalink
    def get_absolute_url(self):
        if self.name.startswith("*"):
            return ("show_sample_by_id", (), {"sample_id": str(self.pk), "path_suffix": ""})
        else:
            return ("show_sample_by_name", [self.name])

    def duplicate(self):
        """This is used to create a new `Sample` instance with the same data as
        the current one.  Note that the `processes` field is not set because
        many-to-many fields can only be set after the object was saved.

        :Return:
          A new sample with the same data as the current.

        :rtype: `Sample`
        """
        return Sample(name=self.name, current_location=self.current_location,
                      currently_responsible_person=self.currently_responsible_person, tags=self.tags,
                      split_origin=self.split_origin, topic=self.topic)

    def is_dead(self):
        return self.processes.filter(sampledeath__timestamp__isnull=False).exists()

    def last_process_if_split(self):
        """Test whether the most recent process applied to the sample – except
        for result processes – was a split.

        :Return:
          the split, if it is the most recent process, else ``None``

        :rtype: `models.SampleSplit` or ``NoneType``
        """
        for process in self.processes.order_by("-timestamp"):
            process = process.actual_instance
            if isinstance(process, SampleSplit):
                return process
            if not isinstance(process, Result):
                break
        return None

    def get_sample_details(self):
        """Retreive the sample details of a sample.  Sample details are an optional
        feature that doesn't exist in the app "samples" itself.  It can be
        provided by an app built on top of it.

        If you do so, the sample details must have a O2O relationship to
        ``Sample`` with the related name ``sample_details``.  Furthermore, it
        must have a ``get_context_for_user`` method which takes the ``user``
        and the ``sample_context`` as a parameter, and returns the populated
        sample context dict.

        This in turn can then be used in the overriden ``show_sample.html``
        template in the ``sample_details`` block.

        :Return:
          the sample details object, or ``None`` if there aren't any (because
          there is no model at all or no particular details for *this* sample)

        :rtype: ``SampleDetails`` or ``NoneType``
        """
        try:
            return self.sample_details
        except (AttributeError, models.ObjectDoesNotExist):
            return None

    def get_data(self, only_processes=False):
        """Extract the data of this sample as a tree of nodes (or a single
        node) with lists of key–value pairs, ready to be used for general data
        export.  Every child of the top-level node is a process of the sample.
        In contrast to `get_data_for_table_export`, I export *all* attributes
        that may be interesting for the user, and even some related data.
        Typically, this data is used if a non-browser client retrieves a single
        resource (*not* its table export!) and expects JSON output.

        Additionaly, nothing is translated here.  This is in order to have
        stable keys and values.  Otherwise, interpretation of the extracted
        data would be a nightmare.  This also means that you must pass a
        unicode to ``DataNode`` instead of an instance because an instance gets
        translated.

        :Parameters:
          - `only_processes`: Whether only processes should be included.  It is
            not part of the official `get_data` API.  I use it only to avoid
            having a special inner function in this method.

        :type only_processes: bool

        :Return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = DataNode(self.name)
        if not only_processes:
            sample_details = self.get_sample_details()
            if sample_details:
                sample_details_data = sample_details.get_data()
                data_node.children = sample_details_data.children
        if self.split_origin:
            ancestor_data = self.split_origin.parent.get_data(only_processes=True)
            data_node.children.extend(ancestor_data.children)
        data_node.children.extend(process.actual_instance.get_data() for process in self.processes.all())
        data_node.items = [DataItem("ID", self.pk),
                           DataItem("name", self.name),
                           DataItem("currently responsible person", self.currently_responsible_person),
                           DataItem("current location", self.current_location),
                           DataItem("purpose", self.purpose),
                           DataItem("tags", self.tags),
                           DataItem("split origin", self.split_origin and self.split_origin.id),
                           DataItem("topic", self.topic)]
        if not only_processes and sample_details:
            data_node.items.extend(sample_details_data.items)
        return data_node


    def get_data_for_table_export(self):
        """Extract the data of this sample as a tree of nodes (or a single
        node) with lists of key–value pairs, ready to be used for the table
        data export.  Every child of the top-level node is a process of the
        sample.  See the `samples.views.table_export` module for all the glory
        details.

        Note that ``_`` must get ``ugettext`` in these methods because
        otherwise, subsequent modifications in derived classes break.

        :Return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        _ = ugettext
        data_node = DataNode(self, unicode(self))
        data_node.items = [DataItem("name", self.name),
                           DataItem("currently responsible person", self.currently_responsible_person),
                           DataItem("current location", self.current_location),
                           DataItem("purpose", self.purpose),
                           DataItem("tags", self.tags),
                           DataItem("split origin", self.split_origin),
                           DataItem("topic", self.topic)]
        sample_details = self.get_sample_details()
        if sample_details:
            sample_details_data = sample_details.get_data_for_table_export()
            data_node.children = sample_details_data.children
        else:
            if self.split_origin:
                ancestor_data = self.split_origin.parent.get_data_for_table_export()
                data_node.children.extend(ancestor_data.children)
            data_node.children.extend(process.actual_instance.get_data_for_table_export()
                                  for process in self.processes.order_by("timestamp").iterator())
        return data_node


    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :Return:
          the tree node for this model instance

        :rtype: ``chantal_common.search.SearchTreeNode``
        """
        search_fields = [search.TextSearchField(cls, "name"),
                         search.TextSearchField(cls, "currently_responsible_person", "username"),
                         search.TextSearchField(cls, "current_location"), search.TextSearchField(cls, "purpose"),
                         search.TextSearchField(cls, "tags"), search.TextNullSearchField(cls, "topic", "name")]
        related_models = dict((model, "processes") for model in get_all_searchable_physical_processes())
        related_models[Result] = "processes"
        # FixMe: The following line must be removed but not before possible
        # problems are tackled.
        related_models[Process] = "processes"
        if hasattr(cls, "sample_details"):
            return search.DetailsSearchTreeNode(cls, related_models, search_fields, "sample_details")
        else:
            return search.SearchTreeNode(cls, related_models, search_fields)


class SampleAlias(models.Model):
    """Model for former names of samples.  If a sample gets renamed (for
    example, because it was deposited), its old name is moved here.  Note that
    aliases needn't be unique.  Two old names may be the same.

    Note that they may be equal to a ``Sample.name``.  However, when accessing
    a sample by its name in the URL, this shadows any aliases of the same
    name.  Only if you look for the name by the search function, you also find
    aliases of the same name.
    """
    name = models.CharField(_("name"), max_length=255)
    sample = models.ForeignKey(Sample, verbose_name=_("sample"), related_name="aliases")

    class Meta:
        unique_together = (("name", "sample"),)
        verbose_name = _("name alias")
        verbose_name_plural = _("name aliases")

    def save(self, *args, **kwargs):
        """Saves the instance and touches the affected sample.
        """
        super(SampleAlias, self).save(*args, **kwargs)
        self.sample.save(with_relations=False)

    def __unicode__(self):
        return self.name


class SampleSplit(Process):
    """A process where a sample is split into many child samples.  The sample
    split itself is a process of the *parent*, whereas the children point to it
    through `Sample.split_origin`.  This way one can walk through the path of
    relationship in both directions.
    """
        # Translators: parent of a sample
    parent = models.ForeignKey(Sample, verbose_name=_("parent"))
    """This field exists just for a fast lookup.  Its existence is actually a
    violation of the non-redundancy rule in database models because one could
    find the parent via the samples attribute every process has, too."""

    class Meta(Process.Meta):
        verbose_name = _("sample split")
        verbose_name_plural = _("sample splits")

    def __unicode__(self):
        _ = ugettext
        return _("split of {parent_name}").format(parent_name=self.parent.name)

    def get_cache_key(self, user_settings_hash, local_context):
        """Calculate a cache key for this context instance of the sample
        split.  Here, I actually use `local_context` in order to generate
        different cached items for different positions of the sample split in
        the process list.  The underlying reason for it is that in contrast to
        other process classes, the display of sample splits depends on many
        things.  For example, if the sample split belongs to the sample the
        datasheet of which is displayed, the rendering is different from the
        very same sample split on the data sheet of a child sample.
        """
        hash_ = hashlib.sha1()
        hash_.update(user_settings_hash)
        hash_.update("\x04{0}\x04{1}\x04{2}".format(local_context.get("original_sample", ""),
                                                    local_context.get("latest_descendant", ""),
                                                    local_context.get("sample", "")))
        return "process:{0}-{1}".format(self.pk, hash_.hexdigest())

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if context["sample"] != context["original_sample"]:
            context["parent"] = context["sample"]
        else:
            context["parent"] = None
        if context["sample"].last_process_if_split() == self and \
                permissions.has_permission_to_edit_sample(user, context["sample"]):
            context["resplit_url"] = django.core.urlresolvers.reverse(
                "samples.views.split_and_rename.split_and_rename", kwargs={"old_split_id": self.pk})
        else:
            context["resplit_url"] = None
        return super(SampleSplit, self).get_context_for_user(user, context)

    @classmethod
    def get_search_tree_node(cls):
        raise NotImplementedError


class Clearance(models.Model):
    """Model for clearances for specific samples to specific users.  Apart
    from unblocking the sample itself (at least, some fields), particular
    processes can be unblocked, too.

    Note that the processes needn't be processes connected with the sample.
    They may also belong to one of its ancestors.
    """
    user = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("user"), related_name="clearances")
    sample = models.ForeignKey(Sample, verbose_name=_("sample"), related_name="clearances")
    processes = models.ManyToManyField(Process, verbose_name=_("processes"), related_name="clearances", blank=True)
    last_modified = models.DateTimeField(_("last modified"), auto_now=True, auto_now_add=True)

    class Meta:
        unique_together = ("user", "sample")
        verbose_name = _("clearance")
        verbose_name_plural = _("clearances")

    def __unicode__(self):
        _ = ugettext
        return _("clearance of {sample} for {user}").format(sample=self.sample, user=self.user)


class SampleClaim(models.Model):
        # Translators: someone who assert a claim to samples
    requester = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("requester"), related_name="claims")
    reviewer = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("reviewer"),
                                 related_name="claims_as_reviewer")
    samples = models.ManyToManyField(Sample, related_name="claims", verbose_name=_("samples"))
        # Translators: "closed" claim to samples
    closed = models.BooleanField(_("closed"), default=False)

    class Meta:
        verbose_name = _("sample claim")
        verbose_name_plural = _("sample claims")

    def __unicode__(self):
        _ = ugettext
        return _("sample claim #{number}").format(number=self.pk)

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.claim.show", (self.pk,))


sample_death_reasons = (
    ("split", _("completely split")),
    ("lost", _("lost and unfindable")),
    ("destroyed", _("completely destroyed")),
    )
"""Contains all possible choices for `SampleDeath.reason`.
"""

class SampleDeath(Process):
    """This special process marks the end of the sample.  It can have various
    reasons accoring to `sample_death_reasons`.  It is impossible to add
    processes to a sample if it has a `SampleDeath` process, and its timestamp
    must be the last.
    """
        # Translators: Of a sample
    reason = models.CharField(_("cause of death"), max_length=50, choices=sample_death_reasons)

    class Meta(Process.Meta):
            # Translators: Of a sample
        verbose_name = _("cease of existence")
            # Translators: Of a sample
        verbose_name_plural = _("ceases of existence")

    def __unicode__(self):
        _ = ugettext
        try:
            # Translators: Of a sample
            return _("cease of existence of {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            # Translators: Of a sample
            return _("cease of existence #{number}").format(number=self.pk)

    @classmethod
    def get_search_tree_node(cls):
        raise NotImplementedError


image_type_choices = (("none", _("none")),
                    ("pdf", "PDF"),
                    ("png", "PNG"),
                    ("jpeg", "JPEG"),
                    )

class Result(Process):
    """Adds a result to the history of a sample.  This may be just a comment,
    or a plot, or an image, or a link.
    """
        # Translators: Of a result
    title = models.CharField(_("title"), max_length=50)
    image_type = models.CharField(_("image file type"), max_length=4, choices=image_type_choices, default="none")
        # Translators: Physical quantities are meant
    quantities_and_values = models.TextField(_("quantities and values"), blank=True, help_text=_("in JSON format"))
    """This is a data structure, serialised in JSON.  If you de-serialise it,
    it is a tuple with two items.  The first is a list of unicodes with all
    quantities (the table headings).  The second is a list of lists with
    unicodes (the values; the table cells).  The outer list is the set of rows,
    the inner the columns.  No Markdown is used here, just plain strings.  (The
    HTML entity substitution in quantities has taken place already *before*
    anyting is written here.)
    """

    class Meta(Process.Meta):
            # Translators: experimental result
        verbose_name = _("result")
            # Translators: experimental results
        verbose_name_plural = _("results")

    def save(self, *args, **kwargs):
        """Do everything in `Process.save`, plus touching all samples in all
        connected sample series and the series themselves.
        """
        with_relations = kwargs.get("with_relations", True)
        super(Result, self).save(*args, **kwargs)
        if with_relations:
            for sample_series in self.sample_series.all():
                sample_series.save(touch_samples=True)

    def __unicode__(self):
        _ = ugettext
        try:
            # Translators: experimental result
            return _("result for {sample}").format(sample=self.samples.get())
        except (Sample.DoesNotExist, Sample.MultipleObjectsReturned):
            try:
                # Translators: experimental result
                return _("result for {sample}").format(sample=self.sample_series.get())
            except (SampleSeries.DoesNotExist, SampleSeries.MultipleObjectsReturned):
                # Translators: experimental result
                return _("result #{number}").format(number=self.pk)

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.result.show", (self.pk,))

    def get_image_locations(self):
        """Get the location of the image in the local filesystem as well
        as on the webpage.

        Every image exist twice on the local filesystem.  First, it is in
        ``settings.MEDIA_ROOT/results``.  (Typically, ``MEDIA_ROOT`` is
        ``/var/www/juliabase/uploads/`` and should be backuped.)  This is the
        original file, uploaded by the user.  Its filename is ``"0"`` plus the
        respective file extension (jpeg, png, or pdf).  The sub-directory is
        the primary key of the result.  (This allows for more than one image
        per result in upcoming JuliaBase versions.)

        Secondly, there are the thumbnails as either a JPEG or a PNG, depending
        on the original file type, and stored in ``settings.MEDIA_ROOT``.

        :Return:
          a dictionary containing the following keys:

          =========================  =========================================
                 key                           meaning
          =========================  =========================================
          ``"image_file"``           full path to the original image file
          ``"image_url"``            full relative URL to the image
          ``"thumbnail_file"``       full path to the thumbnail file
          ``"thumbnail_url"``        full relative URL to the thumbnail (i.e.,
                                     without domain)
          =========================  =========================================

        :rtype: dict mapping str to str
        """
        assert self.image_type != "none"
        original_extension = "." + self.image_type
        thumbnail_extension = ".jpeg" if self.image_type == "jpeg" else ".png"
        sluggified_filename = defaultfilters.slugify(self.title) + original_extension
        return {"image_file": os.path.join(settings.MEDIA_ROOT, "results", str(self.pk), "0" + original_extension),
                "image_url": django.core.urlresolvers.reverse(
                    "samples.views.result.show_image", kwargs={"process_id": str(self.pk)}),
                "thumbnail_file": os.path.join(settings.CACHE_ROOT, "results_thumbnails", str(self.pk),
                                               "0" + thumbnail_extension),
                "thumbnail_url": django.core.urlresolvers.reverse(
                    "samples.views.result.show_thumbnail", kwargs={"process_id": str(self.pk)}),
                "sluggified_filename": sluggified_filename}

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if self.quantities_and_values:
            if "quantities" not in context or "value_lists" not in context:
                context["quantities"], context["value_lists"] = json.loads(self.quantities_and_values)
            context["export_url"] = \
                django.core.urlresolvers.reverse("samples.views.result.export", kwargs={"process_id": self.pk})
        if "thumbnail_url" not in context or "image_url" not in context:
            if self.image_type != "none":
                image_locations = self.get_image_locations()
                context.update({"thumbnail_url": image_locations["thumbnail_url"],
                                "image_url": image_locations["image_url"]})
            else:
                context["thumbnail_url"] = context["image_url"] = None
        if permissions.has_permission_to_edit_result_process(user, self):
            context["edit_url"] = \
                django.core.urlresolvers.reverse("edit_result", kwargs={"process_id": self.pk})
        else:
            context["edit_url"] = None
        return super(Result, self).get_context_for_user(user, context)

    def get_data(self):
        """Extract the data of this result process as a tree of nodes (or a
        single node) with lists of key–value pairs, ready to be used for
        general data export.  In contrast to `get_data_for_table_export`, I
        export *all* attributes that may be interesting for the user, and even
        some related data.  Typically, this data is used if a non-browser
        client retrieves a single resource (*not* its table export!) and
        expects JSON output.

        Additionaly, nothing is translated here.  This is in order to have
        stable keys and values.  Otherwise, interpretation of the extracted
        data would be a nightmare.  This also means that you must pass a
        unicode to ``DataNode`` instead of an instance because an instance gets
        translated.

        :Return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = super(Result, self).get_data()
        data_node.name = data_node.descriptive_name = self.title
        quantities, values_lists = json.loads(self.quantities_and_values)
        quantities_and_values = []
        for i, quantity in enumerate(quantities):
            values = [values[i] for values in values_lists]
            quantities_and_values.append((quantity, values))
        data_node.items.extend([DataItem("title", self.title),
                                DataItem("image type", self.image_type),
                                DataItem("quantities and values", quantities_and_values),
                                DataItem("sample series", self.sample_series.values_list("name", flat=True))])
        return data_node

    def get_data_for_table_export(self):
        """Extract the data of this result process as a tree of nodes (or a
        single node) with lists of key–value pairs, ready to be used for the
        table data export.  See the `samples.views.table_export` module for all
        the glory details.

        However, I should point out the peculiarities of result processes in
        this respect.  Result comments are exported by the parent class, here
        just the table is exported.  If the table contains only one row (which
        should be the case almost always), only one data tree node is returned,
        with this row as the key–value list.

        If the result table has more than one row, for each row, a sub-node is
        generated, which contains the row columns in its key–value list.

        :Return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        _ = ugettext
        data_node = super(Result, self).get_data_for_table_export()
        data_node.name = data_node.descriptive_name = self.title
        quantities, value_lists = json.loads(self.quantities_and_values)
        if len(value_lists) > 1:
            for i, value_list in enumerate(value_lists):
                # Translators: In a table
                child_node = DataNode(_("row"), _("row #{number}").format(number=i + 1))
                child_node.items = [DataItem(quantities[j], value) for j, value in enumerate(value_list)]
                data_node.children.append(child_node)
        elif len(value_lists) == 1:
            data_node.items.extend([DataItem(quantity, value) for quantity, value in zip(quantities, value_lists[0])])
        return data_node


class SampleSeries(models.Model):
    """A sample series groups together zero or more `Sample`.  It must belong
    to a topic, and it may contain processes, however, only *result processes*.
    The ``name`` and the ``timestamp`` of a sample series can never change
    after it has been created.
    """
    name = models.CharField(_("name"), max_length=50, primary_key=True,
                            # Translators: The “Y” stands for “year”
                            help_text=_("must be of the form “originator-YY-name”"))
    timestamp = models.DateTimeField(_("timestamp"))
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, related_name="sample_series",
                                                     verbose_name=_("currently responsible person"))
    description = models.TextField(_("description"))
    samples = models.ManyToManyField(Sample, blank=True, verbose_name=_("samples"), related_name="series")
    results = models.ManyToManyField(Result, blank=True, related_name="sample_series", verbose_name=_("results"))
    topic = models.ForeignKey(Topic, related_name="sample_series", verbose_name=_("topic"))
    last_modified = models.DateTimeField(_("last modified"), auto_now=True, auto_now_add=True, editable=False)

    class Meta:
        verbose_name = _("sample series")
        verbose_name_plural = pgettext_lazy("plural", "sample series")

    def save(self, *args, **kwargs):
        """Saves the instance.

        :Parameters:
          - `touch_samples`: If ``True``, also touch all samples in this
            series.  ``False`` is default because samples don't store
            information about the sample series that may change (note that the
            sample series' name never changes).

        :type touch_samples: bool
        """
        touch_samples = kwargs.pop("touch_samples", False)
        super(SampleSeries, self).save(*args, **kwargs)
        if touch_samples:
            for sample in self.samples.all():
                sample.save(with_relations=False)

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.sample_series.show", [self.name])

    def get_data(self):
        """Extract the data of this sample series as a tree of nodes with
        lists of key–value pairs, ready to be used for general data export.
        Every child of the top-level node is a sample of the sample series.  In
        contrast to `get_data_for_table_export`, I export *all* attributes that
        may be interesting for the user, and even some related data.
        Typically, this data is used if a non-browser client retrieves a single
        resource (*not* its table export!) and expects JSON output.

        Additionaly, nothing is translated here.  This is in order to have
        stable keys and values.  Otherwise, interpretation of the extracted
        data would be a nightmare.  This also means that you must pass a
        unicode to ``DataNode`` instead of an instance because an instance gets
        translated.

        :Return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = DataNode(self.name)
        data_node.children.extend(sample.get_data() for sample in self.samples.all())
        data_node.items = [DataItem("currently responsible person", self.currently_responsible_person),
                           DataItem("timestamp", self.timestamp),
                           DataItem("description", self.description),
                           DataItem("topic", self.topic)]
        return data_node

    def get_data_for_table_export(self):
        """Extract the data of this sample series as a tree of nodes with
        lists of key–value pairs, ready to be used for the data export.  Every
        child of the top-level node is a sample of the sample series.  See the
        `samples.views.table_export` module for all the glory details.

        :Return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        _ = ugettext
        data_node = DataNode(self, unicode(self))
        data_node.children.extend(sample.get_data_for_table_export() for sample in self.samples.all())
        # I don't think that any sample series properties are interesting for
        # table export; people only want to see the *sample* data.  Thus, I
        # don't set ``cvs_note.items``.
        return data_node

    def touch_samples(self):
        """Touch all samples of this series for cache expiring.  This isn't
        done in a custom ``save()`` method because sample don't store
        information about the sample series that may change (note that the
        sample series' name never changes).
        """
        for sample in self.samples.all():
            sample.save(with_relations=False)

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :Return:
          the tree node for this model instance

        :rtype: ``chantal_common.search.SearchTreeNode``
        """
        search_fields = [search.TextSearchField(cls, "name"),
                         search.TextSearchField(cls, "currently_responsible_person", "username"),
                         search.DateTimeSearchField(cls, "timestamp"), search.TextSearchField(cls, "description"),
                         search.TextSearchField(cls, "topic", "name")]
        related_models = {Sample: "samples", Result: "results"}
        return search.SearchTreeNode(cls, related_models, search_fields)

    def get_hash_value(self):
        """Calculates a sha1 hash value out of the sample series name

        :Return:
         sha1 hash hex value

        :rtype: str
        """
        return hashlib.sha1(self.name.encode("utf-8")).hexdigest()


class Initials(models.Model):
    """Model for initials of people or external operators.  They are used to
    build namespaces for sample names and sample series names.  They must match
    the regular expression ``"[A-Z]{2,4}[0-9]*"`` with the additional
    constraint to be no longer than 4 characters.

    You should not delete an entry in this table, and you must never have an
    entry where ``user`` and ``external_operator`` are both set.  It is,
    however, possible to have both ``user`` and ``external_operator`` not set
    in case of initials that have been abandonned.  They should not be re-given
    though.  “Should not” means here “to be done only by the administrator
    after thorough examination”.
    """
    initials = models.CharField(_("initials"), max_length=4, primary_key=True)
    user = models.OneToOneField(django.contrib.auth.models.User, verbose_name=_("user"),
                                related_name="initials", null=True, blank=True)
    external_operator = models.OneToOneField(ExternalOperator, verbose_name=_("external operator"),
                                             related_name="initials", null=True, blank=True)

    class Meta:
        verbose_name = _("initials")
        verbose_name_plural = pgettext_lazy("plural", "initialses")

    def __unicode__(self):
        return self.initials


class UserDetails(models.Model):
    """Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_("user"),
                                related_name="samples_user_details")
    auto_addition_topics = models.ManyToManyField(
        Topic, blank=True, related_name="auto_adders", verbose_name=_("auto-addition topics"),
        help_text=_("new samples in these topics are automatically added to “My Samples”"))
    only_important_news = models.BooleanField(_("get only important news"), default=False)
    my_layers = models.TextField(_("my layers"), blank=True, help_text=_("in JSON format"))
    """This string is the JSON serialisation of the list with contains
    3-tuples of the the form ``(nickname, deposition, layer)``, where
    “deposition” is the *process id* (``Process.pk``, not the deposition
    number!) of the deposition, and “layer” is the layer number
    (`models_depositions.Layer.number`).
    """
    display_settings_timestamp = models.DateTimeField(_("display settings last modified"), auto_now_add=True)
    """This timestamp denotes when anything changed which influences the
    display of a sample, process, sample series etc which is not covered by
    other timestamps.  See `touch_display_settings`.
    """
    my_samples_timestamp = models.DateTimeField(_("My Samples last modified"), auto_now_add=True)
    """This timestamp denotes when My Samples were changed most recently.  It
    is used for expiring sample datasheet caching.
    """
    idenfifying_data_hash = models.CharField(_("identifying data hash"), max_length=40)
    """Contains the SHA1 hash of the username, first name, and family name of
    the user.  It is used for efficient caching.  If the name of the user
    changes, all connected processes, samples, and sample series must be
    expired in the cache.  If other things on the user data are changed (in
    particular, the "last_login" field at each login of the user), nothing must
    be done.  In order to be able to distinguish between the two cases, we save
    the old data here, for comparison.
    """
    subscribed_feeds = models.ManyToManyField(ContentType, related_name="subscribed_users",
                                              verbose_name=_("subscribed newsfeeds"), blank=True)
    default_folded_process_classes = models.ManyToManyField(ContentType, related_name="dont_show_to_user",
                                              verbose_name=_("folded processes"), blank=True)
    folded_processes = models.TextField(_("folded processes"), blank=True, help_text=_("in JSON format"),
                                        default="{}")
    visible_task_lists = models.ManyToManyField(ContentType, related_name="task_lists_from_user",
                                                verbose_name=_("visible task lists"), blank=True)
    folded_topics = models.TextField(_("folded topics"), blank=True, help_text=_("in JSON format"),
                                     default="[]")
    folded_series = models.TextField(_("folded sample series"), blank=True, help_text=_("in JSON format"),
                                     default="[]")
    show_users_from_department = models.ManyToManyField(Department, related_name="shown_users",
                                                        verbose_name=_("show users from department"), blank=True)


    class Meta:
        verbose_name = _("user details")
        verbose_name_plural = _("user details")
        _ = lambda x: x
        permissions = (("edit_permissions_for_all_physical_processes",
                        _("Can edit permissions for all physical processes")),)

    def __unicode__(self):
        return unicode(self.user)

    def touch_display_settings(self):
        """Set the last modifications of sample settings to the current time.
        This method must be called every time when something was changed which
        influences the display of a sample datasheet (and is not covered by
        other timestamps (``my_samples_timestamp``,
        `chantal_common.models.UserDetails.layout_last_modified`), e. g. topic
        memberships.  It is used for efficient caching.
        """
        self.display_settings_timestamp = datetime.datetime.now()
        self.save()


status_level_choices = (
    ("undefined", _("undefined")),
    ("red", _("red")),
    ("yellow", _("yellow")),
    ("green", _("green"))
)

class StatusMessage(models.Model):
    """This class is for the current status of the processes.  The class
    discusses whether the process is available, or is currently out of service.
    It provides a many to many relationship between the status messages and the
    processes.
    """
    process_classes = models.ManyToManyField(ContentType, related_name="status_messages", verbose_name=_("processes"))
    timestamp = models.DateTimeField(_("timestamp"))
    begin = models.DateTimeField(_("begin"), null=True, blank=True, help_text=_("YYYY-MM-DD HH:MM:SS"))
    end = models.DateTimeField(_("end"), null=True, blank=True, help_text=_("YYYY-MM-DD HH:MM:SS"))
    begin_inaccuracy = models.PositiveSmallIntegerField(_("begin inaccuracy"), choices=timestamp_inaccuracy_choices,
                                                        default=0)
    end_inaccuracy = models.PositiveSmallIntegerField(_("end inaccuracy"), choices=timestamp_inaccuracy_choices, default=0)
    operator = models.ForeignKey(django.contrib.auth.models.User, related_name="status_messages",
                                 verbose_name=_("reporter"))
    message = models.TextField(_("message"), blank=True)
    status_level = models.CharField(_("level"), choices=status_level_choices, default="undefined", max_length=10)
    withdrawn = models.BooleanField(_("withdrawn"), default=False)

    class Meta:
        verbose_name = _("status message")
        verbose_name_plural = _("status messages")

    def __unicode__(self):
        _ = ugettext
        return _("status message #{number}").format(number=self.pk)


status_choices = (
    ("0 finished", _("finished")),
    ("1 new", _("new")),
    ("2 accepted", _("accepted")),
    ("3 in progress", _("in progress"))
)
priority_choices = (
    ("0 critical", _("critical")),
    ("1 high", _("high")),
    ("2 normal", _("normal")),
    ("3 low", _("low"))
)

class Task(models.Model):
    """
    """
    status = models.CharField(_("status"), max_length=15, choices=status_choices, default="1 new")
    customer = models.ForeignKey(django.contrib.auth.models.User, related_name="tasks", verbose_name=_("customer"))
    creating_timestamp = models.DateTimeField(_("created at"), help_text=_("YYYY-MM-DD HH:MM:SS"),
                                              auto_now_add=True, editable=False)
    last_modified = models.DateTimeField(_("last modified"), help_text=_("YYYY-MM-DD HH:MM:SS"),
                                         auto_now=True, auto_now_add=True, editable=False)
    operator = models.ForeignKey(django.contrib.auth.models.User, related_name="operated tasks",
                                 verbose_name=_("operator"), null=True, blank=True)
    process_class = models.ForeignKey(ContentType, related_name="tasks", verbose_name=_("process class"))
    finished_process = models.ForeignKey(Process, related_name="task", null=True, blank=True,
                                         verbose_name=_("finished process"))
    samples = models.ManyToManyField(Sample, related_name="task", verbose_name=_("samples"))
    comments = models.TextField(_("comments"), blank=True)
    priority = models.CharField(_("priority"), max_length=15, choices=priority_choices, default="2 normal")

    class Meta:
        verbose_name = _("task")
        verbose_name_plural = _("tasks")

    def __unicode__(self):
        _ = ugettext
        return _("task of {process_class} from {datetime}". format(
                process_class=self.process_class.name, datetime=self.creating_timestamp))

    def get_absolute_url(self):
        return "{0}#task_{1}".format(django.core.urlresolvers.reverse("samples.views.task_lists.show"), self.id)


class ProcessWithSamplePositions(models.Model):
    """An abstract class for saving the positions of the samples
    in an apparatus.
    The ``sample_positions`` field may be used by derived models for storing
    where the samples were mounted during the deposition.  Sometimes it is
    interesting to know that because the deposition device may not work
    homogeneously.  It is placed here in order to be able to extend the
    split-after-deposition view so that it offers input fields for it if it is
    applicable.  (For example, this can be given in the query string.)
    """
    sample_positions = models.TextField(_("sample positions"), default="{}", help_text=_("in JSON format"))
    """In JSON format, mapping sample IDs to positions.  Positions can be
    numbers or strings."""
    class Meta:
        abstract = True

    def get_sample_position_context(self, user, old_context):
        context = old_context.copy()
        if "sample_position" not in context:
            sample = context.get("sample")
            sample_positions_dict = json.loads(self.sample_positions)
            if sample_positions_dict and sample:
                context["sample_position"] = (sample if (sample.topic and not sample.topic.confidential) or
                                                    permissions.has_permission_to_fully_view_sample(user, sample) or
                                                    permissions.has_permission_to_add_edit_physical_process(user, self,
                                                                                    self.content_type.model_class())
                                                    else _("confidential sample"),
                                                    sample_positions_dict[unicode(sample.id)])
        if "sample_positions" not in context:
            sample_positions_dict = json.loads(self.sample_positions)
            if sample_positions_dict:
                context["sample_positions"] = collections.OrderedDict((sample if (sample.topic and not sample.topic.confidential) or
                                                    permissions.has_permission_to_fully_view_sample(user, sample) or
                                                    permissions.has_permission_to_add_edit_physical_process(user, self,
                                                                                    self.content_type.model_class())
                                                    else _("confidential sample"),
                                                    sample_positions_dict[unicode(sample.id)])
                                                   for sample in self.samples.order_by("name").iterator())
        return context


    def get_cache_key(self, user_settings_hash, local_context):
        """Generates an own cache key for every instance of this process.
        When a process inherits from both ``Process`` class and
        ``ProcessWithSamplePositions`` class, you have to make shure, that the
        process uses this method for the cache key and not the method from
        the ``Process`` class.

        For the parameter description see
            ``samples.models_common.Process.get_cache_key()``
        """
        hash_ = hashlib.sha1()
        hash_.update(user_settings_hash)
        hash_.update("\x04{0}".format(local_context.get("sample", "")))
        return "process:{0}-{1}".format(self.pk, hash_.hexdigest())
