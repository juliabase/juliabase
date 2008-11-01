#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""This module is the connection to the database.  It contains the *models*,
i.e. Python classes which represent the tables in the relational database.
Every class which inherits from ``models.Model`` is a MySQL table at the same
time, unless it has ``abstract = True`` set in their ``Meta`` subclass.

If you add fields here, and you have a MySQL database running which contains
already valuable data, you have to add the fields manually with SQL commands to
the database, too.  (There is a project called `“Django Evolution”`_ that tries
to improve this situation.)

.. _“Django Evolution”: http://code.google.com/p/django-evolution/

However, if you add new *classes*, you can just run ``./manage.py syncdb`` and
the new tables are automatically created.

:type default_location_of_deposited_samples: dict mapping `Deposition` to
  string.

:var all_physical_process_models: list of all models that denote physical
  processes (i.e. depositions, measurements, etching processes etc).  Such
  processes must have a permission of the form ``"add_edit_model_name"`` where
  the model name is in lowercase with underscores.  Additionally, they must
  have the method ``get_add_link`` (see `SixChamberDeposition.get_add_link`).
  For the sake of performance, I don't want to enforce the latter by a common
  parent class.

:type all_physical_process_models: list of ``class``.
"""

import hashlib, os.path, codecs
from django.db import models
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.utils import translation
from django.utils.http import urlquote, urlquote_plus
import django.core.urlresolvers
from django.contrib import admin
from django.template import defaultfilters
from chantal import settings
from chantal.samples import permissions

import matplotlib
matplotlib.use("Agg")
import pylab

def get_really_full_name(user):
    u"""Unfortunately, Django's ``get_full_name`` method for users returns the
    empty string if the user has no first and surname set.  However, it'd be
    sensible to use the login name as a fallback then.  This is realised here.

    :Parameters:
      - `user`: the user instance
    :type user: ``django.contrib.auth.models.User``

    :Return:
      The full, human-friendly name of the user

    :rtype: unicode
    """
    return user.get_full_name() or unicode(user)

class PlotError(Exception):
    u"""Raised if an error occurs while generating a plot.  Usually, it is
    raised in `Process.pylab_commands` and caught in `Process.generate_plot`.
    """
    pass

def read_techplot_file(filename, columns=(0, 1)):
    u"""Read a datafile in TechPlot format and return the content of selected
    columns.
    
    :Parameters:
      - `filename`: full path to the Techplot data file
      - `columns`: the columns that should be read.  Defaults to the first two,
        i.e., ``(0, 1)``.  Note that the column numbering starts with zero.

    :type filename: str
    :type columns: list of int

    :Return:
      List of all columns.  Every column is represented as a list of floating
      point values.

    :rtype: list of list of float

    :Exceptions:
      - `PlotError`: if something wents wrong with interpreting the file (I/O,
        unparseble data)
    """
    start_values = False
    try:
        datafile = codecs.open(filename, encoding="cp1252")
    except IOError:
        raise PlotError("datafile could not be opened")
    result = [[] for i in range(len(columns))]
    for line in datafile:
        if start_values:
            if line.startswith("END"):
                break
            cells = line.split()
            for column, result_array in zip(columns, result):
                try:
                    value = float(cells[column])
                except IndexError:
                    raise PlotError("datafile contained too few columns")
                except ValueError:
                    value = float("nan")
                result_array.append(value)
        elif line.startswith("BEGIN"):
            start_values = True
    datafile.close()
    return result

default_location_of_deposited_samples = {}
u"""Dictionary mapping process classes to strings which contain the default
location where samples can be found after this process has been performed.
This is used in
`samples.views.split_after_deposition.GlobalNewDataForm.__init__`.
"""

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
    class Meta:
        ordering = ["timestamp"]
        verbose_name = _(u"process")
        verbose_name_plural = _(u"processes")

class Deposition(Process):
    u"""The base class for deposition processes.  Note that, like `Process`,
    this must never be instantiated.  Instead, derive the concrete deposition
    class from it.
    
    Every derived class, if it has sub-objects which resemble layers, must
    implement them as a class derived from `Layer`, with a ``ForeignKey`` field
    pointing to the deposition class with ``relative_name="layers"``.  In other
    words, ``instance.layers.all()`` must work if ``instance`` is an instance
    of your deposition class.
    """
    number = models.CharField(_(u"deposition number"), max_length=15, unique=True)
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.main.show_deposition", [urlquote(self.number, safe="")])
    def __unicode__(self):
        _ = ugettext
        return _(u"deposition %s") % self.number
    class Meta:
        verbose_name = _(u"deposition")
        verbose_name_plural = _(u"depositions")

class SixChamberDeposition(Deposition):
    u"""6-chamber depositions.
    """
    carrier = models.CharField(_(u"carrier"), max_length=10, blank=True)
    def get_additional_template_context(self, process_context):
        u"""This method is called e.g. when the process list for a sample is
        being constructed.  It returns a dict with additional fields that are
        supposed to be given to the templates.

        ``"edit_url"`` and ``"duplicate_url"`` are somewhat special here
        because they are processed by the *outer* template (the one rendering
        the sample or sample series).  Other keys are just passed to the
        process template itself.  See also
        `samples.views.utils.ResultContext.digest_process` for further
        information.

        :Parameters:
          - `process_context`: the context of this process is for example the
            current sample, the requesting user, and maybe further info that is
            needed by the process to know what further things must be passed to
            the displaying templates (sample(-series) and process templates).

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        if permissions.has_permission_to_add_edit_physical_process(process_context.user, self):
            return {"edit_url": django.core.urlresolvers.reverse("edit_6-chamber_deposition",
                                                                 kwargs={"deposition_number": self.number}),
                    "duplicate_url": "%s?copy_from=%s" % (django.core.urlresolvers.reverse("add_6-chamber_deposition"),
                                                          urlquote_plus(self.number))}
        else:
            return {}
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.six_chamber_deposition.show", [urlquote(self.number, safe="")])
    @classmethod
    def get_add_link(cls):
        u"""Return all you need to generate a link to the “add” view for this
        process.  This is the URL, and a short text used for labeling it.  This
        starts with a capital letter, and it is not ended by a full stop.  For
        example, it may be ``u"Add 6-chamber deposition"``.

        This method marks the current class as a so-called physical process.
        This implies that it also must have an “add-edit” permission.

        :Return:
          the full URL to the add page for this process, hyperlink label like
          ``u"Add 6-chamber deposition"``

        :rtype: str, unicode
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_6-chamber_deposition"), _(u"Add 6-chamber deposition")
    class Meta:
        verbose_name = _(u"6-chamber deposition")
        verbose_name_plural = _(u"6-chamber depositions")
        _ = lambda x: x
        permissions = (("add_edit_six_chamber_deposition", _("Can create and edit 6-chamber depositions")),)
default_location_of_deposited_samples[SixChamberDeposition] = _(u"6-chamber deposition lab")
admin.site.register(SixChamberDeposition)

class HallMeasurement(Process):
    u"""This model is intended to store Hall measurements.  So far, all just
    fields here …
    """
    def __unicode__(self):
        _ = ugettext
        try:
            _(u"hall measurement of %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            return _(u"hall measurement #%d") % self.pk
    @classmethod
    def get_add_link(cls):
        u"""Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process, hyperlink label like
          ``u"Add 6-chamber deposition"``

        :rtype: str, unicode
        """
        _ = ugettext
        raise NotImplementedError
        return django.core.urlresolvers.reverse("add_hall_measurement"), _(u"Add hall measurement")
    class Meta:
        verbose_name = _(u"Hall measurement")
        verbose_name_plural = _(u"Hall measurements")
        _ = lambda x: x
        permissions = (("add_edit_hall_measurement", _("Can create and edit hall measurements")),)
admin.site.register(HallMeasurement)

class Layer(models.Model):
    u"""This is an abstract base model for deposition layers.  Now, this is the
    first *real* abstract model here.  It is abstract because it can never
    occur in a model relationship.  It just ensures that every layer has a
    number, because at least the MyLayers infrastructure relies on this.  (See
    for example `views.six_chamber_deposition.change_structure`, after ``if
    my_layer:``.)

    Every class derived from this model must point to their deposition with
    ``related_name="layers"``.  See also `Deposition`.
    """
    number = models.IntegerField(_(u"layer number"))
    class Meta:
        abstract = True
        ordering = ["number"]
        unique_together = ("deposition", "number")
        verbose_name = _(u"layer")
        verbose_name_plural = _(u"layers")

six_chamber_chamber_choices = (
    ("#1", "#1"),
    ("#2", "#2"),
    ("#3", "#3"),
    ("#4", "#4"),
    ("#5", "#5"),
    ("#6", "#6"),
    ("LL", "LL"),
    ("TL1", "TL1"),
    ("TL2", "TL2"))
u"""Contains all possible choices for `SixChamberLayer.chamber`.
"""

class SixChamberLayer(Layer):
    u"""One layer in a 6-chamber deposition.

    FixMe: Maybe `chamber` should become optional, too?
    """
    deposition = models.ForeignKey(SixChamberDeposition, related_name="layers", verbose_name=_(u"deposition"))
    chamber = models.CharField(_(u"chamber"), max_length=5, choices=six_chamber_chamber_choices)
    pressure = models.CharField(_(u"deposition pressure"), max_length=15, help_text=_(u"with unit"), blank=True)
    time = models.CharField(_(u"deposition time"), max_length=9, help_text=_(u"format HH:MM:SS"), blank=True)
    substrate_electrode_distance = \
        models.DecimalField(_(u"substrate–electrode distance"), null=True, blank=True, max_digits=4,
                            decimal_places=1, help_text=_(u"in mm"))
    comments = models.TextField(_(u"comments"), blank=True)
    transfer_in_chamber = models.CharField(_(u"transfer in the chamber"), max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField(_(u"pre-heat"), max_length=9, blank=True, help_text=_(u"format HH:MM:SS"))
    gas_pre_heat_gas = models.CharField(_(u"gas of gas pre-heat"), max_length=10, blank=True)
    gas_pre_heat_pressure = models.CharField(_(u"pressure of gas pre-heat"), max_length=15, blank=True,
                                             help_text=_(u"with unit"))
    gas_pre_heat_time = models.CharField(_(u"time of gas pre-heat"), max_length=15, blank=True,
                                         help_text=_(u"format HH:MM:SS"))
    heating_temperature = models.IntegerField(_(u"heating temperature"), help_text=_(u"in ℃"), null=True, blank=True)
    transfer_out_of_chamber = models.CharField(_(u"transfer out of the chamber"), max_length=10, default="Ar", blank=True)
    plasma_start_power = models.DecimalField(_(u"plasma start power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                             help_text=_(u"in W"))
    # FixMe:  Maybe NullBooleanField?
    plasma_start_with_carrier = models.BooleanField(_(u"plasma start with carrier"), default=False, null=True, blank=True)
    deposition_frequency = models.DecimalField(_(u"deposition frequency"), max_digits=5, decimal_places=2,
                                               null=True, blank=True, help_text=_(u"in MHz"))
    deposition_power = models.DecimalField(_(u"deposition power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text=_(u"in W"))
    base_pressure = models.FloatField(_(u"base pressure"), help_text=_(u"in Torr"), null=True, blank=True)
    def __unicode__(self):
        _ = ugettext
        return _(u"layer %(number)d of %(deposition)s") % {"number": self.number, "deposition": self.deposition}
    class Meta(Layer.Meta):
        verbose_name = _(u"6-chamber layer")
        verbose_name_plural = _(u"6-chamber layers")
admin.site.register(SixChamberLayer)

six_chamber_gas_choices = (
    ("SiH4", "SiH₄"),
    ("H2", "H₂"),
    ("PH3+SiH4", _(u"PH₃ in 2% SiH₄")),
    ("TMB", _(u"TMB in 1% He")),
    ("B2H6", _(u"B₂H₆ in 5ppm H₂")),
    ("CH4", "CH₄"),
    ("CO2", "CO₂"),
    ("GeH4", "GeH₄"),
    ("Ar", "Ar"),
    ("Si2H6", "Si₂H₆"),
    ("PH3", _(u"PH₃ in 10 ppm H₂")))
u"""Contains all possible choices for `SixChamberChannel.gas`.
"""
    
class SixChamberChannel(models.Model):
    u"""One channel of a certain layer in a 6-chamber deposition.
    """
    number = models.IntegerField(_(u"channel"))
    layer = models.ForeignKey(SixChamberLayer, related_name="channels", verbose_name=_(u"layer"))
    gas = models.CharField(_(u"gas and dilution"), max_length=30, choices=six_chamber_gas_choices)
    flow_rate = models.DecimalField(_(u"flow rate"), max_digits=4, decimal_places=1, help_text=_(u"in sccm"))
    def __unicode__(self):
        _ = ugettext
        return _(u"channel %(number)d of %(layer)s") % {"number": self.number, "layer": self.layer}
    class Meta:
        verbose_name = _(u"6-chamber channel")
        verbose_name_plural = _(u"6-chamber channels")
        unique_together = ("layer", "number")
        ordering = ["number"]
admin.site.register(SixChamberChannel)

class LargeAreaDeposition(Deposition):
    u"""Large-area depositions.
    """
    def get_additional_template_context(self, process_context):
        u"""See `SixChamberDeposition.get_additional_template_context`.

        :Parameters:
          - `process_context`: the context of this process

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        if permissions.has_permission_to_add_edit_physical_process(process_context.user, self):
            return {"edit_url": django.core.urlresolvers.reverse("edit_large-area_deposition",
                                                                 kwargs={"deposition_number": self.number}),
                    "duplicate_url": "%s?copy_from=%s" % (django.core.urlresolvers.reverse("add_large-area_deposition"),
                                                          urlquote_plus(self.number))}
        else:
            return {}
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.large_area_deposition.show", [urlquote(self.number, safe="")])
    @classmethod
    def get_add_link(cls):
        u"""Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process, hyperlink label like
          ``u"Add 6-chamber deposition"``

        :rtype: str, unicode
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_large-area_deposition"), _(u"Add large-area deposition")
    class Meta:
        verbose_name = _(u"large-area deposition")
        verbose_name_plural = _(u"large-area depositions")
        _ = lambda x: x
        permissions = (("add_edit_large_area_deposition", _("Can create and edit large-area depositions")),)
default_location_of_deposited_samples[SixChamberDeposition] = _(u"large-area deposition lab")
admin.site.register(LargeAreaDeposition)

large_area_layer_type_choices = (
    ("p", "p"),
    ("i", "i"),
    ("n", "n"),
)
large_area_station_choices = (
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
)
large_area_hf_frequency_choices = (
    ("13.56", _(u"13.56")),
    ("27.12", _(u"27.12")),
    ("40.68", _(u"40.68")),
)
# FixMe: should this really be made translatable?
large_area_electrode_choices = (
    ("NN large PC1", _(u"NN large PC1")),
    ("NN large PC2", _(u"NN large PC2")),
    ("NN large PC3", _(u"NN large PC3")),
    ("NN small 1", _(u"NN small 1")),
    ("NN small 2", _(u"NN small 2")),
    ("NN40 large PC1", _(u"NN40 large PC1")),
    ("NN40 large PC2", _(u"NN40 large PC2")),
)
class LargeAreaLayer(Layer):
    u"""One layer in a large-area deposition.

    *Important*: Numbers of large-area layers are the numbers after the “L-”
    because they must be ordinary integers!  This means that all layers of a
    deposition must be in the same calendar year, oh well …
    """
    deposition = models.ForeignKey(LargeAreaDeposition, related_name="layers", verbose_name=_(u"deposition"))
    date = models.DateField(_(u"date"))
    layer_type = models.CharField(_(u"layer type"), max_length=2, choices=large_area_layer_type_choices)
    station = models.CharField(_(u"station"), max_length=2, choices=large_area_station_choices)
    sih4 = models.DecimalField(_(u"SiH₄ flow rate"), max_digits=5, decimal_places=2, help_text=_(u"in sccm"))
    h2 = models.DecimalField(_(u"H₂ flow rate"), max_digits=5, decimal_places=1, help_text=_(u"in sccm"))
    tmb = models.DecimalField(u"TMB", max_digits=5, decimal_places=2, help_text=_(u"in sccm"), null=True, blank=True)
    ch4 = models.DecimalField(u"CH₄", max_digits=3, decimal_places=1, help_text=_(u"in sccm"), null=True, blank=True)
    co2 = models.DecimalField(u"CO₂", max_digits=4, decimal_places=1, help_text=_(u"in sccm"), null=True, blank=True)
    ph3 = models.DecimalField(u"PH₃", max_digits=3, decimal_places=1, help_text=_(u"in sccm"), null=True, blank=True)
    power = models.DecimalField(_(u"power"), max_digits=5, decimal_places=1, help_text=_(u"in W"))
    pressure = models.DecimalField(_(u"pressure"), max_digits=3, decimal_places=1, help_text=_(u"in Torr"))
    temperature = models.DecimalField(_(u"temperature"), max_digits=4, decimal_places=1, help_text=_(u"in ℃"))
    hf_frequency = models.DecimalField(_(u"HF frequency"), max_digits=5, decimal_places=2,
                                       choices=large_area_hf_frequency_choices, help_text=_(u"in MHz"))
    time = models.IntegerField(_(u"time"), help_text=_(u"in sec"))
    dc_bias = models.DecimalField(_(u"DC bias"), max_digits=3, decimal_places=1, help_text=_(u"in V"), null=True, blank=True)
    electrode = models.CharField(_(u"electrode"), max_length=30, choices=large_area_electrode_choices)
    # FixMe: Must be called "electrodes_distance".  Also in other modules.
    electrodes_distance = models.DecimalField(_(u"electrodes distance"), max_digits=4, decimal_places=1,
                                               help_text=_(u"in mm"))
    def __unicode__(self):
        _ = ugettext
        return _(u"layer %(number)d of %(deposition)s") % {"number": self.number, "deposition": self.deposition}
    class Meta(Layer.Meta):
        verbose_name = _(u"large-area layer")
        verbose_name_plural = _(u"large-area layers")
admin.site.register(LargeAreaLayer)

pds_root_dir = "/home/bronger/temp/pds/" if settings.IS_TESTSERVER else "/windows/T_www-data/daten/pds/"

class PDSMeasurement(Process):
    u"""Model for PDS measurements.
    """
    number = models.IntegerField(_(u"pd number"), unique=True)
    raw_datafile = models.CharField(_(u"raw data file"), max_length=200,
                                    help_text=_(u"only the relative path below \"pds/\""))
    evaluated_datafile = models.CharField(_(u"evaluated data file"), max_length=200,
                                          help_text=_("only the relative path below \"pds/\""), blank=True)
    def __unicode__(self):
        _ = ugettext
        try:
            return _(u"PDS measurement of %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            return _(u"PDS measurement #%d") % self.number
    def pylab_commands(self, number, filename):
        _ = ugettext
        x_values, y_values = read_techplot_file(filename)
        pylab.plot(x_values, y_values)
        pylab.xlabel(_(u"energy in eV"))
        pylab.ylabel(_(u"counts"))
    def get_datafile_name(self, number):
        return os.path.join(pds_root_dir, self.evaluated_datafile)
    def get_imagefile_basename(self, number):
        try:
            return ("pds_%s" % self.samples.get()).replace("*", "")
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            return "pds_pd%d" % self.number
    def get_additional_template_context(self, process_context):
        u"""See `SixChamberDeposition.get_additional_template_context`.

        :Parameters:
          - `process_context`: the context of this process

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        result = {}
        result["thumbnail"], result["figure"] = self.generate_plot()
        if permissions.has_permission_to_add_edit_physical_process(process_context.user, self):
            result["edit_url"] = django.core.urlresolvers.reverse("edit_pds_measurement", kwargs={"pd_number": self.number})
        return result
    @classmethod
    def get_add_link(cls):
        u"""Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process, hyperlink label like
          ``u"Add 6-chamber deposition"``

        :rtype: str, unicode
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_pds_measurement"), _(u"Add PDS measurement")
    class Meta:
        verbose_name = _(u"PDS measurement")
        verbose_name_plural = _(u"PDS measurements")
        _ = lambda x: x
        permissions = (("add_edit_pds_measurement", _("Can create and edit PDS measurements")),)
admin.site.register(PDSMeasurement)

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
        return self.name
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
            return ("show_sample_by_id", (), {"sample_id": str(self.pk)})
        else:
            return ("show_sample_by_name", [urlquote(self.name, safe="")])
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
    through `Sample.split_origin`.  This way one can walk though the path of
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
        u"""See `SixChamberDeposition.get_additional_template_context` for
        general information.

        :Parameters:
          - `process_context`: context information for this process.  This
            routine needs ``current_sample`` and ``original_sample`` from the
            process context.

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          sample split template: ``"parent"``, ``"original_sample"``,  and
          ``"current_sample"``.

        :rtype: dict mapping string to arbitrary objects
        """
        assert process_context.current_sample
        if process_context.current_sample != process_context.original_sample:
            parent = process_context.current_sample
        else:
            parent = None
        return {"parent": parent, "original_sample": process_context.original_sample,
                "current_sample": process_context.current_sample, "latest_descendant": process_context.latest_descendant}
    class Meta:
        verbose_name = _(u"sample split")
        verbose_name_plural = _(u"sample splits")
admin.site.register(SampleSplit)

substrate_materials = (
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
    def __unicode__(self):
        _ = ugettext
        try:
            return _(u"result for %s") % self.samples.get()
        except Sample.DoesNotExist, Sample.MultipleObjectsReturned:
            try:
                return _(u"result for %s") % self.sample_series.get()
            except SampleSeries.DoesNotExist, SampleSeries.MultipleObjectsReturned:
                return _(u"result #%d") % self.pk
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
          the full path to the original image in the local filesystem, the full
          path to the processed file in the local filesystem, and the full
          relative URL to the image on the website (i.e., only the domain is
          missing).  Note that the latter two are without file extension to
          remain flexible (even without the dot).

        :rtype: str, str, str
        """
        assert self.image_type != "none"
        hash_ = hashlib.sha1()
        hash_.update(settings.SECRET_KEY)
        hash_.update(repr(self.pk))
        basename = str(self.pk) + "-" + hash_.hexdigest()
        dirname = os.path.join("results", basename)
        try:
            os.makedirs(os.path.join(settings.MEDIA_ROOT, dirname))
        except OSError:
            pass
        filename = defaultfilters.slugify(unicode(self))
        relative_path = os.path.join(dirname, filename)
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        url_path = os.path.join(settings.MEDIA_URL, relative_path)
        thumbnail_extension = ".jpeg" if self.image_type == "jpeg" else ".png"
        return {"original": os.path.join(settings.UPLOADED_RESULT_IMAGES_ROOT, basename + "." + self.image_type),
                "thumbnail_file": file_path + thumbnail_extension, "image_file":  file_path + "." + self.image_type,
                "thumbnail_url": url_path + thumbnail_extension, "image_url": url_path + ".pdf"}
    def get_additional_template_context(self, process_context):
        u"""See `SixChamberDeposition.get_additional_template_context` for
        general information.

        :Parameters:
          - `process_context`: context information for this process.  This
            routine needs only ``user`` from the process context.

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with one additional fields that is supposed to be given to the
          sample split template, namely ``"edit_url"``.

        :rtype: dict mapping str to str
        """
        if permissions.has_permission_to_edit_result_process(process_context.user, self):
            return {"edit_url":
                        django.core.urlresolvers.reverse("samples.views.result.edit", kwargs={"process_id": self.pk})}
        else:
            return {}
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
    samples = models.ManyToManyField(Sample, blank=True, verbose_name=_(u"samples"), related_name="series")
    results = models.ManyToManyField(Result, blank=True, related_name="sample_series", verbose_name=_(u"results"))
    group = models.ForeignKey(django.contrib.auth.models.Group, related_name="sample_series", verbose_name=_(u"group"))
    def __unicode__(self):
        return self.name
    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.sample_series.show", [urlquote(self.name, safe="")])
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

class FeedEntry(models.Model):
    u"""Abstract base model for newsfeed entries.  This is also not really
    abstract as it has a table in the database, however, it is never
    instantiated itself.  Instead, see `find_actual_instance` which is also
    injected into this class.
    """
    originator = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"originator"))
    timestamp = models.DateTimeField(_(u"timestamp"), auto_now_add=True)
    important = models.BooleanField(_(u"is important"), default=True, null=True, blank=True)
    sha1_hash = models.CharField(_(u"SHA1 hex digest"), max_length=40, blank=True, editable=False)
    u"""You'll never calculate the SHA-1 hash yourself.  It is done in
    `save`."""
    def __unicode__(self):
        _ = ugettext
        return _(u"feed entry #%d") % self.pk
    def get_metadata(self):
        u"""Return the title of this feed entry, as a plain string (no HTML),
        and the categorisation (see the Atom feed specification, :RFC:`4646`,
        section 4.2.2).  It also returns a link if approriate (without domain
        but with the leading ``/``).

        :Return:
          a dictionary with the keys ``"title"``, ``"category term"``,
          ``"link"``, and ``"category label"``.  ``"link"`` is optional.

        :rtype: dict mapping str to unicode
        """
        raise NotImplementedError
    def get_additional_template_context(self, user_details):
        u"""Return a dictionary with additional context that should be
        available in the template.  It is similar to
        `Process.get_additional_context`.

        :Parameters:
          - `user_details`: the details of the user fetching the feed

        :type user_details: `UserDetails`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        raise NotImplementedError
    def save(self, *args, **kwargs):
        u"""Before saving the feed entry, I calculate an unsalted SHA-1 from
        the timestamp, the username of the originator, the object's ID, and the
        link (if given).  It is used for the GUID of this entry.

        Note that I have to call the parent's ``save()`` method twice and I
        pass the parameter only to the first call.

        :Return:
          ``None``
        """
        super(FeedEntry, self).save(*args, **kwargs)
        entry_hash = hashlib.sha1()
        entry_hash.update(repr(self.timestamp))
        entry_hash.update(repr(self.originator))
        entry_hash.update(repr(self.pk))
        self.sha1_hash = entry_hash.hexdigest()
        super(FeedEntry, self).save()
    class Meta:
        verbose_name = _(u"feed entry")
        verbose_name_plural = _(u"feed entries")
        ordering = ["-timestamp"]

class FeedNewSamples(FeedEntry):
    u"""Model for feed entries about new samples having been added to the database.
    """
    samples = models.ManyToManyField(Sample, verbose_name=_(u"samples"), blank=True)
    group = models.ForeignKey(django.contrib.auth.models.Group, verbose_name=_(u"group"))
    purpose = models.CharField(_(u"purpose"), max_length=80, blank=True)
    auto_adders = models.ManyToManyField("UserDetails", verbose_name=_(u"auto adders"), blank=True)
    def get_metadata(self):
        _ = ugettext
        result = {}
        result["title"] = ungettext(u"New sample in “%s”", u"New samples in “%s”", self.samples.count()) % self.group
        result["category term"] = "new samples"
        result["category label"] = _(u"new samples")
        return result
    def get_additional_template_context(self, user_details):
        return {"auto_added": self.auto_adders.filter(pk=user_details.pk).count() != 0}
    class Meta:
        verbose_name = _(u"new samples feed entry")
        verbose_name_plural = _(u"new samples feed entries")
admin.site.register(FeedNewSamples)

class FeedNewPhysicalProcess(FeedEntry):
    u"""Model for feed entries about new physical processes.
    """
    process = models.OneToOneField(Process, verbose_name=_(u"process"))
    def get_metadata(self):
        _ = ugettext
        result = {}
        process = self.process.find_actual_instance()
        result["title"] = _(u"New %s") % process
        result["category term"] = "new physical process"
        result["category label"] = _(u"new physical process")
        result["link"] = process.get_absolute_url()
        return result
    def get_additional_template_context(self, user_details):
        return {"process": self.process.find_actual_instance()}
    class Meta:
        verbose_name = _(u"new physical process feed entry")
        verbose_name_plural = _(u"new physical process feed entries")
admin.site.register(FeedNewPhysicalProcess)

class FeedEditedPhysicalProcess(FeedEntry):
    u"""Model for feed entries about edited physical processes.
    """
    process = models.ForeignKey(Process, verbose_name=_(u"process"))
    description = models.TextField(_(u"description"))
    def get_metadata(self):
        _ = ugettext
        result = {}
        process = self.process.find_actual_instance()
        result["title"] = _(u"Edited %s") % process
        result["category term"] = "new physical process"
        result["category label"] = _(u"new physical process")
        result["link"] = process.get_absolute_url()
        return result
    def get_additional_template_context(self, user_details):
        return {"process": self.process.find_actual_instance()}
    class Meta:
        verbose_name = _(u"edited physical process feed entry")
        verbose_name_plural = _(u"edited physical process feed entries")
admin.site.register(FeedEditedPhysicalProcess)

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
    feed_entries = models.ManyToManyField(FeedEntry, verbose_name=_(u"feed enties"), related_name="users")
    my_layers = models.CharField(_(u"my layers"), max_length=255, blank=True)
    u"""This string is of the form ``"nickname1: deposition1-layer1, nickname2:
    deposition2-layer2, ..."``, where “nickname” can be chosen freely except
    that it mustn't contain “:” or “,” or whitespace.  “deposition” is the
    *process id* (``Process.pk``, not the deposition number!) of the
    deposition, and “layer” is the layer number (`Layer.number`).
    """
    def __unicode__(self):
        return unicode(self.user)
    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")
        _ = lambda x: x
        permissions = (("edit_group_memberships", _("Can edit group memberships and add new groups")),)
admin.site.register(UserDetails)

import copy, inspect
_globals = copy.copy(globals())
all_models = [cls for cls in _globals.values() if inspect.isclass(cls) and issubclass(cls, models.Model)]
all_physical_process_models = [cls for cls in all_models if hasattr(cls, "get_add_link")]
class_hierarchy = inspect.getclasstree(all_models)
u"""Rather complicated list structure that represents the class hierarchy of
models in this module.  Nobody needs to understand it as long as the internal
`inject_direct_subclasses` is working."""
def find_actual_instance(self):
    u"""This is a module function but is is injected into ``Models.model`` to
    become a class method for all models of Chantal.  If you call this method
    on a database instance, you get the leaf class instance of this model.  For
    example, if you retrieved a `Process` from the database, you get the
    `SixChamberDeposition` (if it is one).  This way, polymorphism actually
    works with the relational database.

    :Return:
      an instance of the actual model class for this database entry.

    :rtype: ``models.Model``.
    """
    try:
        return self.__actual_instance
    except AttributeError:
        if not self.direct_subclasses:
            self.__actual_instance = self
        else:
            for cls in self.direct_subclasses:
                name = cls.__name__.lower()
                if hasattr(self, name):
                    instance = getattr(self, name)
                    self.__actual_instance = instance.find_actual_instance()
                    break
            else:
                raise Exception("internal error: instance not found")
        return self.__actual_instance
models.Model.find_actual_instance = find_actual_instance
def inject_direct_subclasses(parent, hierarchy):
    u"""This is a mere helper function which injects a list with all subclasses
    into the class itself, under the name ``direct_subclasses``.  It is only
    for use by `find_actual_instance`.

    This is basically a tree walker through the weird nested data structure
    returned by ``inspect.getclasstree`` and stored in `class_hierarchy`.

    :Parameters:
      - `parent`: the class to which the subclasses should be added
      - `hierarchy`: the remaining class inheritance hierarchy that has to be
        processed.

    :type parent: class, descendant of ``models.Model``
    :type hierarchy: list as returned by ``inspect.getclasstree``
    """
    i = 0
    while i < len(hierarchy):
        hierarchy[i][0].direct_subclasses = []
        if parent:
            parent.direct_subclasses.append(hierarchy[i][0])
        if i + 1 < len(hierarchy) and isinstance(hierarchy[i+1], list):
            inject_direct_subclasses(hierarchy[i][0], hierarchy[i+1])
            i += 2
        else:
            i += 1
inject_direct_subclasses(None, class_hierarchy)
del _globals, cls
