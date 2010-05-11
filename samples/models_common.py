#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""The most basic models like ``Sample``, ``SampleSeries``, ``UserDetails``
etc.  It is important to see that this module is imported by almost all other
models modules.  Therefore, you *must* *not* import any Chantal models module
here, in particular not ``models.py``.  Otherwise, you'd end up with
irresolvable cyclic imports.
"""

from __future__ import absolute_import, division

import hashlib, os.path, shutil, subprocess, datetime
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.utils import translation
from django.template import defaultfilters
from django.utils.http import urlquote, urlquote_plus
import django.core.urlresolvers
from django.conf import settings
from django.db import models
from chantal_common.utils import get_really_full_name
from chantal_common.models import Topic
from samples import permissions
from samples.views import shared_utils
from samples.csv_common import CSVNode, CSVItem


class ExternalOperator(models.Model):
    u"""Some samples and processes are not made in our institute but in external
    institutions.  This is realised by setting the `Process.external_operator`
    field, which in turn contains `ExternalOperator`.
    """
    name = models.CharField(_(u"name"), max_length=30)
    institution = models.CharField(_(u"institution"), max_length=255)
    email = models.EmailField(_(u"email"))
    alternative_email = models.EmailField(_(u"alternative email"), null=True, blank=True)
    phone = models.CharField(_(u"phone"), max_length=30, blank=True)
    contact_person = models.ForeignKey(django.contrib.auth.models.User, related_name="external_contacts",
                                       verbose_name=_(u"contact person in the institute"))
        # Translation hint: Topic which is not open to senior members
    restricted = models.BooleanField(_(u"restricted"), default=False)

    class Meta:
        verbose_name = _(u"external operator")
        verbose_name_plural = _(u"external operators")
        _ = lambda x: x
        permissions = (("add_external_operator", _("Can add an external operator")),)

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.external_operator.show", [urlquote(self.pk, safe="")])


timestamp_inaccuracy_choices = (
        # Translation hint: It's about timestamps
    (0, _(u"totally accurate")),
    (1, _(u"accurate to the minute")),
    (2, _(u"accurate to the hour")),
    (3, _(u"accurate to the day")),
    (4, _(u"accurate to the month")),
    (5, _(u"accurate to the year")),
    (6, _(u"not even accurate to the year")),
    )

class Process(models.Model):
    u"""This is the parent class of all processes and measurements.  Actually,
    it is an *abstract* base class, i.e. there are no processes in the database
    that are *just* processes.  However, it is not marked as ``abstract=True``
    in the ``Meta`` subclass because I must be able to link to it with
    ``ForeignKey``.

    If you retrieve a `Process`, you may call (injected) method
    `find_actual_instance` to get the actual object, e.g. a
    `SixChamberDeposition`::

        process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id))
        process = process.find_actual_instance()
    """
    timestamp = models.DateTimeField(_(u"timestamp"))
    timestamp_inaccuracy = models.IntegerField(_("timestamp inaccuracy"), choices=timestamp_inaccuracy_choices, default=0)
    operator = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"operator"), related_name="processes")
    external_operator = models.ForeignKey(ExternalOperator, verbose_name=_("external operator"), null=True, blank=True,
                                          related_name="processes")
    comments = models.TextField(_(u"comments"), blank=True)

    class Meta:
        ordering = ["timestamp"]
        verbose_name = _(u"process")
        verbose_name_plural = _(u"processes")

    def __unicode__(self):
        return unicode(self.find_actual_instance())

    @models.permalink
    def get_absolute_url(self):
        u"""Returns the relative URL (ie, without the domain name) of the
        database object.  Django calls this method ``get_absolute_url`` to make
        clear that *only* the domain part is missing.  Apart from that, it
        includes the full URL path to where the object can be seen.

        Note that Django itself uses this method in its built-in syndication
        framework.  However currently, Chantal uses it only explicitly in
        re-directions and links in templates.

        :Return:
          Relative URL, however, starting with a “/”, to the page where one can
          view the object.

        :rtype: str
        """
        return ("samples.views.main.main_menu", (), {})
#        return ("samples.views.main.show_process", [str(self.pk)])

    def calculate_plot_locations(self, number):
        u"""Get the location of a plot in the local filesystem as well as on
        the webpage.

        Every plot resides in a directory with a peculiar name in order to be
        un-guessable.  This is not security by obscurity because we really use
        cryptographic hashes.  While it still is not the highest level of
        security, it is a sensible compromise between security and performance.
        Besides, this method excludes name collisions.

        :Parameters:
          - `number`: the number of the image.  This is mostly ``0`` because
            most measurement models have only one graphics.

        :type number: int

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
        hash_ = hashlib.sha1()
        hash_.update(settings.SECRET_KEY)
        hash_.update(translation.get_language())
        hash_.update(repr(self.pk))
        hash_.update(repr(number))
        hashname = str(self.pk) + "-" + hash_.hexdigest()
        if number == 0:
            # We give this a nicer URL because this case is so common
            plot_url = django.core.urlresolvers.reverse("default_plot", kwargs={"process_id": str(self.pk)})
        else:
            plot_url = django.core.urlresolvers.reverse("samples.views.plots.show_plot",
                                                        kwargs={"process_id": str(self.pk), "number": str(number)})
        return {"plot_file": os.path.join(settings.CACHE_ROOT, "plots", hashname + ".pdf"),
                "plot_url": plot_url,
                "thumbnail_file": os.path.join(settings.MEDIA_ROOT, "plots", hashname + ".png"),
                "thumbnail_url": os.path.join(settings.MEDIA_URL, "plots", hashname + ".png")}

    def generate_plot_files(self, number=0):
        u"""The central plot-generating method which shouldn't be overridden by
        a derived class.  This method tests whether it is necessary to generate
        new plots from the original datafile (by checking existence and file
        timestamps), and does it if necessary.

        Note that plots can only be generated for *physical* processes,
        i.e. depositions, measurements, etc.

        The thumbnail image is a PNG, the figure image is a PDF.

        :Parameters:
          - `number`: the number of the plot to be generated.  It defaults to
            ``0`` because most models will have at most one plot anyway.

        :type number: int

        :Return:
          the full relative URL to the thumbnail image (i.e., without domain
          but with file extension), and the full relative URL to the figure
          image (which usually is linked with the thumbnail).  If the
          generation fails, it returns ``None, None``.

        :rtype: str, str; or ``NoneType``, ``NoneType``
        """
        datafile_name = self.get_datafile_name(number)
        if not datafile_name:
            return None, None
        datafile_names = datafile_name if isinstance(datafile_name, list) else [datafile_name]
        if not all(os.path.exists(filename) for filename in datafile_names):
            return None, None
        plot_locations = self.calculate_plot_locations(number)
        thumbnail_necessary = not os.path.exists(plot_locations["thumbnail_file"]) or \
            any(os.stat(plot_locations["thumbnail_file"]).st_mtime < os.stat(filename).st_mtime
                for filename in datafile_names)
        figure_necessary = not os.path.exists(plot_locations["plot_file"]) or \
            any(os.stat(plot_locations["plot_file"]).st_mtime < os.stat(filename).st_mtime for filename in datafile_names)
        if thumbnail_necessary or figure_necessary:
            try:
                if thumbnail_necessary:
                    figure = Figure(frameon=False, figsize=(4, 3))
                    canvas = FigureCanvasAgg(figure)
                    axes = figure.add_subplot(111)
                    axes.set_position((0.15, 0.15, 0.8, 0.8))
                    axes.grid(True)
                    self.draw_plot(axes, number, datafile_name, for_thumbnail=True)
                    shared_utils.mkdirs(plot_locations["thumbnail_file"])
                    canvas.print_figure(plot_locations["thumbnail_file"], dpi=settings.THUMBNAIL_WIDTH / 4)
                if figure_necessary:
                    figure = Figure()
                    canvas = FigureCanvasAgg(figure)
                    axes = figure.add_subplot(111)
                    axes.grid(True)
                    self.draw_plot(axes, number, datafile_name, for_thumbnail=False)
                    axes.set_title(unicode(self))
                    shared_utils.mkdirs(plot_locations["plot_file"])
                    canvas.print_figure(plot_locations["plot_file"], format="pdf")
            except (IOError, shared_utils.PlotError):
                return None, None
        return plot_locations["thumbnail_url"], plot_locations["plot_url"]

    def draw_plot(self, axes, number, filename, for_thumbnail):
        u"""Generate a plot using Matplotlib commands.  You may do whatever you
        want here – but eventually, there must be a savable Matplotlib plot in
        the `axes`.  The ``filename`` parameter ist not really necessary but it
        makes things a little bit faster and easier.

        This method must be overridden in derived classes that wish to offer
        plots.

        :Parameters:
          - `axes`: The Matplotlib axes to which the plot must be drawn.  You
            call methods of this parameter to draw the plot,
            e.g. ``axes.plot(x_values, y_values)``.
          - `number`: The number of the plot.  For most models offering plots,
            this can only be zero and as such is not used it all in this
            method.
          - `filename`: the filename of the original data file; it may also be
            a list of filenames if more than one file lead to the plot
          - `for_thumbnail`: whether we do a plot for the thumbnail bitmap; for
            simple plots, this can be ignored

        :type axes: ``matplotlib.axes.Axes``
        :type number: int
        :type filename: str or list of str
        :type for_thumbnail: bool

        :Exceptions:
          - `PlotError`: if anything went wrong during the generation of the
            plot
        """
        raise NotImplementedError

    def get_datafile_name(self, number):
        u"""Get the name of the file with the original data for the plot with
        the given ``number``.  It may also be a list of filenames if more than
        one file lead to the plot.

        This method must be overridden in derived classes that wish to offer
        plots.

        :Parameters:
          - `number`: the number of the plot.  For most models offering plots,
            this can only be zero and as such is not used it all in this
            method.

        :type number: int

        :Return:
          The absolute path of the file(s) with the original data for this plot
          in the local filesystem.  It's ``None`` if there is no plottable
          datafile for this process.

        :rtype: list of str, str, or ``NoneType``
        """
        raise NotImplementedError

    def get_plotfile_basename(self, number):
        u"""Get the name of the plot files with the given ``number``.  For
        example, for the PDS measurement for the sample 01B410, this may be
        ``"pds_01B410"``.  It should be human-friendly and reasonable
        descriptive since this is the name that is used if the user wishes to
        download a plot to their local filesystem.  It need not be unique in
        any way (although mostly it is).

        This method must be overridden in derived classes that wish to offer
        plots.

        :Parameters:
          - `number`: the number of the plot.  For most models offering plots,
            this can only be zero and as such is not used it all in this
            method.

        :type number: int

        :Return:
          the base name for the plot files, without directories or extension

        :rtype: str
        """
        raise NotImplementedError

    def get_data(self):
        u"""Extract the data of this process as a tree of nodes (or a single
        node) with lists of key–value pairs, ready to be used for the CSV table
        export.  See the `samples.views.csv_export` module for all the glory
        details.

        :Return:
          a node for building a CSV tree

        :rtype: `samples.csv_common.CSVNode`
        """
        csv_node = CSVNode(self)
        csv_node.items = [CSVItem(_(u"timestamp"), self.timestamp, "process"),
                          CSVItem(_(u"operator"), get_really_full_name(self.operator), "process"),
                          CSVItem(_(u"comments"), self.comments, "process")]
        return csv_node

    @classmethod
    def get_lab_notebook_context(cls, year, month):
        processes = cls.objects.filter(timestamp__year=year, timestamp__month=month).select_related()
        return {"processes": processes}


class Sample(models.Model):
    u"""The model for samples.
    """
    name = models.CharField(_(u"name"), max_length=30, unique=True, db_index=True)
        # Translation hint: location of a sample
    current_location = models.CharField(_(u"current location"), max_length=50)
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, related_name="samples",
                                                     verbose_name=_(u"currently responsible person"))
    purpose = models.CharField(_(u"purpose"), max_length=80, blank=True)
        # Translation hint: keywords for samples
    tags = models.CharField(_(u"tags"), max_length=255, blank=True, help_text=_(u"separated with commas, no whitespace"))
    split_origin = models.ForeignKey("SampleSplit", null=True, blank=True, related_name="pieces",
                                     # Translation hint: ID of mother sample
                                     verbose_name=_(u"split origin"))
    processes = models.ManyToManyField(Process, blank=True, related_name="samples", verbose_name=_(u"processes"))
    topic = models.ForeignKey(Topic, null=True, blank=True, related_name="samples", verbose_name=_(u"topic"))

    class Meta:
        verbose_name = _(u"sample")
        verbose_name_plural = _(u"samples")
        ordering = ["name"]
        _ = lambda x: x
        permissions = (("view_all_samples", _("Can view all samples (senior user)")),)

    def __unicode__(self):
        u"""Here, I realise the peculiar naming scheme of provisional sample
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
            return u"*" + name.lstrip("*0")
        else:
            return name

    @models.permalink
    def get_absolute_url(self):
        if self.name.startswith("*"):
            return ("show_sample_by_id", (), {"sample_id": str(self.pk), "path_suffix": ""})
        else:
            return ("show_sample_by_name", [urlquote(self.name, safe="")])

    def duplicate(self):
        u"""This is used to create a new `Sample` instance with the same data as
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
        return self.processes.filter(sampledeath__timestamp__isnull=False).count() > 0

    def last_process_if_split(self):
        u"""Test whether the most recent process applied to the sample – except
        for result processes – was a split.

        :Return:
          the split, if it is the most recent process, else ``None``

        :rtype: `models.SampleSplit` or ``NoneType``
        """
        for process in self.processes.order_by("-timestamp"):
            process = process.find_actual_instance()
            if isinstance(process, SampleSplit):
                return process
            if not isinstance(process, Result):
                break
        return None

    def get_data(self):
        u"""Extract the data of this sample as a tree of nodes with lists of
        key–value pairs, ready to be used for the CSV table export.  Every
        child of the top-level node is a process of the sample.  See the
        `samples.views.csv_export` module for all the glory details.

        :Return:
          a node for building a CSV tree

        :rtype: `samples.csv_common.CSVNode`
        """
        _ = ugettext
        csv_node = CSVNode(self, unicode(self))
        csv_node.children.extend(process.find_actual_instance().get_data() for process in self.processes.all())
        # I don't think that any sample properties are interesting for table
        # export; people only want to see the *process* data.  Thus, I don't
        # set ``cvs_note.items``.
        return csv_node


class SampleAlias(models.Model):
    u"""Model for former names of samples.  If a sample gets renamed (for
    example, because it was deposited), its old name is moved here.  Note that
    aliases needn't be unique.  Two old names may be the same.

    Note that they may be equal to a ``Sample.name``.  However, when accessing
    a sample by its name in the URL, this shadows any aliases of the same
    name.  Only if you look for the name by the search function, you also find
    aliases of the same name.
    """
    name = models.CharField(_(u"name"), max_length=30)
    sample = models.ForeignKey(Sample, verbose_name=_(u"sample"), related_name="aliases")

    class Meta:
        unique_together = (("name", "sample"),)
        verbose_name = _(u"name alias")
        verbose_name_plural = _(u"name aliases")

    def __unicode__(self):
        return self.name


class SampleSplit(Process):
    u"""A process where a sample is split into many child samples.  The sample
    split itself is a process of the *parent*, whereas the children point to it
    through `Sample.split_origin`.  This way one can walk through the path of
    relationship in both directions.
    """
        # Translation hint: parent of a sample
    parent = models.ForeignKey(Sample, verbose_name=_(u"parent"))
    u"""This field exists just for a fast lookup.  Its existence is actually a
    violation of the non-redundancy rule in database models because one could
    find the parent via the samples attribute every process has, too."""

    class Meta:
        verbose_name = _(u"sample split")
        verbose_name_plural = _(u"sample splits")

    def __unicode__(self):
        _ = ugettext
        return _(u"split of %s") % self.parent.name

    def get_additional_template_context(self, process_context):
        u"""See
        `models_depositions.SixChamberDeposition.get_additional_template_context`
        for general information.

        :Parameters:
          - `process_context`: context information for this process.  This
            routine needs ``current_sample`` and ``original_sample`` from the
            process context.

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          sample split template: ``"parent"``, ``"original_sample"``,
          ``"current_sample"``, and ``"latest_descendant"``.

        :rtype: dict mapping string to arbitrary objects
        """
        assert process_context.current_sample
        if process_context.current_sample != process_context.original_sample:
            parent = process_context.current_sample
        else:
            parent = None
        result = {"parent": parent, "original_sample": process_context.original_sample,
                  "current_sample": process_context.current_sample, "latest_descendant": process_context.latest_descendant}
        result["resplit_url"] = None
        if process_context.current_sample.last_process_if_split() == self and \
                permissions.has_permission_to_edit_sample(process_context.user, process_context.current_sample):
            result["resplit_url"] = django.core.urlresolvers.reverse(
                "samples.views.split_and_rename.split_and_rename", kwargs={"old_split_id": self.pk})
        return result


substrate_materials = (
        # Translation hint: sample substrate type
    ("custom", _(u"custom")),
    ("asahi-u", _(u"ASAHI-U")),
    ("corning", _(u"Corning glass")),
    ("si-wafer", _(u"silicon wafer")),
    )
u"""Contains all possible choices for `Substrate.material`.
"""

class Substrate(Process):
    u"""Model for substrates.  It is very senseful, though not mandatory, that
    the very first process of a sample is a substrate process.  It is some sort
    of birth certificale of the sample.  If it doesn't exist, we don't know
    when the sample was actually created.  If the substrate process has an
    `Process.external_operator`, it is an external sample.
    """
    material = models.CharField(_(u"substrate material"), max_length=30, choices=substrate_materials)
    # The following field should be unique, but this doesn't work, see
    # <http://stackoverflow.com/questions/454436/unique-fields-that-allow-nulls-in-django>.
    # Karen Tracey's comment would probably help but this would exclude Oracle
    # as a possible database backend.
    cleaning_number = models.CharField(_(u"cleaning number"), max_length=10, null=True, blank=True)

    class Meta:
        verbose_name = _(u"substrate")
        verbose_name_plural = _(u"substrates")
        _ = lambda x: x
        permissions = (("clean_substrate", _("Can clean substrates")),
                       ("add_edit_substrate", _("Can create and edit substrates")))

    def __unicode__(self):
        result = self.material
        if self.cleaning_number:
            result += u" ({0})".format(self.cleaning_number)
        return result

    def get_data(self):
        # See `Process.get_data` for the documentation.
        _ = ugettext
        csv_node = super(Substrate, self).get_data()
        csv_node.items.append(CSVItem(_(u"material"), self.get_material_display()))
        # FixMe: Should this be appended even if it doesn't exist?
        csv_node.items.append(CSVItem(_(u"cleaning number"), self.cleaning_number))
        return csv_node

    @classmethod
    def get_add_link(cls):
        u"""Return the URL to the “add” view for this process.

        This method marks the current class as a so-called physical process.
        This implies that it also must have an “add-edit” permission.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_substrate")


sample_death_reasons = (
    ("split", _(u"completely split")),
    ("lost", _(u"lost and unfindable")),
    ("destroyed", _(u"completely destroyed")),
    )
u"""Contains all possible choices for `SampleDeath.reason`.
"""

class SampleDeath(Process):
    u"""This special process marks the end of the sample.  It can have various
    reasons accoring to `sample_death_reasons`.  It is impossible to add
    processes to a sample if it has a `SampleDeath` process, and its timestamp
    must be the last.
    """
        # Translation hint: Of a sample
    reason = models.CharField(_(u"cause of death"), max_length=50, choices=sample_death_reasons)

    class Meta:
            # Translation hint: Of a sample
        verbose_name = _(u"cease of existence")
            # Translation hint: Of a sample
        verbose_name_plural = _(u"ceases of existence")

    def __unicode__(self):
        _ = ugettext
        try:
            # Translation hint: Of a sample
            return _(u"cease of existence of %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            # Translation hint: Of a sample
            return _(u"cease of existence #%d") % self.pk


image_type_choices=(("none", _(u"none")),
                    ("pdf", "PDF"),
                    ("png", "PNG"),
                    ("jpeg", "JPEG"),
                    )

class Result(Process):
    u"""Adds a result to the history of a sample.  This may be just a comment,
    or a plot, or an image, or a link.
    """
        # Translation hint: Of a result
    title = models.CharField(_(u"title"), max_length=50)
    image_type = models.CharField(_("image file type"), max_length=4, choices=image_type_choices, default="none")
        # Translation hint: Physical quantities are meant
    quantities_and_values = models.TextField(_("quantities and values"), blank=True, help_text=_(u"in Python pickle format"))
    u"""This is a data structure, serialised in Python pickle format (protocol
    2 plus a base64 encoding, because this is UTF-8 safe; you never know what
    the database does with it).  If you un-pickle it, it is a tuple with two
    items.  The first is a list of unicodes with all quantities (the table
    headings).  The second is a list of lists with unicodes (the values; the
    table cells).  The outer list is the set of rows, the inner the columns.
    No Markdown is used here, just plain strings.  (The HTML entity
    substitution in quantities has taken place already *before* anyting is
    written here.)
    """

    class Meta:
            # Translation hint: experimental result
        verbose_name = _(u"result")
            # Translation hint: experimental results
        verbose_name_plural = _(u"results")

    def __unicode__(self):
        _ = ugettext
        try:
            # Translation hint: experimental result
            return _(u"result for %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            try:
                # Translation hint: experimental result
                return _(u"result for %s") % self.sample_series.get()
            except SampleSeries.DoesNotExist, SampleSeries.MultipleObjectsReturned:
                # Translation hint: experimental result
                return _(u"result #%d") % self.pk

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.result.show", (self.pk,))

    def get_image_locations(self):
        u"""Get the location of the image in the local filesystem as well
        as on the webpage.

        Every image exist twice on the local filesystem.  First, it is in
        ``settings.UPLOADS_ROOT/results``.  (Typically, ``UPLOADS_ROOT`` is
        ``/var/www/chantal/uploads/`` and should be backuped.)  This is the
        original file, uploaded by the user.  Its filename is ``"0"`` plus the
        respective file extension (jpeg, png, or pdf).  The sub-directory is
        the primary key of the result.  (This allows for more than one image
        per result in upcoming Chantal versions.)

        Secondly, there are the thumbnails as either a JPEG or a PNG, depending
        on the original file type, and stored in ``settings.MEDIA_ROOT``.  The
        thumbnails are served by Lighty without permissions-checking.
        Therefore, their path is protected by a salted hash.

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
        hash_ = hashlib.sha1()
        hash_.update(settings.SECRET_KEY)
        hash_.update(repr(self.pk))
        hashname = str(self.pk) + "-" + hash_.hexdigest()
        sluggified_filename = defaultfilters.slugify(self.title)
        original_extension = "." + self.image_type
        thumbnail_extension = ".jpeg" if self.image_type == "jpeg" else ".png"
        relative_thumbnail_path = os.path.join("results", hashname + thumbnail_extension)
        return {"image_file": os.path.join(settings.UPLOADS_ROOT, "results", str(self.pk), "0" + original_extension),
                "image_url": django.core.urlresolvers.reverse(
                "samples.views.result.show_image", kwargs={"process_id": str(self.pk),
                                                           "image_filename": sluggified_filename + original_extension}),
                "thumbnail_file": os.path.join(settings.MEDIA_ROOT, relative_thumbnail_path),
                "thumbnail_url": os.path.join(settings.MEDIA_URL, relative_thumbnail_path)}

    def get_image(self):
        u"""Assures that the image thumbnail of this result process is
        generated and returns the URLs of thumbnail and original.

        :Return:
          The full relative URL (i.e. without the domain, but with the leading
          ``/``) to the thumbnail, and the full relative URL to the “real”
          image.  Both strings are ``None`` if there is no image connected with
          this result, or the original image couldn't be found.  They are
          returned in a dictionary with the keys ``"thumbnail_url"`` and
          ``"image_url"``, respectively.

        :rtype: dict mapping str to (str or ``NoneType``)
        """
        if self.image_type == "none":
            return {"thumbnail_url": None, "image_url": None}
        image_locations = self.get_image_locations()
        if not os.path.exists(image_locations["thumbnail_file"]):
            shared_utils.mkdirs(image_locations["thumbnail_file"])
            if not os.path.exists(image_locations["thumbnail_file"]):
                subprocess.call(["convert", image_locations["image_file"] + ("[0]" if self.image_type == "pdf" else ""),
                                 "-resize", "%(width)dx%(width)d" % {"width": settings.THUMBNAIL_WIDTH},
                                 image_locations["thumbnail_file"]])
        return {"thumbnail_url": image_locations["thumbnail_url"], "image_url": image_locations["image_url"]}

    def get_additional_template_context(self, process_context):
        u"""See
        `models_depositions.SixChamberDeposition.get_additional_template_context`
        for general information.

        :Parameters:
          - `process_context`: context information for this process.  This
            routine needs only ``user`` from the process context.

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          result process template, e.g. ``"edit_url"``.

        :rtype: dict mapping str to str
        """
        result = self.result.get_image()
        if permissions.has_permission_to_edit_result_process(process_context.user, self):
            result["edit_url"] = \
                django.core.urlresolvers.reverse("edit_result", kwargs={"process_id": self.pk})
        if self.quantities_and_values:
            result["quantities"], result["value_lists"] = shared_utils.ascii_unpickle(self.quantities_and_values)
            result["export_url"] = \
                django.core.urlresolvers.reverse("samples.views.result.export", kwargs={"process_id": self.pk})
        return result

    def get_data(self):
        u"""Extract the data of this result process as a tree of nodes (or a
        single node) with lists of key–value pairs, ready to be used for the
        CSV table export.  See the `samples.views.csv_export` module for all
        the glory details.

        However, I should point out the peculiarities of result processes in
        this respect.  Result comments are exported by the parent class, here
        just the table is exported.  If the table contains only one row (which
        should be the case almost always), only one CSV tree node is returned,
        with this row as the key–value list.

        If the result table has more than one row, for each row, a sub-node is
        generated, which contains the row columns in its key–value list.

        :Return:
          a node for building a CSV tree

        :rtype: `samples.csv_common.CSVNode`
        """
        _ = ugettext
        csv_node = super(Result, self).get_data()
        csv_node.name = csv_node.descriptive_name = self.title
        quantities, value_lists = shared_utils.ascii_unpickle(self.quantities_and_values)
        if len(value_lists) > 1:
            for i, value_list in enumerate(value_lists):
                # Translation hint: In a table
                child_node = CSVNode(_(u"row"), _(u"row #%d") % (i + 1))
                child_node.items = [CSVItem(quantities[j], value) for j, value in enumerate(value_list)]
                csv_node.children.append(child_node)
        elif len(value_lists) == 1:
            csv_node.items.extend([CSVItem(quantity, value) for quantity, value in zip(quantities, value_lists[0])])
        return csv_node


class SampleSeries(models.Model):
    u"""A sample series groups together zero or more `Sample`.  It must belong
    to a topic, and it may contain processes, however, only *result processes*.
    The ``name`` and the ``timestamp`` of a sample series can never change
    after it has been created.
    """
    name = models.CharField(_(u"name"), max_length=50, primary_key=True,
                            # Translation hint: The “Y” stands for “year”
                            help_text=_(u"must be of the form “originator-YY-name”"))
    timestamp = models.DateTimeField(_(u"timestamp"))
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, related_name="sample_series",
                                                     verbose_name=_(u"currently responsible person"))
    description = models.TextField(_(u"description"))
    samples = models.ManyToManyField(Sample, blank=True, verbose_name=_(u"samples"), related_name="series")
    results = models.ManyToManyField(Result, blank=True, related_name="sample_series", verbose_name=_(u"results"))
    topic = models.ForeignKey(Topic, related_name="sample_series", verbose_name=_(u"topic"))

    class Meta:
        verbose_name = _(u"sample series")
        verbose_name_plural = _(u"sample serieses")

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.sample_series.show", [urlquote(self.name, safe="")])

    def get_data(self):
        u"""Extract the data of this sample series as a tree of nodes with
        lists of key–value pairs, ready to be used for the CSV table export.
        Every child of the top-level node is a sample of the sample series.
        See the `samples.views.csv_export` module for all the glory details.

        :Return:
          a node for building a CSV tree

        :rtype: `samples.csv_common.CSVNode`
        """
        _ = ugettext
        csv_node = CSVNode(self, unicode(self))
        csv_node.children.extend(sample.get_data() for sample in self.samples.all())
        # I don't think that any sample series properties are interesting for
        # table export; people only want to see the *sample* data.  Thus, I
        # don't set ``cvs_note.items``.
        return csv_node


class Initials(models.Model):
    u"""Model for initials of people or external operators.  They are used to
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
    initials = models.CharField(_(u"initials"), max_length=4, primary_key=True)
    user = models.OneToOneField(django.contrib.auth.models.User, verbose_name=_(u"user"),
                                related_name="initials", null=True, blank=True)
    external_operator = models.OneToOneField(ExternalOperator, verbose_name=_(u"external operator"),
                                             related_name="initials", null=True, blank=True)

    class Meta:
        verbose_name = _(u"initials")
            # Translation hint: Plural of “initials”
        verbose_name_plural = _(u"initialses")

    def __unicode__(self):
        return self.initials


class UserDetails(models.Model):
    u"""Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_(u"user"),
                                related_name="samples_user_details")
    my_samples = models.ManyToManyField(Sample, blank=True, related_name="watchers", verbose_name=_(u"my samples"))
    auto_addition_topics = models.ManyToManyField(
        Topic, blank=True, related_name="auto_adders", verbose_name=_(u"auto-addition topics"),
        help_text=_(u"new samples in these topics are automatically added to “My Samples”"))
    only_important_news = models.BooleanField(_(u"get only important news"), default=False)
    feed_entries = models.ManyToManyField("FeedEntry", verbose_name=_(u"feed entries"), related_name="users", blank=True)
    my_layers = models.CharField(_(u"my layers"), max_length=255, blank=True)
    u"""This string is of the form ``"nickname1: deposition1-layer1, nickname2:
    deposition2-layer2, ..."``, where “nickname” can be chosen freely except
    that it mustn't contain “:” or “,” or whitespace.  “deposition” is the
    *process id* (``Process.pk``, not the deposition number!) of the
    deposition, and “layer” is the layer number (`models_depositions.Layer.number`).
    """

    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")
        _ = lambda x: x
        permissions = (("edit_topic", _("Can edit topics, and can add new topics")),)

    def __unicode__(self):
        return unicode(self.user)
