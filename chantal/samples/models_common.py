#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""The most basic models like ``Sample``, ``SampleSeries``, ``UserDetails``
etc.  It is important to see that this module is imported by almost all other
models modules.  Therefore, you *must* *not* import any Chantal modles module
here, in particular not ``models.py``.  Otherwise, you'd end up with
irresolvable cyclic imports.
"""

import hashlib, os.path, shutil, subprocess, datetime
import cPickle as pickle
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.utils import translation
from django.contrib import admin
from django.template import defaultfilters
from django.utils.http import urlquote, urlquote_plus
import django.core.urlresolvers
from django.conf import settings
from django.db import models
from chantal.samples import permissions
from chantal.samples.views import shared_utils
from chantal.samples.views.csv_node import CSVNode, CSVItem

import matplotlib
matplotlib.use("Agg")
import pylab

class PlotError(Exception):
    u"""Raised if an error occurs while generating a plot.  Usually, it is
    raised in `Process.pylab_commands` and caught in `Process.generate_plot`.
    """
    pass

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
    def __unicode__(self):
        return self.name
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.external_operator.show", [urlquote(self.pk, safe="")])
    class Meta:
        verbose_name = _(u"external operator")
        verbose_name_plural = _(u"external operators")
        _ = lambda x: x
        permissions = (("add_external_operator", _("Can add an external operator")),)
admin.site.register(ExternalOperator)

timestamp_inaccuracy_choices = (
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
    def calculate_image_filename_and_url(self, number):
        u"""Get the location of a (plot) image in the local filesystem as well
        as on the webpage.  The results are without file extension so that you
        can append ``".jpeg"`` or ``".png"`` (for the thumbnails) or ``".pdf"``
        (for the high-quality figure) yourself.

        Every plot or image resides in a directory with a peculiar name in
        order to be un-guessable.  This is not security by obscurity because we
        really use cryptographic hashes.  While it still is not the highest
        level of security, it is a sensible compromise between security and
        performance.  Besides, this method excludes name collisions.

        :Parameters:
          - `number`: the number of the image.  This is mostly ``0`` because
            most measurement models have only one graphics.

        :type number: int

        :Return:
          the full path to the image file in the local filesystem, and the full
          relative URL to the image on the website (i.e., only the domain is
          missing).  Note that both is without file extension to remain flexible
          (even without the dot).

        :rtype: str, str
        """
        hash_ = hashlib.sha1()
        hash_.update(settings.SECRET_KEY)
        hash_.update(translation.get_language())
        hash_.update(repr(self.pk))
        hash_.update(repr(number))
        dirname = os.path.join("results", str(self.pk) + "-" + hash_.hexdigest())
        try:
            os.makedirs(os.path.join(settings.MEDIA_ROOT, dirname))
        except OSError:
            pass
        filename = self.get_imagefile_basename(number)
        relative_path = os.path.join(dirname, filename)
        return os.path.join(settings.MEDIA_ROOT, relative_path), os.path.join(settings.MEDIA_URL, relative_path)
    def generate_plot(self, number=0):
        u"""The central plot-generating method which shouldn't be overridden by
        a derived class.  This method tests whether it is necessary to generate
        new plots from the original datafile (by checking existence and file
        timestamps), and does it if necessary.

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
        output_filename, output_url = self.calculate_image_filename_and_url(number)
        if not os.path.exists(datafile_name):
            return None, None
        thumbnail_filename = output_filename + ".png"
        thumbnail_necessary = \
            not os.path.exists(thumbnail_filename) or os.stat(thumbnail_filename).st_mtime < os.stat(datafile_name).st_mtime
        figure_filename = output_filename + ".pdf"
        figure_necessary = \
            not os.path.exists(figure_filename) or os.stat(figure_filename).st_mtime < os.stat(datafile_name).st_mtime
        if thumbnail_necessary or figure_necessary:
            pylab.figure()
            try:
                self.pylab_commands(number, datafile_name)
                if thumbnail_necessary:
                    pylab.savefig(open(thumbnail_filename, "wb"), facecolor=("#e6e6e6"), edgecolor=("#e6e6e6"), dpi=50)
                pylab.title(unicode(self))
                if figure_necessary:
                    pylab.savefig(open(figure_filename, "wb"), format="pdf")
            except (IOError, PlotError):
                pylab.close("all")
                return None, None
            finally:
                pylab.close("all")
        return output_url+".png", output_url+".pdf"
    def pylab_commands(self, number, filename):
        u"""Generate a plot using Pylab commands.  You may do whatever you want
        here – but eventually, there must be a savable Matplotlib plot.  You
        should't use ``pylab.figure``.  The ``filename`` parameter ist not
        really necessary but it makes things a little bit faster and easier.

        This method must be overridden in derived classes that wish to offer
        plots.

        :Parameters:
          - `number`: the number of the plot.  For most models offering plots,
            this can only be zero and as such is not used it all in this
            method.
          - `filename`: the filename of the original data file

        :type number: int
        :type filename: str

        :Exceptions:
          - `PlotError`: if anything went wrong during the generation of the
            plot
        """
        raise NotImplementedError
    def get_datafile_name(self, number):
        u"""Get the name of the file with the original data for the plot with
        the given ``number``.

        This method must be overridden in derived classes that wish to offer
        plots.

        :Parameters:
          - `number`: the number of the plot.  For most models offering plots,
            this can only be zero and as such is not used it all in this
            method.

        :type number: int

        :Return:
          the absolute path of the file with the original data for this plot in
          the local filesystem.

        :rtype: str
        """
        raise NotImplementedError
    def get_imagefile_basename(self, number):
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
        export.  See the `chantal.samples.views.csv_export` module for all the
        glory details.

        :Return:
          a node for building a CSV tree

        :rtype: `chantal.samples.views.csv_node.CSVNode`
        """
        csv_node = CSVNode(self)
        csv_node.items = [CSVItem(_(u"timestamp"), self.timestamp, "process"),
                          CSVItem(_(u"operator"), shared_utils.get_really_full_name(self.operator), "process"),
                          CSVItem(_(u"comments"), self.comments, "process")]
        return csv_node
    @classmethod
    def get_monthly_processes(cls, year, month):
        return cls.objects.filter(timestamp__year=year, timestamp__month=month).select_related()
    class Meta:
        ordering = ["timestamp"]
        verbose_name = _(u"process")
        verbose_name_plural = _(u"processes")

class Sample(models.Model):
    u"""The model for samples.
    """
    name = models.CharField(_(u"name"), max_length=30, unique=True)
    current_location = models.CharField(_(u"current location"), max_length=50)
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, related_name="samples",
                                                     verbose_name=_(u"currently responsible person"))
    purpose = models.CharField(_(u"purpose"), max_length=80, blank=True)
    tags = models.CharField(_(u"tags"), max_length=255, blank=True, help_text=_(u"separated with commas, no whitespace"))
    split_origin = models.ForeignKey("SampleSplit", null=True, blank=True, related_name="pieces",
                                     verbose_name=_(u"split origin"))
    processes = models.ManyToManyField(Process, blank=True, related_name="samples", verbose_name=_(u"processes"))
    group = models.ForeignKey(django.contrib.auth.models.Group, null=True, blank=True, related_name="samples",
                              verbose_name=_(u"group"))
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
                      split_origin=self.split_origin, group=self.group)
    @models.permalink
    def get_absolute_url(self):
        if self.name.startswith("*"):
            return ("show_sample_by_id", (), {"sample_id": str(self.pk), "path_suffix": ""})
        else:
            return ("show_sample_by_name", [urlquote(self.name, safe="")])
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
        `chantal.samples.views.csv_export` module for all the glory details.

        :Return:
          a node for building a CSV tree

        :rtype: `chantal.samples.views.csv_node.CSVNode`
        """
        _ = ugettext
        csv_node = CSVNode(self)
        csv_node.children.extend(process.find_actual_instance().get_data() for process in self.processes.all())
        # I don't think that any sample properties are interesting for table
        # export; people only want to see the *process* data.  Thus, I don't
        # set ``cvs_note.items``.
        return csv_node
    class Meta:
        verbose_name = _(u"sample")
        verbose_name_plural = _(u"samples")
        ordering = ["name"]
        _ = lambda x: x
        permissions = (("view_all_samples", _("Can view all samples (senior user)")),)
admin.site.register(Sample)

class SampleAlias(models.Model):
    u"""Model for former names of samples.  If a sample gets renamed (for
    example, because it was deposited), its old name is moved here.  Note that
    aliases needn't be unique.  Two old names may be the same.  However, they
    must not be equal to a `Sample.name`.
    """
    name = models.CharField(_(u"name"), max_length=30)
    sample = models.ForeignKey(Sample, verbose_name=_(u"sample"), related_name="aliases")
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _(u"name alias")
        verbose_name_plural = _(u"name aliases")
admin.site.register(SampleAlias)

class SampleSplit(Process):
    u"""A process where a sample is split into many child samples.  The sample
    split itself is a process of the *parent*, whereas the children point to it
    through `Sample.split_origin`.  This way one can walk through the path of
    relationship in both directions.
    """
    parent = models.ForeignKey(Sample, verbose_name=_(u"parent"))
    u"""This field exists just for a fast lookup.  Its existence is actually a
    violation of the non-redundancy rule in database models because one could
    find the parent via the samples attribute every process has, too."""
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
    class Meta:
        verbose_name = _(u"sample split")
        verbose_name_plural = _(u"sample splits")
admin.site.register(SampleSplit)

substrate_materials = (
    ("custom", _(u"custom")),
    ("asahi-u", _(u"ASAHI-U")),
    ("100-Si", _(u"silicon 100 wafer")),
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
    def __unicode__(self):
        return self.material
    def get_data(self):
        # See `Process.get_data` for the documentation.
        _ = ugettext
        csv_node = super(Substrate, self).get_data()
        csv_node.items.append(CSVItem(_(u"material"), self.get_material_display()))
        return csv_node
    class Meta:
        verbose_name = _(u"substrate")
        verbose_name_plural = _(u"substrates")
admin.site.register(Substrate)

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
    reason = models.CharField(_(u"cause of death"), max_length=50, choices=sample_death_reasons)
    def __unicode__(self):
        _ = ugettext
        try:
            return _(u"cease of existence of %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            return _(u"cease of existence #%d") % self.pk
    class Meta:
        verbose_name = _(u"cease of existence")
        verbose_name_plural = _(u"ceases of existence")
admin.site.register(SampleDeath)

image_type_choices=(("none", _(u"none")),
                    ("pdf", "PDF"),
                    ("png", "PNG"),
                    ("jpeg", "JPEG"),
                    )
class Result(Process):
    u"""Adds a result to the history of a sample.  This may be just a comment,
    or a plot, or an image, or a link.
    """
    title = models.CharField(_(u"title"), max_length=50)
    image_type = models.CharField(_("image file type"), max_length=4, choices=image_type_choices, default="none")
    quantities_and_values = models.TextField(_("quantities and values"), blank=True, help_text=_(u"in Python pickle format"))
    u"""This is a data structure, serialised in Python pickle format (protocol
    0, because this is UTF-8 safe; you never know what the database does with
    it).  If you un-pickle it, it is a tuple with two items.  The first is a
    list of unicodes with all quantities (the table headings).  The second is a
    list of lists with unicodes (the values; the table cells).  The outer list
    is the set of rows, the inner the columns.  No Markdown is used here, just
    plain strings.  (The HTML entity substitution in quantities has taken place
    already *before* anyting is written here.)
    """
    def __unicode__(self):
        _ = ugettext
        try:
            return _(u"result for %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            try:
                return _(u"result for %s") % self.sample_series.get()
            except SampleSeries.DoesNotExist, SampleSeries.MultipleObjectsReturned:
                return _(u"result #%d") % self.pk
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.result.show", (self.pk,))
    def get_image_locations(self):
        u"""Get the location of the image in the local filesystem as well
        as on the webpage.  The results are without file extension so that you
        can append ``".jpeg"`` or ``".png"`` (for the thumbnails) or ``".pdf"``
        (for the high-quality figure) yourself.

        Every image exist three times on the local filesystem.  First, it is in
        ``/var/lib/chantal_images``.  This is the original file, uploaded by
        the user.  Its filename is the hash plus the respective file extension
        (jpeg, png, or pdf).

        Secondly, there are the *processed* images in the ``MEDIA_ROOT``.  This
        is very similar to plots, see
        `Process.calculate_image_filename_and_url`.  There are two of them, the
        thumbnail and the full version.  The full version is always a PDF (not
        necessarily A4), whereas the thumbnail is either a JPEG or a PNG,
        depending on the original file type.

        :Return:
          a dictionary containing the following keys:

          =====================  =========================================
                 key                           meaning
          =====================  =========================================
          ``"original"``         full path to the original image file
          ``"image_directory"``  full path to the directory containing the
                                 processed images
          ``"thumbnail_file"``   full path to the thumbnail file
          ``"image_file"``       full path to the image (always a PDF)
          ``"thumbnail_url"``    full relative URL to the thumbnail (i.e.,
                                 without domain)
          ``"image_url"``        full relative URL to the image
          =====================  =========================================

        :rtype: dict mapping str to str
        """
        assert self.image_type != "none"
        hash_ = hashlib.sha1()
        hash_.update(settings.SECRET_KEY)
        hash_.update(repr(self.pk))
        basename = str(self.pk) + "-" + hash_.hexdigest()
        dirname = os.path.join("results", basename)
        filename = defaultfilters.slugify(unicode(self))
        relative_path = os.path.join(dirname, filename)
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        url_path = os.path.join(settings.MEDIA_URL, relative_path)
        original_extension = "." + self.image_type
        thumbnail_extension = "_thumbnail.jpeg" if self.image_type == "jpeg" else "_thumbnail.png"
        return {"original": os.path.join(settings.UPLOADED_RESULT_IMAGES_ROOT, basename + original_extension),
                "image_directory": os.path.join(settings.MEDIA_ROOT, dirname),
                "thumbnail_file": file_path + thumbnail_extension, "image_file": file_path + original_extension,
                "thumbnail_url": url_path + thumbnail_extension, "image_url": url_path + original_extension}
    def get_image(self):
        u"""Assures that the images of this result process are generated and
        returns their URLs.

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
        if not os.path.exists(image_locations["thumbnail_file"]) or not os.path.exists(image_locations["image_file"]):
            if not os.path.exists(image_locations["original"]):
                return {"thumbnail_url": None, "image_url": None}
            try:
                os.makedirs(image_locations["image_directory"])
            except OSError:
                pass
            if not os.path.exists(image_locations["thumbnail_file"]):
                subprocess.call(["convert", image_locations["original"] + ("[0]" if self.image_type == "pdf" else ""),
                                 "-resize", "%(width)dx%(width)d" % {"width": settings.THUMBNAIL_WIDTH},
                                 image_locations["thumbnail_file"]])
            if not os.path.exists(image_locations["image_file"]):
                shutil.copy(image_locations["original"], image_locations["image_file"])
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
            result["quantities"], result["value_lists"] = pickle.loads(str(self.quantities_and_values))
        return result
    def get_data(self):
        u"""Extract the data of this result process as a tree of nodes (or a
        single node) with lists of key–value pairs, ready to be used for the
        CSV table export.  See the `chantal.samples.views.csv_export` module
        for all the glory details.

        However, I should point out the peculiarities of result processes in
        this respect.  Result comments are not exported, just the table.  If
        the table contains only one row (which should be the case almost
        always), one one CSV tree node is returned, with this row as the
        key–value list.

        If the result table has more than one row, for each row, a sub-node is
        generated, which contains the row columns in its key–value list.

        :Return:
          a node for building a CSV tree

        :rtype: `chantal.samples.views.csv_node.CSVNode`
        """
        _ = ugettext
        csv_node = super(Result, self).get_data()
        quantities, value_lists = pickle.loads(str(self.quantities_and_values))
        if len(value_lists) > 1:
            for value_list in value_lists:
                child_node = CSVNode(_(u"row"))
                child_node.items = [CSVItem(quantities[i], value) for i, value in enumerate(value_list)]
                csv_node.children.append(child_node)
        else:
            csv_node.items = [CSVItem(quantity, value) for quantity, value in zip(quantities, value_lists[0])]
        return csv_node
    class Meta:
        verbose_name = _(u"result")
        verbose_name_plural = _(u"results")
admin.site.register(Result)

class SampleSeries(models.Model):
    u"""A sample series groups together zero or more `Sample`.  It must belong
    to a group, and it may contain processes, however, only *result processes*.
    The `name` and the `timestamp` of a sample series can never change after it
    has been created.
    """
    name = models.CharField(_(u"name"), max_length=50, primary_key=True,
                            help_text=_(u"must be of the form “originator-YY-name”"))
    timestamp = models.DateTimeField(_(u"timestamp"))
    currently_responsible_person = models.ForeignKey(django.contrib.auth.models.User, related_name="sample_series",
                                                     verbose_name=_(u"currently responsible person"))
    description = models.TextField(_(u"description"))
    samples = models.ManyToManyField(Sample, blank=True, verbose_name=_(u"samples"), related_name="series")
    results = models.ManyToManyField(Result, blank=True, related_name="sample_series", verbose_name=_(u"results"))
    group = models.ForeignKey(django.contrib.auth.models.Group, related_name="sample_series", verbose_name=_(u"group"))
    def __unicode__(self):
        return self.name
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.sample_series.show", [urlquote(self.name, safe="")])
    def get_data(self):
        u"""Extract the data of this sample series as a tree of nodes with
        lists of key–value pairs, ready to be used for the CSV table export.
        Every child of the top-level node is a sample of the sample series.
        See the `chantal.samples.views.csv_export` module for all the glory
        details.

        :Return:
          a node for building a CSV tree

        :rtype: `chantal.samples.views.csv_node.CSVNode`
        """
        _ = ugettext
        csv_node = CSVNode(self)
        csv_node.children.extend(sample.get_data() for sample in self.samples.all())
        # I don't think that any sample series properties are interesting for
        # table export; people only want to see the *sample* data.  Thus, I
        # don't set ``cvs_note.items``.
        return csv_node
    class Meta:
        verbose_name = _(u"sample series")
        verbose_name_plural = _(u"sample serieses")
admin.site.register(SampleSeries)

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
    def __unicode__(self):
        return self.initials
    class Meta:
        verbose_name = _(u"initials")
        verbose_name_plural = _(u"initialses")
admin.site.register(Initials)

languages = (
    ("de", u"Deutsch"),
    ("en", u"English"),
    )
u"""Contains all possible choices for `UserDetails.language`.
"""

class UserDetails(models.Model):
    u"""Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_(u"user"))
    language = models.CharField(_(u"language"), max_length=10, choices=languages, default="de")
    my_samples = models.ManyToManyField(Sample, blank=True, related_name="watchers", verbose_name=_(u"my samples"))
    auto_addition_groups = models.ManyToManyField(
        django.contrib.auth.models.Group, blank=True, related_name="auto_adders", verbose_name=_(u"auto-addition groups"),
        help_text=_(u"new samples in these groups are automatically added to “My Samples”"))
    only_important_news = models.BooleanField(_(u"get only important news"), default=False, null=True, blank=True)
    feed_entries = models.ManyToManyField("FeedEntry", verbose_name=_(u"feed enties"), related_name="users", blank=True)
    my_layers = models.CharField(_(u"my layers"), max_length=255, blank=True)
    u"""This string is of the form ``"nickname1: deposition1-layer1, nickname2:
    deposition2-layer2, ..."``, where “nickname” can be chosen freely except
    that it mustn't contain “:” or “,” or whitespace.  “deposition” is the
    *process id* (``Process.pk``, not the deposition number!) of the
    deposition, and “layer” is the layer number (`models_depositions.Layer.number`).
    """
    def __unicode__(self):
        return unicode(self.user)
    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")
        _ = lambda x: x
        permissions = (("edit_group_memberships", _("Can edit group memberships and add new groups")),)
admin.site.register(UserDetails)
