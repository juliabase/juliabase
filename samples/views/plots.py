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


"""View for showing a plot as a PDF file.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six

import os.path
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from samples import models, permissions
from samples.views import utils
import jb_common.utils
from jb_common.signals import storage_changed


@login_required
def show_plot(request, process_id, plot_id, thumbnail):
    """Shows a particular plot.  Although its response is a bitmap rather than
    an HTML file, it is served by Django in order to enforce user permissions.

    :param request: the current HTTP Request object
    :param process_id: the database ID of the process to show
    :param plot_id: the plot_id of the image.  This is mostly ``u""`` because
        most measurement models have only one graphics.
    :param thumbnail: whether we serve a thumbnail instead of a real PDF plot

    :type request: HttpRequest
    :type process_id: unicode
    :type plot_id: unicode
    :type thumbnail: bool

    :return:
      the HTTP response object with the image

    :rtype: HttpResponse
    """
    process = get_object_or_404(models.Process, pk=utils.convert_id_to_int(process_id))
    process = process.actual_instance
    permissions.assert_can_view_physical_process(request.user, process)
    plot_filepath = process.calculate_plot_locations(plot_id)["thumbnail_file" if thumbnail else "plot_file"]
    datafile_name = process.get_datafile_name(plot_id)
    if datafile_name is None:
        raise Http404("No such plot available.")
    timestamps = [] if thumbnail else [sample.last_modified for sample in process.samples.all()]
    timestamps.append(process.last_modified)
    if datafile_name:
        datafile_names = datafile_name if isinstance(datafile_name, list) else [datafile_name]
        if not all(os.path.exists(filename) for filename in datafile_names):
            raise Http404("One of the raw datafiles was not found.")
        update_necessary = jb_common.utils.is_update_necessary(plot_filepath, datafile_names, timestamps)
    else:
        update_necessary = jb_common.utils.is_update_necessary(plot_filepath, timestamps=timestamps)
    if update_necessary:
        try:
            if thumbnail:
                figure = Figure(frameon=False, figsize=(4, 3))
                canvas = FigureCanvasAgg(figure)
                axes = figure.add_subplot(111)
                axes.set_position((0.17, 0.16, 0.78, 0.78))
                axes.grid(True)
                process.draw_plot(axes, plot_id, datafile_name, for_thumbnail=True)
                jb_common.utils.mkdirs(plot_filepath)
                canvas.print_figure(plot_filepath, dpi=settings.THUMBNAIL_WIDTH / 4)
            else:
                figure = Figure()
                canvas = FigureCanvasAgg(figure)
                axes = figure.add_subplot(111)
                axes.grid(True)
                axes.set_title(six.text_type(process))
                process.draw_plot(axes, plot_id, datafile_name, for_thumbnail=False)
                # FixMe: Activate this line with Matplotlib 1.1.0.
#                figure.tight_layout()
                jb_common.utils.mkdirs(plot_filepath)
                canvas.print_figure(plot_filepath, format="pdf")
            storage_changed.send(models.Process)
        except utils.PlotError as e:
            raise Http404(six.text_type(e) or "Plot could not be generated.")
    return jb_common.utils.static_file_response(plot_filepath,
                                                     None if thumbnail else process.get_plotfile_basename(plot_id) + ".pdf")
