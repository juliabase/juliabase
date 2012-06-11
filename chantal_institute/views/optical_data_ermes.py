#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


from __future__ import absolute_import, division, unicode_literals

import os.path, datetime, codecs
from django.utils.translation import ugettext as _, get_language
from django.shortcuts import render_to_response
from django.template import RequestContext
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils.encoding import smart_str
from samples.views import utils
import chantal_common.utils
from chantal_common.signals import storage_changed
import django.core.urlresolvers
from samples.views.shared_utils import PlotError


def calculate_plot_locations(filename):

    plot_url = django.core.urlresolvers.reverse("ermes_optical_plot", kwargs={"filename": str(filename)})
    thumbnail_url = django.core.urlresolvers.reverse("ermes_optical_plot_thumbnail",
                                                         kwargs={"filename": str(filename)})
    basename = "ermes-optical-data-{0}-{1}".format(get_language(), filename[:filename.rfind(".")])
    return {"plot_file": os.path.join(settings.CACHE_ROOT, "plots", basename + ".pdf"),
            "plot_url": plot_url,
            "thumbnail_file": os.path.join(settings.CACHE_ROOT, "plots", basename + ".png"),
            "thumbnail_url": thumbnail_url}


def read_optical_data_plot_file(filename, columns):
    try:
        datafile = codecs.open(filename, encoding="cp1252")
    except IOError:
        raise PlotError("datafile could not be opened")
    result = [[] for i in range(len(columns))]
    for line in datafile.readlines()[2:]:
            if not line.strip():
                continue
            cells = line.strip().split(",")
            for column, result_array in zip(columns, result):
                try:
                    value = float(cells[column])
                except IndexError:
                    raise PlotError("datafile contained too few columns")
                except ValueError:
                    value = float("nan")
                result_array.append(value)
    datafile.close()
    return result

def draw_plot(axes, file_path, for_thumbnail):
    x_values, y1_values, y2_values = read_optical_data_plot_file(file_path, (1, 2, 3))
    x_label, y_label, y2_label = _("wavelength in nm"), _("n"), _("k")
    axes.plot(x_values, y1_values, color="b")
    fontsize = 9
    axes.set_xlabel(x_label, fontsize=fontsize)
    axes.set_ylabel(y_label, fontsize=fontsize)
    for x in axes.get_xticklabels():
        x.set_fontsize(fontsize)
    for yl in axes.get_yticklabels():
        yl.set_fontsize(fontsize)
        yl.set_color("b")
    axes2 = axes.twinx()
    axes2.plot(x_values, y2_values, color="r")
    axes2.set_ylabel(y2_label, fontsize=fontsize)
    for yr in axes2.get_yticklabels():
        yr.set_fontsize(fontsize)
        yr.set_color("r")


def get_datafile_path(filename):
    return os.path.join(settings.ERMES_OPTICAL_DATA_ROOT_DIR, filename)


@login_required
def show_plot(request, filename, thumbnail):
    """Shows a particular plot.  Although its response is a bitmap rather than
    an HTML file, it is served by Django in order to enforce user permissions.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the database ID of the process to show
      - `filename`: the filename of the image.  This is mostly ``u""`` because
        most measurement models have only one graphics.
      - `thumbnail`: whether we serve a thumbnail instead of a real PDF plot

    :type request: ``HttpRequest``
    :type thumbnail: bool

    :Returns:
      the HTTP response object with the image

    :rtype: ``HttpResponse``
    """
    plot_filepath = calculate_plot_locations(filename)["thumbnail_file" if thumbnail else "plot_file"]
    datafile_path = get_datafile_path(filename)
    if datafile_path is None:
        raise Http404("No such plot available.")
    timestamps = [datetime.datetime.fromtimestamp(os.path.getmtime(datafile_path))]
    if datafile_path:
        datafile_names = datafile_path if isinstance(datafile_path, list) else [datafile_path]
        # FixMe: This is only necessary as long as we don't have WSGI running
        # in daemon mode.  Then, Trac (or whatever) seems to set the LANG
        # environ variable to an invalid value, causing os.stat (which is
        # called by isdir) to fail.
        datafile_names = map(smart_str, datafile_names)
        if not all(os.path.exists(filename_) for filename_ in datafile_names):
            raise Http404("One of the raw datafiles was not found.")
        update_necessary = chantal_common.utils.is_update_necessary(plot_filepath, datafile_names, timestamps)
    else:
        update_necessary = chantal_common.utils.is_update_necessary(plot_filepath, timestamps=timestamps)
    if update_necessary:
        try:
            if thumbnail:
                figure = Figure(frameon=False, figsize=(4, 3))
                canvas = FigureCanvasAgg(figure)
                axes = figure.add_subplot(111)
                axes.set_position((0.17, 0.16, 0.7, 0.7))
                axes.grid(True)
                draw_plot(axes, datafile_path, for_thumbnail=True)
                chantal_common.utils.mkdirs(plot_filepath)
                canvas.print_figure(plot_filepath, dpi=settings.THUMBNAIL_WIDTH / 4)
            else:
                figure = Figure()
                canvas = FigureCanvasAgg(figure)
                axes = figure.add_subplot(111)
                axes.grid(True)
                title = open(datafile_path, "r").readline().split(":")[1].strip()
                axes.set_title(unicode(title))
                draw_plot(axes, datafile_path, for_thumbnail=False)
                chantal_common.utils.mkdirs(plot_filepath)
                canvas.print_figure(plot_filepath, format="pdf")
            storage_changed.send(figure)
        except utils.PlotError as e:
            raise Http404(unicode(e) or "Plot could not be generated.")
    return chantal_common.utils.static_file_response(plot_filepath,
                                                     None if thumbnail else filename.replace(".txt", ".pdf"))

@login_required
def show(request):
    plot_urls = {}
    disclaimer = ""
    for entry in os.listdir(settings.ERMES_OPTICAL_DATA_ROOT_DIR):
            if entry == "README.txt":
                disclaimer = b"".join(open(os.path.join(settings.ERMES_OPTICAL_DATA_ROOT_DIR, entry), "r").readlines())
            else:
                title = open(os.path.join(settings.ERMES_OPTICAL_DATA_ROOT_DIR, entry), "r").readline().split(":")[1].strip()
                plot_locations = calculate_plot_locations(entry)
                plot_urls[title] = (plot_locations["thumbnail_url"], plot_locations["plot_url"], entry)
    template_context = {"title": _(u"Optical data obtained by ellipsometry and PDS"),
                        "disclaimer": disclaimer,
                        "plot_urls": plot_urls,
                        }
    return render_to_response("samples/show_optical_data.html", template_context, context_instance=RequestContext(request))
