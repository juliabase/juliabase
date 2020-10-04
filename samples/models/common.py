# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""The most basic models like `Sample`, `Process`, `SampleSeries`,
`UserDetails` etc.  It is important to see that this module is imported by
almost all other models modules.  Therefore, you *must* *not* import any
JuliaBase models module here, in particular not ``models.py``.  Otherwise,
you'd end up with irresolvable cyclic imports.  In order to avoid cyclic
import, it is sometimes (e.g. for ``samples.permissions``) necessary to avoid
the ``from`` keyword.
"""

import hashlib, os.path, collections, datetime, html
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext, pgettext_lazy, get_language
from django.utils.http import urlquote
import django.utils.timezone
from django.contrib.contenttypes.models import ContentType
from django.template import Context, TemplateDoesNotExist
import django.utils.text
from django.template.loader import render_to_string
import django.urls
from django.conf import settings
from django.db import models
from django.core.cache import cache
from jb_common.utils.base import get_really_full_name, cache_key_locked, format_enumeration, camel_case_to_underscores
from jb_common.models import Topic, PolymorphicModel, Department
import samples.permissions
from jb_common import search
from samples.data_tree import DataNode, DataItem


def empty_list():
    return []

def empty_dict():
    return {}

def empty_double_list():
    return [[], []]


_table_export_blacklist = {"actual_object_id", "id", "content_type", "timestamp_inaccuracy", "last_modified"}
"""Set of field names that should never be included by `fields_to_data_items`.
"""

def fields_to_data_items(instance, data_node, additional_blacklist=frozenset()):
    """Adds all fields of a model instance to the items of a data node.  This
    function is called inside :py:meth:`Process.get_data_for_table_export` in
    order to conveniently fill the :py:class:`~samples.data_tree.DataNode` with
    the fields.

    :param instance: model field instance from which this is called
    :param data_node: the data node the items of which the fields should be
        added; this means, it is changed in place
    :param additional_blacklist: field names that should not be added

    :type instance: model.Model
    :type data_node: `samples.data_tree.DataNode`
    :type additional_blacklist: set of str
    """
    blacklist = _table_export_blacklist | additional_blacklist
    for field in instance._meta.fields:
        if field.name not in blacklist and not field.name.endswith("_ptr"):
            if field.choices:
                value = getattr(instance, "get_{}_display".format(field.name))()
            else:
                value = getattr(instance, field.name)
                if isinstance(value, django.contrib.auth.models.User):
                    value = get_really_full_name(value)
            try:
                unit = "/" + field.unit
            except AttributeError:
                unit = ""
            data_node.items.append(DataItem(html.unescape(field.verbose_name + unit), value, field.model.__name__.lower()))


def remove_data_item(instance, data_node, field_name):
    """Remove an item from a `~samples.data_tree.DataNode` with a certain key.
    This is called from a `get_data_for_table_export` method for refine the
    `~samples.data_tree.DataNode`.  Typically, the items of the
    `~samples.data_tree.DataNode` have been populated by an inherited
    `fields_to_data_items`, and in this step, too many fields were added.  This
    can be corrected by call this function.

    :param instance: model field instance from which this is called
    :param data_node: the data node the items of which should be filtered; this
        means that this variable is changed in place
    :param field_name: name of the field to be removed, if available

    :type instance: model.Model
    :type data_node: `samples.data_tree.DataNode`
    :type field_name: str
    """
    key = instance._meta.get_field(field_name).verbose_name
    data_node.items = [item for item in data_node.items if item.key != key]


class ExternalOperator(models.Model):
    """Some samples and processes are not made in our institute but in external
    institutions.  This is realised by setting the `Process.external_operator`
    field, which in turn contains `ExternalOperator`.
    """
    name = models.CharField(_("name"), max_length=30, unique=True)
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
        default_permissions = ()
        permissions = (("add_externaloperator", _("Can add an external operator")),
                       ("view_every_externaloperator", _("Can view all external operators")))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        for process in self.processes.all():
            process.actual_instance.save()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return django.urls.reverse("samples:show_external_operator", args=(self.pk,))


class Process(PolymorphicModel):
    """This is the parent class of all processes and measurements.  Actually,
    it is an *abstract* base class, i.e. there are no processes in the database
    that are *just* processes.  However, it is not marked as ``abstract=True``
    in the ``Meta`` subclass because I must be able to link to it with
    ``ForeignKey``.

    Note that derived processes might set their own primary key.  So if you
    need the process as such to identify uniquely within the set of all
    processes, you must use the ``id`` attribute rather than the ``pk``
    attribute.

    If you retrieve a `Process`, you may read (inherited) field
    `actual_instance` to get the actual object, e.g. a `SixChamberDeposition`::

        process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id))
        process = process.actual_instance
    """

    class TimestampInaccuracy(models.IntegerChoices):
            # Translators: It's about timestamps
        TOTAL = 0, _("totally accurate")
        MINUTE = 1, _("accurate to the minute")
        HOUR = 2, _("accurate to the hour")
        DAY = 3, _("accurate to the day")
        MONTH = 4, _("accurate to the month")
        YEAR = 5, _("accurate to the year")
        NOT_EVEN_YEAR = 6, _("not even accurate to the year")

    timestamp = models.DateTimeField(_("timestamp"))
    timestamp_inaccuracy = models.PositiveSmallIntegerField(_("timestamp inaccuracy"), choices=TimestampInaccuracy.choices,
                                                            default=TimestampInaccuracy.TOTAL)
    operator = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("operator"),
                                 related_name="processes")
    external_operator = models.ForeignKey(ExternalOperator, models.CASCADE, verbose_name=_("external operator"),
                                          null=True, blank=True, related_name="processes")
    comments = models.TextField(_("comments"), blank=True)
    last_modified = models.DateTimeField(_("last modified"), auto_now=True)
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

        :param with_relations: If ``True`` (default), also touch the related
            samples.  Should be set to ``False`` if called from another
            ``save`` method in order to avoid endless recursion.

        :type with_relations: bool
        """
        keys_list_key = "process-keys:{0}".format(self.id)
        with cache_key_locked("process-lock:{0}".format(self.id)):
            keys = cache.get(keys_list_key)
            if keys:
                cache.delete_many(keys)
            cache.delete(keys_list_key)
        with_relations = kwargs.pop("with_relations", True)
        super().save(*args, **kwargs)
        if with_relations:
            for sample in self.samples.all():
                sample.save(with_relations=False)

    def __str__(self):
        self = self.actual_instance
        samples = self.samples.values_list("name", flat=True)
        try:
            field_name = self.JBMeta.identifying_field
        except AttributeError:
            field_name = None
        if field_name:
            # Translators: Label for a process instance, e.g. “thickness
            # measurement 26”.
            return _("{process_class_name} {identifier}"). \
                format(process_class_name=self._meta.verbose_name, identifier=getattr(self, field_name))
        elif samples:
            # Translators: Label for a process instance, e.g. a measurement,
            # e.g. “thickness measurement of 01B-410”.  Singular/plural refers
            # to {samples}.
            return ungettext("{process_class_name} of {samples}", "{process_class_name} of {samples}", len(samples)). \
                format(process_class_name=self._meta.verbose_name, samples=format_enumeration(samples))
        else:
            # Translators: Label for a process instance, e.g. “thickness
            # measurement 26”.
            return _("{process_class_name} {identifier}"). \
                format(process_class_name=self._meta.verbose_name, identifier=self.id)

    def get_absolute_url(self):
        """Returns the relative URL (ie, without the domain name) of the
        database object.  Django calls this method ``get_absolute_url`` to make
        clear that *only* the domain part is missing.  Apart from that, it
        includes the full URL path to where the object can be seen.

        Note that Django itself uses this method in its built-in syndication
        framework.  However currently, JuliaBase uses it only explicitly in
        re-directions and links in templates.

        :return:
          Relative URL, however, starting with a “/”, to the page where one can
          view the object.

        :rtype: str
        """
        return django.urls.reverse("samples:show_process", args=(str(self.id),))

    def calculate_plot_locations(self, plot_id=""):
        """Get the location of a plot in the local filesystem as well as on
        the webpage.  Usually, you will not override this method.

        :param plot_id: the unique ID of the image.  This is mostly ``""``
            because most measurement models have only one graphics.

        :type plot_id: str

        :return:
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
            plot_url = django.urls.reverse("samples:default_process_plot", kwargs={"process_id": str(self.id)})
            thumbnail_url = django.urls.reverse("samples:default_process_plot_thumbnail", kwargs={"process_id": str(self.id)})
        else:
            plot_url = django.urls.reverse("samples:process_plot", kwargs={"process_id": str(self.id), "plot_id": plot_id})
            thumbnail_url = django.urls.reverse("samples:process_plot_thumbnail",
                                                kwargs={"process_id": str(self.id), "plot_id": plot_id})
        basename = "{0}-{1}-{2}-{3}-{4}".format(
            self.content_type.app_label, self.content_type.model, get_language(), self.id, plot_id)
        return {"plot_file": os.path.join("plots", basename + ".pdf"),
                "plot_url": plot_url,
                "thumbnail_file": os.path.join("plots", basename + ".png"),
                "thumbnail_url": thumbnail_url}

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        """Generate a plot using Matplotlib commands.  You may do whatever you
        want here – but eventually, there must be a savable Matplotlib plot in
        the `axes`.  The ``filename`` parameter is not really necessary but it
        makes things a little bit faster and easier.

        This method must be overridden in derived classes that wish to offer
        plots.

        :param axes: The Matplotlib axes to which the plot must be drawn.  You
            call methods of this parameter to draw the plot,
            e.g. ``axes.plot(x_values, y_values)``.
        :param plot_id: The ID of the plot.  For most models offering plots,
            this can only be the empty string and as such is not used it all in
            this method.
        :param filename: the filename of the original data file; it may also be
            a list of filenames if more than one file lead to the plot
        :param for_thumbnail: whether we do a plot for the thumbnail bitmap; for
            simple plots, this can be ignored

        :type axes: matplotlib.axes.Axes
        :type plot_id: str
        :type filename: str or list of str
        :type for_thumbnail: bool

        :raises samples.utils.plots.PlotError: if anything went wrong during
            the generation of the plot
        """
        raise NotImplementedError

    def get_datafile_name(self, plot_id):
        """Get the name of the file with the original data for the plot with
        the given ``plot_id``.  It may also be a list of filenames if more than
        one file lead to the plot.

        This method must be overridden in derived classes that wish to offer
        plots.

        :param plot_id: the ID of the plot.  For most models offering plots,
            this can only be the empty string and as such is not used it all in
            this method.  Note that you must not assume that its value is
            valid.

        :type plot_id: str

        :return:
          The absolute path of the file(s) with the original data for this plot
          in the local filesystem.  It's ``None`` if there is no plot available
          for this process.  If there are no raw datafile but you want to draw
          a plot nevertheless (e.g. from process data), return an empty list.

        :rtype: list of str, str, or NoneType
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

        :param plot_id: the ID of the plot.  For most models offering plots,
            this can only be the empty string and as such is not used it all in
            this method then.

        :type plot_id: str

        :return:
          the base name for the plot files, without directories or extension

        :rtype: str
        """
        basename = "{0}_{1}".format(camel_case_to_underscores(self.__class__.__name__), self.id)
        if plot_id:
            basename += "_" + plot_id
        return basename

    def get_data(self):
        """Extract the data of this process as a dictionary, ready to be used for
        general data export.  In contrast to `get_data_for_table_export`, I
        export all fields automatically of the instance, including foreign
        keys.  In addition to all fields, it exports the IDs of the contained
        samples with the key ``"samples"``.  It does not, however, include
        reverse relations of derived processes automatically.  Typically, this
        data is used when a non-browser client retrieves a single resource and
        expects JSON output.

        You will rarely need to override this method.  One case is if you need
        to include reverse relation fields, e.g. of sub-measurements.

        :return:
          the content of all fields of this process

        :rtype: `dict`
        """
        data = {field.name: getattr(self, field.name) for field in self._meta.fields
                if field.name not in {"actual_object_id", "process_ptr"}}
        data["samples"] = list(self.samples.values_list("id", flat=True))
        if "sample_positions" in data:
            data["sample_positions"] = data["sample_positions"]
        return data

    def get_data_for_table_export(self):
        """Extract the data of this process as a tree of nodes (or a single
        node) with lists of key–value pairs, ready to be used for the table
        data export.  See the `samples.views.table_export` module for all the
        glory details.

        If you're lucky, you don't need to override this method in derived
        processes.  You may need to do this in case of sub-models contained in
        a reverse foreign key.  Note that the `Deposition` class can handle
        layers already.  Moreover, you may wish to refine the
        `~samples.data_tree.DataNode` by adding further fields and by using
        `remove_data_item`.

        :return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = DataNode(self)
        fields_to_data_items(self, data_node)
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

        :param user_settings_hash: hash over all settings which affect the
            rendering of processes, e. g. language
        :param local_context: the local sample context; currently, this is only
            relevant to `SampleSplit`, see
            :py:meth:`SampleSplit.get_cache_key`.

        :type user_settings_hash: str
        :type local_context: dict mapping str to ``object``

        :return:
          the cache key for this process instance

        :rtype: str
        """
        return "process:{0}-{1}".format(self.id, user_settings_hash)

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
        ``export_url``, ``duplicate_url``, and ``delete_url``.  It may also
        have further fields, which must be interpreted by the respective
        ``"show_…"`` template.

        It is very important to see that ``html_body`` (the result of the
        ``show_<process name>.html`` template) must not depend on sample data!
        Otherwise, you see outdated process data after having changed sample
        data.  (There is only one exception: sample splits.)  If you really
        need this dependency, then expire the cached sample items yourself in a
        signal function.

        Note that it is necessary that ``self`` is the actual instance and not
        a parent class.

        :param user: the current user
        :param old_context: The present context for the process.  This may be
             only the sample context (i. e. ``sample``, ``original_sample``
             etc) if the process hasn't been found in the cache. Otherwise, it
             is the full process context, although (possibly) for another user,
             so it needs to be adapted.  This dictionary will not be touched in
             this method.

        :type user: django.contrib.auth.models.User
        :type old_context: dict mapping str to ``object``

        :return:
          the adapted full context for the process

        :rtype: dict mapping str to ``object``
        """
        context = old_context.copy()
        if "browser_system" not in context:
            context["browser_system"] = user.jb_user_details.browser_system
        if "process" not in context:
            context["process"] = self
        if "name" not in context:
            name = str(self._meta.verbose_name) if not isinstance(self, Result) else self.title
            context["name"] = name[:1].upper() + name[1:]
        if hasattr(self, "get_sample_position_context"):
            context = self.get_sample_position_context(user, context)
        if "html_body" not in context:
            context["html_body"] = render_to_string(
                "samples/show_" + camel_case_to_underscores(self.__class__.__name__) + ".html", context)
            if "short_html_body" not in context:
                try:
                    context["short_html_body"] = render_to_string(
                        "samples/show-short_{0}.html". \
                            format(camel_case_to_underscores(self.__class__.__name__)), context)
                except TemplateDoesNotExist:
                    context["short_html_body"] = None
            if "extend_html_body" not in context:
                try:
                    context["extended_html_body"] = render_to_string(
                        "samples/show-extended_{0}.html". \
                            format(camel_case_to_underscores(self.__class__.__name__)), context)
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
        ``NotImplementedError`` or if the method doesn't exist at all, the
        respective model cannot be searched for.

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        if cls == Process:
            raise NotImplementedError
        search_fields = [search.TextSearchField(cls, "operator", "username"),
                         search.TextSearchField(cls, "external_operator", "name")]
        search_fields.extend(
            search.convert_fields_to_search_fields(cls, ["timestamp_inaccuracy", "last_modified", "finished"]))
        related_models = {Sample: "samples"}
        related_models.update(
            (related_object.related_model, related_object.get_accessor_name()) for related_object
            in cls._meta.get_fields() if related_object.one_to_many and related_object.auto_created
            and not related_object.related_model.__name__.startswith("Feed"))
        return search.SearchTreeNode(cls, related_models, search_fields)

    def delete(self, *args, **kwargs):
        """Deletes this process.  This function should be called on the actual
        instance.

        In contrast to ordinary Django ``delete`` methods, this method takes
        two optional optional keyword arguments for a dry run (no deletion).

        The dry run checks whether the deletion is allowed to the user.

        The dry run is realised within ``delete()`` instead of in a method of
        its own because the algorithms for both are very similar.  Thus, it
        avoids code duplication.

        *Important*: Any ``delete()`` you call in case of a dry run *must*
        support the ``dry_run`` argument.

        :param dry_run: If it is ``True``, nothing is actually deleted.
          Instead, the methods explores whether all affected objects can be
          deleted in the first place, and if so, which database objects are
          affected.
        :param user: The current user.  This must only be given if ``dry_run``
          is ``True``.

        :type dry_run: bool
        :type user: django.contrib.auth.models.User

        :return:
          If ``dry_run`` is not ``True``, the result of the original ``delete``
          method is returned.  Otherwise, a set of affected objects is
          returned.  It includes the current instance.  This may be used by the
          caller to generate an expressive and informative “Are you really
          sure” page.

          In most cases, this set will only contain the current instance.
          However sample splits, for example, also delete their pieces (and
          grand-pieces etc).  Moreover, samples deletions also delete processes
          which relate to only that sample.

        :rtype: (int, dict mapping ``Model`` to int) or set of ``Model``
        """
        # FixMe: This method by default forbids to delete a process.  The main
        # reason is that there is no general “can delete” assertion for
        # processes yet.  This is unfortunate because in every derived class
        # which should be allowed to be deleted, I cannot call this inherited
        # method during a dry run.  This is bad OOP and leads to duplicated
        # tests in the derived classes (e.g. for too old process).
        dry_run = kwargs.pop("dry_run", False)
        user = kwargs.pop("user", None)
        if dry_run:
            description = _("You are not allowed to delete the process “{process}” because this kind of process cannot be "
                            "deleted.").format(process=self)
            raise samples.permissions.PermissionError(user, description)
        else:
            self.save()
            # FixMe: The following line is necessary only until
            # https://code.djangoproject.com/ticket/17688 is fixed.
            self.samples.clear()
            return super().delete(*args, **kwargs)


class PhysicalProcess(Process):
    """Abstract class for physical processes.  These processes are “real”
    processes such as depositions, etching processes, measurements etc.  This
    class doesn't define anything.  Its main purpose is to bring structure to
    the class hierarchy by pooling all physical processes.

    Such processes can have permissions of the form ``"add_classname"``,
    ``"change_classname"``, ``"view_every_classname"`` and
    ``"edit_permissions_for_classname"`` where the model name is in lowercase
    with underscores.

    Normally, all four permissions are available.  However, you may omit
    ``"add_classname"`` if *every* user should be allowed to add such processes
    (and edit their own).

    You can omit ``"view_every_classname"`` if no-one should be allowed to see
    all processes (or see the lab notebook, which shouldn't even exist in this
    case for obvious reasons).

    If you omit ``"edit_permissions_for_classname"``, no email is sent if a
    particular user adds it first process of this kind.

    If neiter ``"add_classname"`` nor ``"edit_permissions_for_classname"`` is
    included, the process won't show up on the permissions list page.
    """
    class Meta(PolymorphicModel.Meta):
        abstract = True
        default_permissions = ()
        # I must repeat it here because I can derive ``Meta`` only from an
        # abstract ancestor, and this one doesn't have these fields.
        ordering = ["timestamp"]
        get_latest_by = "timestamp"

    def _urlresolve(self, prefix):
        prefix = self._meta.app_label + ":" + prefix
        class_name = camel_case_to_underscores(self.__class__.__name__)
        try:
            field_name = parameter_name = self.JBMeta.identifying_field
        except AttributeError:
            field_name, parameter_name = "id", class_name + "_id"
        # Quote it in order to allow slashs in values.
        field_value = urlquote(str(getattr(self, field_name)), safe="")
        try:
            return django.urls.reverse(prefix + class_name, kwargs={parameter_name: field_value})
        except django.urls.NoReverseMatch:
            return django.urls.reverse(prefix + class_name, kwargs={"process_id": field_value})

    def get_absolute_url(self):
        try:
            return self._urlresolve("show_")
        except django.urls.NoReverseMatch:
            return django.urls.reverse("samples:show_process", args=(str(self.id),))

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if samples.permissions.has_permission_to_edit_physical_process(user, self):
            try:
                context["edit_url"] = self._urlresolve("edit_")
            except django.urls.NoReverseMatch:
                context["edit_url"] = None
        else:
            context["edit_url"] = None
        if samples.permissions.has_permission_to_delete_physical_process(user, self):
            context["delete_url"] = django.urls.reverse("samples:delete_process_confirmation", kwargs={"process_id": self.pk})
        else:
            context["delete_url"] = None
        return super().get_context_for_user(user, context)

    @classmethod
    def get_add_link(cls):
        """Returns the URL to the “add” view for this process.  A physical process
        should define a named URL called ``"add_process_class_name"`` unless
        this process class should not be explicitly added by users (but is
        created by the program somehow).

        :return:
          the full URL to the add page for this process

        :rtype: str
        """
        try:
            return django.urls.reverse(cls._meta.app_label + ":add_" + camel_case_to_underscores(cls.__name__))
        except django.urls.NoReverseMatch:
            return None

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

    def delete(self, *args, **kwargs):
        dry_run = kwargs.get("dry_run", False)
        if dry_run:
            user = kwargs["user"]
            if self.timestamp < django.utils.timezone.now() - datetime.timedelta(hours=1):
                description = _("You are not allowed to delete the process “{process}” because it is older than "
                                "one hour.").format(process=self)
                raise samples.permissions.PermissionError(user, description)
            samples.permissions.assert_can_edit_physical_process(user, self)
            return {self}
        else:
            return super().delete(*args, **kwargs)


all_searchable_physical_processes = None
def get_all_searchable_physical_processes():
    """Returns all physical processes which have a ``get_search_tree_node``
    method.

    :return:
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
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, related_name="samples",
                                                     verbose_name=_("currently responsible person"))
    purpose = models.CharField(_("purpose"), max_length=80, blank=True)
        # Translators: keywords for samples
    tags = models.CharField(_("tags"), max_length=255, blank=True, help_text=_("separated with commas, no whitespace"))
    split_origin = models.ForeignKey("SampleSplit", models.CASCADE, null=True, blank=True, related_name="pieces",
                                     # Translators: ID of mother sample
                                     verbose_name=_("split origin"))
    processes = models.ManyToManyField(Process, blank=True, related_name="samples", verbose_name=_("processes"))
    topic = models.ForeignKey(Topic, models.CASCADE, null=True, blank=True, related_name="samples", verbose_name=_("topic"))
    last_modified = models.DateTimeField(_("last modified"), auto_now=True)

    class Meta:
        verbose_name = _("sample")
        verbose_name_plural = _("samples")
        ordering = ["name"]
        _ = lambda x: x
        permissions = (("view_every_sample", _("Can view all samples from his/her department")),
                       ("adopt_samples", _("Can adopt samples from his/her department")),
                       ("rename_samples", _("Can rename samples from his/her department")))

    def save(self, *args, **kwargs):
        """Saves the instance and clears stalled cache items.

        It also touches all ancestors and children and the associated split
        processes.

        :param with_relations: If ``True`` (default), also touch the related
            samples.  Should be set to ``False`` if called from another
            ``save`` method in order to avoid endless recursion.
        :param from_split: When walking through the decendents, this is set to
            the originating split so that the child sample knows which of its
            splits should be followed, too.  Thus, only the timestamp of
            ``from_split`` is actually used.  It must be ``None`` (default)
            when this method is called from outside this method, or while
            walking through the ancestors.

        :type with_relations: bool
        :type from_split: `SampleSplit` or NoneType
        """
        keys_list_key = "sample-keys:{0}".format(self.pk)
        with cache_key_locked("sample-lock:{0}".format(self.pk)):
            keys = cache.get(keys_list_key)
            if keys:
                cache.delete_many(keys)
            cache.delete(keys_list_key)
        with_relations = kwargs.pop("with_relations", True)
        from_split = kwargs.pop("from_split", None)
        super().save(*args, **kwargs)
        UserDetails.objects.filter(user__in=self.watchers.all()).update(my_samples_list_timestamp=django.utils.timezone.now())
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

    def __str__(self):
        """Here, I realise the peculiar naming scheme of provisional sample
        names.  Provisional samples names always start with ``"*"``, followed
        by a number.  The problem is ordering:  This way, ``"*2"`` and
        ``"*10"`` are ordered ``("*10", "*2")``.  Therefore, I make all numbers
        five-digit numbers.  However, for the sake of readability, I remove the
        leading zeroes in this routine.

        Thus be careful how to access the sample name.  If you want to get a
        human-readable name, use ``str(sample)`` or simply ``{{ sample }}``
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

        :param user: The user for which the tags should be displayed.  If the
            user is not allowed to view the sample fully, no tags are
            returned.

        :type user: django.contrib.auth.models.User

        :return:
          the shortened tags in parentheses

        :rtype: str
        """
        if self.tags and samples.permissions.has_permission_to_fully_view_sample(user, self):
            tags = self.tags if len(self.tags) <= 12 else self.tags[:10] + "…"
            return " ({0})".format(tags)
        else:
            return ""

    def name_with_tags(self, user):
        """Returns the sample's name with possible tags attached.  This is a
        convenience method which simply combines `__str__` and `tags_suffix`.

        :param user: The user for which the tags should be displayed.  If the
            user is not allowed to view the sample fully, no tags are
            returned.

        :type user: django.contrib.auth.models.User

        :return:
          the name of the sample, possibly with shortened tags

        :rtype: str
        """
        return str(self) + self.tags_suffix(user)

    def get_absolute_url(self):
        if self.name.startswith("*"):
            return django.urls.reverse("samples:show_sample_by_id", kwargs={"sample_id": str(self.pk), "path_suffix": ""})
        else:
            return django.urls.reverse("samples:show_sample_by_name", args=(urlquote(self.name, safe=""),))

    def duplicate(self):
        """This is used to create a new `Sample` instance with the same data as
        the current one.  Note that the ``processes`` field is not set because
        many-to-many fields can only be set after the object was saved.

        :return:
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

        :return:
          the split, if it is the most recent process, else ``None``

        :rtype: `SampleSplit` or NoneType
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

        :return:
          the sample details object, or ``None`` if there aren't any (because
          there is no model at all or no particular details for *this* sample)

        :rtype: ``SampleDetails`` or NoneType
        """
        try:
            return self.sample_details
        except (AttributeError, models.ObjectDoesNotExist):
            return None

    def get_data(self, only_processes=False):
        """Extract the data of this sample as a dictionary, ready to be used for
        general data export.  In contrast to `get_data_for_table_export`, I
        export all fields automatically of the instance, including foreign
        keys.  It does not, however, include reverse relations.  Typically,
        this data is used when a non-browser client retrieves a single resource
        and expects JSON output.

        :param only_processes: Whether only processes should be included.  It is
            not part of the official `get_data` API.  I use it only to avoid
            having a special inner function in this method.

        :type only_processes: bool

        :return:
          the content of all fields of this process

        :rtype: `dict`
        """
        data = {field.name: getattr(self, field.name) for field in self._meta.fields}
        if not only_processes:
            sample_details = self.get_sample_details()
            if sample_details:
                sample_details_data = sample_details.get_data()
                data.update(sample_details_data)
        if self.split_origin:
            ancestor_data = self.split_origin.parent.get_data(only_processes=True)
            data.update(ancestor_data)
        data.update(("process #{}".format(process.id), process.actual_instance.get_data())
                    for process in self.processes.all())
        return data

    def get_data_for_table_export(self):
        """Extract the data of this sample as a tree of nodes with lists of key–value
        pairs, ready to be used for the table data export.  Every child of the
        top-level node is a process of the sample.  See the
        `samples.views.table_export` module for all the glory details.

        :return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = DataNode(self, str(self))
        fields_to_data_items(self, data_node)
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

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        search_fields = [search.TextSearchField(cls, "name"),
                         search.TextSearchField(cls, "currently_responsible_person", "username"),
                         search.TextSearchField(cls, "current_location"), search.TextSearchField(cls, "purpose"),
                         search.TextSearchField(cls, "tags"), search.TextNullSearchField(cls, "topic", "name")]
        related_models = {model: "processes" for model in get_all_searchable_physical_processes()}
        related_models[Result] = "processes"
        # FixMe: The following line must be removed but not before possible
        # problems are tackled.
        related_models[Process] = "processes"
        if hasattr(cls, "sample_details"):
            return search.DetailsSearchTreeNode(cls, related_models, search_fields, "sample_details")
        else:
            return search.SearchTreeNode(cls, related_models, search_fields)

    def delete(self, *args, **kwargs):
        """Deletes the sample and all of its processes that contain only this sample –
        which includes splits, pieces, and the cascade after that.  See
        :py:meth:`Process.delete` for further information.
        """
        dry_run = kwargs.get("dry_run", False)
        if dry_run:
            affected_objects = {self}
            samples.permissions.assert_can_edit_sample(kwargs["user"], self)
        for process in self.processes.all():
            if process.samples.count() == 1:
                process = process.actual_instance
                result = process.delete(*args, **kwargs)
                if dry_run:
                    affected_objects |= result
        if dry_run:
            return affected_objects
        else:
            # FixMe: The following two lines are necessary only until
            # https://code.djangoproject.com/ticket/17688 is fixed.
            self.processes.clear()
            self.watchers.clear()
            kwargs.pop("dry_run", None)
            kwargs.pop("user", None)
            self.save()
            return super().delete(*args, **kwargs)


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
    sample = models.ForeignKey(Sample, models.CASCADE, verbose_name=_("sample"), related_name="aliases")

    class Meta:
        unique_together = (("name", "sample"),)
        verbose_name = _("name alias")
        verbose_name_plural = _("name aliases")

    def save(self, *args, **kwargs):
        """Saves the instance and touches the affected sample.
        """
        super().save(*args, **kwargs)
        self.sample.save(with_relations=False)

    def __str__(self):
        return self.name


class SampleSplit(Process):
    """A process where a sample is split into many child samples.  The sample
    split itself is a process of the *parent*, whereas the children point to it
    through `Sample.split_origin`.  This way one can walk through the path of
    relationship in both directions.
    """
        # Translators: parent of a sample
    parent = models.ForeignKey(Sample, models.CASCADE, verbose_name=_("parent"))
    """This field exists just for a fast lookup.  Its existence is actually a
    violation of the non-redundancy rule in database models because one could
    find the parent via the samples attribute every process has, too.
    """

    class Meta(PolymorphicModel.Meta):
        verbose_name = _("sample split")
        verbose_name_plural = _("sample splits")

    def __str__(self):
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
        hash_.update(user_settings_hash.encode())
        hash_.update("\x04{0}\x04{1}\x04{2}".format(local_context.get("original_sample", ""),
                                                    local_context.get("latest_descendant", ""),
                                                    local_context.get("sample", "")).encode())
        return "process:{0}-{1}".format(self.id, hash_.hexdigest())

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if context["sample"] != context["original_sample"]:
            context["parent"] = context["sample"]
        else:
            context["parent"] = None
        if context["sample"].last_process_if_split() == self and \
                samples.permissions.has_permission_to_edit_sample(user, context["sample"]):
            context["resplit_url"] = django.urls.reverse("samples:resplit", kwargs={"old_split_id": self.id})
        else:
            context["resplit_url"] = None
        return super().get_context_for_user(user, context)

    @classmethod
    def get_search_tree_node(cls):
        raise NotImplementedError

    def delete(self, *args, **kwargs):
        dry_run = kwargs.get("dry_run", False)
        if dry_run and self.timestamp < django.utils.timezone.now() - datetime.timedelta(hours=1):
            user = kwargs["user"]
            description = _("You are not allowed to delete the process “{process}” because it is older than "
                            "one hour.").format(process=self)
            raise samples.permissions.PermissionError(user, description)
        affected_objects = {self}
        for sample in self.pieces.all():
            result = sample.delete(*args, **kwargs)
            if dry_run:
                affected_objects |= result
        if dry_run:
            return affected_objects
        else:
            return super().delete(*args, **kwargs)


class Clearance(models.Model):
    """Model for clearances for specific samples to specific users.  Apart
    from unblocking the sample itself (at least, some fields), particular
    processes can be unblocked, too.

    Note that the processes needn't be processes connected with the sample.
    They may also belong to one of its ancestors.
    """
    user = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("user"),
                             related_name="clearances")
    sample = models.ForeignKey(Sample, models.CASCADE, verbose_name=_("sample"), related_name="clearances")
    processes = models.ManyToManyField(Process, verbose_name=_("processes"), related_name="clearances", blank=True)
    last_modified = models.DateTimeField(_("last modified"), auto_now=True)

    class Meta:
        unique_together = ("user", "sample")
        verbose_name = _("clearance")
        verbose_name_plural = _("clearances")

    def __str__(self):
        return _("clearance of {sample} for {user}").format(sample=self.sample, user=self.user)


class SampleClaim(models.Model):
        # Translators: someone who assert a claim to samples
    requester = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("requester"),
                                  related_name="claims")
    reviewer = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("reviewer"),
                                 related_name="claims_as_reviewer")
    samples = models.ManyToManyField(Sample, related_name="claims", verbose_name=_("samples"))
        # Translators: "closed" claim to samples
    closed = models.BooleanField(_("closed"), default=False)

    class Meta:
        verbose_name = _("sample claim")
        verbose_name_plural = _("sample claims")

    def __str__(self):
        return _("sample claim #{number}").format(number=self.pk)

    def get_absolute_url(self):
        return django.urls.reverse("samples:show_claim", args=(self.pk,))


class SampleDeath(Process):
    """This special process marks the end of the sample.  It can have various
    reasons according to :py:data:`sample_death_reasons`.  It is impossible to
    add processes to a sample if it has a `SampleDeath` process, and its
    timestamp must be the last.
    """

    class Reason(models.TextChoices):
        """Contains all possible choices for :py:attr:`SampleDeath.reason`.
        """
        SPLIT = "split", _("completely split")
        LOST = "lost", _("lost and unfindable")
        DESTROYED = "destroyed", _("completely destroyed")

        # Translators: Of a sample
    reason = models.CharField(_("cause of death"), max_length=50, choices=Reason.choices)

    class Meta(PolymorphicModel.Meta):
            # Translators: Of a sample
        verbose_name = _("cease of existence")
            # Translators: Of a sample
        verbose_name_plural = _("ceases of existence")

    @classmethod
    def get_search_tree_node(cls):
        raise NotImplementedError


class Result(Process):
    """Adds a result to the history of a sample.  This may be just a comment,
    or a plot, or an image, or a link.
    """

    class ImageType(models.TextChoices):
        NONE = "none", _("none")
        PDF = "pdf", "PDF"
        PNG = "png", "PNG"
        JPEG = "jpeg", "JPEG"

        # Translators: Of a result
    title = models.CharField(_("title"), max_length=50)
    image_type = models.CharField(_("image file type"), max_length=4, choices=ImageType.choices, default=ImageType.NONE)
        # Translators: Physical quantities are meant
    quantities_and_values = models.JSONField(_("quantities and values"), blank=True, default=empty_double_list)
    """This is a data structure, serialised in JSON.  If you de-serialise it, it is
    a tuple with two items.  The first is a list of unicodes with all
    quantities (the table headings).  The second is a list of lists with
    unicodes (the values; the table cells).  The outer list is the set of rows,
    the inner the cells in each row.  No Markdown is used here, just plain
    strings.  (The HTML entity substitution in quantities has taken place
    already *before* anyting is written here.)
    """

    class Meta(PolymorphicModel.Meta):
            # Translators: experimental result
        verbose_name = _("result")
            # Translators: experimental results
        verbose_name_plural = _("results")

    def save(self, *args, **kwargs):
        """Do everything in :py:meth:`Process.save`, plus touching all samples in all
        connected sample series and the series themselves.
        """
        with_relations = kwargs.get("with_relations", True)
        super().save(*args, **kwargs)
        if with_relations:
            for sample_series in self.sample_series.all():
                sample_series.save(touch_samples=True)

    def __str__(self):
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

    def get_absolute_url(self):
        return django.urls.reverse("samples:show_result", args=(self.pk,))

    def get_image_locations(self):
        """Get the location of the image in the local filesystem as well
        as on the webpage.

        Every image exist twice.  First, it is in the blob store.  If you use
        the ``Filesystem`` blob store with ``settings.MEDIA_ROOT`` as its
        parameter, it is in ``settings.MEDIA_ROOT/results``.  (Typically,
        ``MEDIA_ROOT`` is ``/var/www/juliabase/uploads/`` and should be
        backuped.)  This is the original file, uploaded by the user.  Its
        filename is ``"0"`` plus the respective file extension (jpeg, png, or
        pdf).  The sub-directory is the primary key of the result.  (This
        allows for more than one image per result in upcoming JuliaBase
        versions.)

        Thus, keep in mind that ``"image_file"`` does not refer to an actual
        file path but the path (the primary key if you wish) in the blob
        storage backend.

        Secondly, there are the thumbnails as either a JPEG or a PNG, depending
        on the original file type, and stored in the cache.

        :return:
          a dictionary containing the following keys:

          =========================  =========================================
                 key                           meaning
          =========================  =========================================
          ``"image_file"``           path to the original image file in the
                                     blob storage backend
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
        sluggified_filename = django.utils.text.slugify(self.title) + original_extension
        return {"image_file": os.path.join("results", str(self.pk), "0" + original_extension),
                "image_url": django.urls.reverse("samples:show_result_image", kwargs={"process_id": str(self.pk)}),
                "thumbnail_file": os.path.join("results_thumbnails", str(self.pk), "0" + thumbnail_extension),
                "thumbnail_url": django.urls.reverse("samples:show_result_thumbnail", kwargs={"process_id": str(self.pk)}),
                "sluggified_filename": sluggified_filename}

    def get_context_for_user(self, user, old_context):
        context = old_context.copy()
        if self.quantities_and_values:
            if "quantities" not in context or "value_lists" not in context:
                context["quantities"], context["value_lists"] = self.quantities_and_values
            context["export_url"] = django.urls.reverse("samples:export_result", kwargs={"process_id": self.pk})
        if "thumbnail_url" not in context or "image_url" not in context:
            if self.image_type != "none":
                image_locations = self.get_image_locations()
                context.update({"thumbnail_url": image_locations["thumbnail_url"],
                                "image_url": image_locations["image_url"]})
            else:
                context["thumbnail_url"] = context["image_url"] = None
        if samples.permissions.has_permission_to_edit_result_process(user, self):
            context["edit_url"] = django.urls.reverse("samples:edit_result", kwargs={"process_id": self.pk})
        else:
            context["edit_url"] = None
        return super().get_context_for_user(user, context)

    def get_data(self):
        """Extract the data of this result process as a dictionary.  See
        :py:meth:`Process.get_data` for more information.

        :return:
          the content of all fields of this process

        :rtype: dict
        """
        data = super().get_data()
        data["sample_series"] = list(self.sample_series.values_list("pk", flat=True))
        return data

    def get_data_for_table_export(self):
        """Extract the data of this result process as a tree of nodes (or a single
        node) with lists of key–value pairs, ready to be used for the table
        data export.  See the :py:mod:`samples.views.table_export` module for
        all the glory details.

        However, I should point out the peculiarities of result processes in
        this respect.  Result comments are exported by the parent class, here
        just the table is exported.  If the table contains only one row (which
        should be the case almost always), only one data tree node is returned,
        with this row as the key–value list.

        If the result table has more than one row, for each row, a sub-node is
        generated, which contains the row columns in its key–value list.

        :return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = super().get_data_for_table_export()
        remove_data_item(self, data_node, "quantities_and_values")
        data_node.name = data_node.descriptive_name = self.title
        quantities, value_lists = self.quantities_and_values
        if len(value_lists) > 1:
            for i, value_list in enumerate(value_lists):
                # Translators: In a table
                child_node = DataNode(_("row"), _("row #{number}").format(number=i + 1))
                child_node.items = [DataItem(quantities[j], value) for j, value in enumerate(value_list)]
                data_node.children.append(child_node)
        elif len(value_lists) == 1:
            data_node.items.extend([DataItem(quantity, value) for quantity, value in zip(quantities, value_lists[0])])
        return data_node

    def delete(self, *args, **kwargs):
        # FixMe: This method in its current form is necessary only until
        # https://code.djangoproject.com/ticket/17688 is fixed.
        if not kwargs.get("dry_run", False):
            self.sample_series.clear()
        return super().delete(*args, **kwargs)


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
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE,
                                                     related_name="sample_series",
                                                     verbose_name=_("currently responsible person"))
    description = models.TextField(_("description"))
    samples = models.ManyToManyField(Sample, blank=True, verbose_name=_("samples"), related_name="series")
    results = models.ManyToManyField(Result, blank=True, related_name="sample_series", verbose_name=_("results"))
    topic = models.ForeignKey(Topic, models.CASCADE, related_name="sample_series", verbose_name=_("topic"))
    last_modified = models.DateTimeField(_("last modified"), auto_now=True)

    class Meta:
        verbose_name = _("sample series")
        verbose_name_plural = pgettext_lazy("plural", "sample series")

    def save(self, *args, **kwargs):
        """Saves the instance.

        :param touch_samples: If ``True``, also touch all samples in this
            series.  ``False`` is default because samples don't store
            information about the sample series that may change (note that the
            sample series' name never changes).

        :type touch_samples: bool
        """
        touch_samples = kwargs.pop("touch_samples", False)
        super().save(*args, **kwargs)
        if touch_samples:
            for sample in self.samples.all():
                sample.save(with_relations=False)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return django.urls.reverse("samples:show_sample_series", args=(urlquote(self.name, safe=""),))

    def get_data(self):
        """Extract the data of this sample series as a dictionary, ready to be used for
        general data export.  In addition to all fields, it exports the IDs of
        the contained samples with the key ``"samples"``.  Typically, this data
        is used when a non-browser client retrieves a single resource and
        expects JSON output.

        :return:
          the content of all fields of this sample series

        :rtype: `dict`
        """
        data = {field.name: getattr(self, field.name) for field in self._meta.fields}
        data["samples"] = list(self.samples.values_list("id", flat=True))
        return data

    def get_data_for_table_export(self):
        """Extract the data of this sample series as a tree of nodes with lists of
        key–value pairs, ready to be used for the data export.  Every child of
        the top-level node is a sample of the sample series.  See the
        `samples.views.table_export` module for all the glory details.

        :return:
          a node for building a data tree

        :rtype: `samples.data_tree.DataNode`
        """
        data_node = DataNode(self, str(self))
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

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        search_fields = [search.TextSearchField(cls, "name"),
                         search.TextSearchField(cls, "currently_responsible_person", "username"),
                         search.DateTimeSearchField(cls, "timestamp"), search.TextSearchField(cls, "description"),
                         search.TextSearchField(cls, "topic", "name")]
        related_models = {Sample: "samples", Result: "results"}
        return search.SearchTreeNode(cls, related_models, search_fields)

    def get_hash_value(self):
        """Calculates a SHA-1 hash value out of the sample series name

        :return:
          sha1 hash hex value

        :rtype: str
        """
        return hashlib.sha1(self.name.encode()).hexdigest()


class Initials(models.Model):
    """Model for initials of people or external operators.  They are used to build
    namespaces for sample names and sample series names.  They must match the
    regular expression ``"[A-Z]{2,4}[0-9]*"`` with the additional constraint to
    be no longer than 4 characters.

    You should not delete an entry in this table, and you must never have an
    entry where ``user`` and ``external_operator`` are both set.  It is,
    however, possible to have both ``user`` and ``external_operator`` not set
    in case of initials that have been abandonned.  They should not be re-given
    though.  “Should not” means here “to be done only by the administrator
    after thorough examination”.
    """
    initials = models.CharField(_("initials"), max_length=4, primary_key=True)
    user = models.OneToOneField(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("user"),
                                related_name="initials", null=True, blank=True)
    external_operator = models.OneToOneField(ExternalOperator, models.CASCADE, verbose_name=_("external operator"),
                                             related_name="initials", null=True, blank=True)

    class Meta:
        verbose_name = _("initials")
        verbose_name_plural = pgettext_lazy("plural", "initialses")

    def __str__(self):
        return self.initials


class UserDetails(models.Model):
    """Model for further details about a user, beyond
    django.contrib.auth.models.User.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, models.CASCADE, primary_key=True, verbose_name=_("user"),
                                related_name="samples_user_details")
    auto_addition_topics = models.ManyToManyField(
        Topic, blank=True, related_name="auto_adders", verbose_name=_("auto-addition topics"),
        help_text=_("new samples in these topics are automatically added to “My Samples”"))
    only_important_news = models.BooleanField(_("get only important news"), default=False)
    my_steps = models.JSONField(_("My Steps"), blank=True, default=empty_list)
    """This string is the JSON serialisation of the list with contains 3-tuples of
    the the form ``(nickname, process, step)``, where “process” is the
    process id (``Process.id``) of the process, and “step” is the step number
    (the field name of which must always be called ``number``), for example the
    layer number within a deposition (`models.depositions.Layer.number`).  In
    this structure, a user can collect favourite sub-processes that they want
    to re-use in new processes.
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
    my_samples_list_timestamp = models.DateTimeField(_("My Samples list last modified"), auto_now_add=True)
    """This timestamp denotes when the My Samples list was changed most recently.
    In contrast to ``my_samples_timestamp``, this also includes things like
    sample series memberships, topic memberships – everything that influences
    the appearance of the samples list in the main menu.  It is used for
    expiring the caching of the results of
    :py:func:`samples.utils.views.build_structured_sample_list`.
    """
    identifying_data_hash = models.CharField(_("identifying data hash"), max_length=40)
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
                                              verbose_name=_("process classes folded by default"), blank=True)
    folded_processes = models.JSONField(_("folded processes"), blank=True, default=empty_dict)
    """Dictionary mapping the ID of a sample to a list of all processes that are
    folded by the user.  Note that due to JSON's constraints, the sample ID is
    a string.
    """
    visible_task_lists = models.ManyToManyField(ContentType, related_name="task_lists_from_user",
                                                verbose_name=_("visible task lists"), blank=True)
    folded_topics = models.JSONField(_("folded topics"), blank=True, default=empty_list)
    # Translators: This is plural.
    folded_series = models.JSONField(_("folded sample series"), blank=True, default=empty_list)
    show_users_from_departments = models.ManyToManyField(Department, related_name="shown_users",
                                                        verbose_name=_("show users from department"), blank=True)


    class Meta:
        verbose_name = _("user details")
        verbose_name_plural = _("user details")
        _ = lambda x: x
        permissions = (("edit_permissions_for_all_physical_processes",
                        _("Can edit permissions for all physical processes")),)

    def __str__(self):
        return str(self.user)

    def touch_display_settings(self):
        """Set the last modifications of sample settings to the current time.  This
        method must be called every time when something was changed which
        influences the display of a sample datasheet (and is not covered by
        other timestamps (``my_samples_timestamp``,
        :py:attr:`jb_common.models.UserDetails.layout_last_modified`),
        e.g. topic memberships.  It is used for efficient caching.
        """
        self.display_settings_timestamp = django.utils.timezone.now()
        self.save()


class StatusMessage(models.Model):
    """This class is for the current status of the processes.  The class
    discusses whether the process is available, or is currently out of service.
    It provides a many to many relationship between the status messages and the
    processes.
    """

    class StatusLevel(models.TextChoices):
        UNDEFINED = "undefined", _("undefined")
        RED = "red", _("red")
        YELLOW = "yellow", _("yellow")
        GREEN = "green", _("green")

    process_classes = models.ManyToManyField(ContentType, related_name="status_messages", verbose_name=_("processes"))
    timestamp = models.DateTimeField(_("timestamp"))
    begin = models.DateTimeField(_("begin"), null=True, blank=True, help_text=_("YYYY-MM-DD HH:MM:SS"))
    end = models.DateTimeField(_("end"), null=True, blank=True, help_text=_("YYYY-MM-DD HH:MM:SS"))
    begin_inaccuracy = models.PositiveSmallIntegerField(_("begin inaccuracy"), choices=Process.TimestampInaccuracy.choices,
                                                        default=Process.TimestampInaccuracy.TOTAL)
    end_inaccuracy = models.PositiveSmallIntegerField(_("end inaccuracy"), choices=Process.TimestampInaccuracy.choices,
                                                        default=Process.TimestampInaccuracy.TOTAL)
    operator = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, related_name="status_messages",
                                 verbose_name=_("reporter"))
    message = models.TextField(_("message"), blank=True)
    status_level = models.CharField(_("level"), choices=StatusLevel.choices, default=StatusLevel.UNDEFINED, max_length=10)
    withdrawn = models.BooleanField(_("withdrawn"), default=False)

    class Meta:
        verbose_name = _("status message")
        verbose_name_plural = _("status messages")

    def __str__(self):
        return _("status message #{number}").format(number=self.pk)


class Task(models.Model):
    """
    """

    class Status(models.TextChoices):
        FINISHED = "0 finished", _("finished")
        NEW = "1 new", _("new")
        ACCEPTED = "2 accepted", _("accepted")
        IN_PROGRESS = "3 in progress", _("in progress")

    class Priority(models.TextChoices):
        CRITICAL = "0 critical", _("critical")
        HIGH = "1 high", _("high")
        NORMAL = "2 normal", _("normal")
        LOW = "3 low", _("low")

    status = models.CharField(_("status"), max_length=15, choices=Status.choices, default=Status.NEW)
    customer = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, related_name="tasks",
                                 verbose_name=_("customer"))
    creating_timestamp = models.DateTimeField(_("created at"), help_text=_("YYYY-MM-DD HH:MM:SS"), auto_now_add=True)
    last_modified = models.DateTimeField(_("last modified"), help_text=_("YYYY-MM-DD HH:MM:SS"), auto_now=True)
    operator = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, related_name="operated_tasks",
                                 verbose_name=_("operator"), null=True, blank=True)
    process_class = models.ForeignKey(ContentType, models.CASCADE, related_name="tasks", verbose_name=_("process class"))
    finished_process = models.ForeignKey(Process, models.CASCADE, related_name="task", null=True, blank=True,
                                         verbose_name=_("finished process"))
    samples = models.ManyToManyField(Sample, related_name="task", verbose_name=_("samples"))
    comments = models.TextField(_("comments"), blank=True)
    priority = models.CharField(_("priority"), max_length=15, choices=Priority.choices, default=Priority.NORMAL)

    class Meta:
        verbose_name = _("task")
        verbose_name_plural = _("tasks")

    def __str__(self):
        return _("task of {process_class} from {datetime}". format(
                process_class=self.process_class.name, datetime=self.creating_timestamp))

    def get_absolute_url(self):
        return "{0}#task_{1}".format(django.urls.reverse("samples:show_task_lists"), self.id)

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        search_fields = [search.TextSearchField(cls, "status"),
                         search.TextSearchField(cls, "customer", "username"),
                         search.TextNullSearchField(cls, "operator", "username"),
                         search.TextSearchField(cls, "comments"), search.TextSearchField(cls, "priority"),
                         search.DateTimeSearchField(cls, "creating_timestamp"),
                         search.DateTimeSearchField(cls, "last_modified")]
        related_models = {model: "finished_process" for model in get_all_searchable_physical_processes()}
        related_models[Sample] = "samples"
        return search.SearchTreeNode(cls, related_models, search_fields)


class ProcessWithSamplePositions(models.Model):
    """An abstract mixin class for saving the positions of the samples in an
    apparatus.

    The ``sample_positions`` field may be used by derived models for storing
    where the samples were mounted during e.g. the deposition.  Sometimes it is
    interesting to know that because the deposition device may not work
    homogeneously.  It is placed here in order to be able to extend the
    split-after-deposition view so that it offers input fields for it if it is
    applicable.  (For example, this can be given in the query string.)
    """

    sample_positions = models.JSONField(_("sample positions"), default=empty_dict)
    """In JSON format, mapping sample IDs to positions.  Positions can be numbers
    or strings.  Note that due to JSON constraints, the sample IDs are
    strings.
    """

    class Meta:
        abstract = True

    def get_sample_position_context(self, user, old_context):
        context = old_context.copy()
        if "sample_position" not in context:
            sample = context.get("sample")
            sample_positions_dict = self.sample_positions
            if sample_positions_dict and sample:
                context["sample_position"] = (sample if sample.topic and not sample.topic.confidential or
                                              samples.permissions.has_permission_to_fully_view_sample(user, sample) or
                                              samples.permissions.has_permission_to_add_edit_physical_process(
                                                  user, self, self.content_type.model_class())
                                              else _("confidential sample"),
                                              sample_positions_dict[str(sample.id)])
        if "sample_positions" not in context:
            sample_positions_dict = self.sample_positions
            if sample_positions_dict:
                context["sample_positions"] = \
                    collections.OrderedDict((sample if sample.topic and not sample.topic.confidential or
                                             samples.permissions.has_permission_to_fully_view_sample(user, sample) or
                                             samples.permissions.has_permission_to_add_edit_physical_process(
                                                 user, self, self.content_type.model_class())
                                             else _("confidential sample"),
                                             sample_positions_dict.get(str(sample.id)))
                                            for sample in self.samples.order_by("name").iterator())
        return context


    def get_cache_key(self, user_settings_hash, local_context):
        """Generates an own cache key for every instance of this process.  If a process
        inherits from both `Process` class and ``ProcessWithSamplePositions``
        class, you have to make sure that the process uses this method for the
        cache key and not the method from the `Process` class.

        For the parameter description see :py:meth:`Process.get_cache_key`.
        """
        hash_ = hashlib.sha1()
        hash_.update(user_settings_hash.encode())
        hash_.update("\x04{0}".format(local_context.get("sample", "")).encode())
        return "process:{0}-{1}".format(self.id, hash_.hexdigest())


_ = ugettext
