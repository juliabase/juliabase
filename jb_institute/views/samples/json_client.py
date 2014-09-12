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


"""Views that are intended only for the Remote Client and AJAX code.  While
also users can visit these links with their browser directly, it is not really
useful what they get there.  Note that the whole communication to the remote
client happens in JSON format.
"""

from __future__ import absolute_import, unicode_literals

import datetime
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.shortcuts import get_object_or_404
from django.http import Http404
from samples.views import utils
from samples import models, permissions
from jb_institute import models as institute_models, layouts
from jb_common.utils import respond_in_json, JSONRequestException


def get_substrates(sample):
    """Returns the substrate processes of a sample.  Of course normally, this
    should be exactly one.  They are returned in chronological order.

    :Parameters:
      - `sample`: the sample whose substrate should be returned.

    :type sample: `models.Sample`

    :Return:
      the substrate processes of the sample

    :rtype: list of `institute_models.Substrate`
    """
    substrates = list(institute_models.Substrate.objects.filter(samples=sample))
    if sample.split_origin:
        substrates = get_substrates(sample.split_origin.parent) + substrates
    return substrates


def get_substrate(sample):
    """Returns the earliest substrate process of a sample.  The routine
    performs no checks it all.  It will fail loudly if the sample and its
    ancestors all don't have a substrate.  This is an interal error anyway.

    :Parameters:
      - `sample`: the sample whose substrate should be returned.

    :type sample: `models.Sample`

    :Return:
      the substrate process of the sample

    :rtype: `institute_models.Substrate`
    """
    return get_substrates(sample)[0]


@login_required
@never_cache
@require_http_methods(["GET"])
def substrate_by_sample(request, sample_id):
    """Searches for the substrate of a sample.  It returns a dictionary with
    the substrate data.  If the sample isn't found, a 404 is returned.  If
    something else went wrong (in particular, no substrate was found),
    ``False`` is returned.

    :Parameters:
      - `request`: the HTTP request object
      - `sample_id`: the primary key of the sample

    :type request: ``HttpRequest``
    :type sample_id: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    if not request.user.is_staff:
        return respond_in_json(False)
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id))
    substrate = get_substrate(sample)
    return respond_in_json(substrate.get_data().to_dict())


def _get_maike_by_filepath(filepath, user):
    """Returns the ID of a solarsimulator measurement with the given filepath.
    Every solarsimulator measurement consists of single measurements which are
    associated with a data filepath each.  This function finds the measurement
    which contains a single (“cell”) measurement with the filepath.

    :Parameters:
      - `filepath`: the path of the measurement file, as it is stored in the
        database
      - `user`: the logged-in user

    :type filepath: unicode
    :type user: ``django.contrib.auth.models.User``

    :Return:
      the ID of the solarsimulator measurement which contains results from the
      given data file

    :rtype: int

    :Exceptions:
      - `permissions.PermissionError`: if the user is not allowed to see the
        solarsimulator measurement
      - `Http404`: if the filepath was not found in the database
    """
    photo_cells = institute_models.SolarsimulatorPhotoCellMeasurement.objects.filter(data_file=filepath)
    if photo_cells.exists():
        measurement = photo_cells[0].measurement
    else:
        raise Http404("No matching solarsimulator measurement found.")
    permissions.assert_can_view_physical_process(user, measurement)
    return measurement.id


@login_required
@never_cache
@require_http_methods(["GET"])
def get_maike_by_filepath(request):
    """Returns the measurement ID of the solarsimulator measurement which
    contains the given filepath.  See `_get_maike_by_filepath`.  The filepath
    is given in the query string parameter “``filepath``”.

    :Parameters:
      - `request`: the HTTP request object

    :type request: ``HttpRequest``

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    try:
        filepath = request.GET["filepath"]
    except KeyError:
        raise JSONRequestException(3, '"filepath" missing')
    return respond_in_json(_get_maike_by_filepath(filepath, request.user))


@login_required
@never_cache
@require_http_methods(["GET"])
def get_matching_solarsimulator_measurement(request, sample_id, irradiance, cell_position, date):
    """Finds the solarsimulator measurement which is best suited for the given
    data file.  This view is to solve the problem that for non-standard-Jülich
    cell layouts, many single data files must be merged into one solarsimulator
    measurements.  When importing them one by one, one has to find the already
    existing measurement to which they must be added.  This is done by this
    view.

    It returns the ID of the measurement, or ``None`` if none was found.

    :Parameters:
      - `request`: the HTTP request object
      - `sample_id`: the ID of the sample which was measured
      - `irradiance`: the irradiance (AM1.5, BG7 etc) which was used
      - `cell_position`: the position of the cell on the layout; don't mix it
        up with the *index* of the cell, which is the number used in the MAIKE
        datafile in the first column
      - `date`: the day (not the time) of the measurement in YYYY-MM-DD format

    :type request: ``HttpRequest``
    :type sample_id: unicode
    :type irradiance: unicode
    :type cell_position: unicode
    :type date: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    try:
        filepath = request.GET["filepath"]
    except KeyError:
        raise JSONRequestException(3, '"filepath" missing')
    try:
        return respond_in_json(_get_maike_by_filepath(filepath, request.user))
    except Http404:
        sample = get_object_or_404(models.Sample, id=sample_id)
        start_date = datetime.datetime.strptime(date, "%Y-%m-%d")
        end_date = start_date + datetime.timedelta(days=1)
        matching_measurements = institute_models.SolarsimulatorPhotoMeasurement.objects.filter(
            samples__id=sample_id, irradiance=irradiance, timestamp__gte=start_date, timestamp__lt=end_date). \
            exclude(photo_cells__position=cell_position).order_by("timestamp")
        if matching_measurements.exists():
            solarsimulator_measurement = matching_measurements[0]
            permissions.assert_can_fully_view_sample(request.user, sample)
            permissions.assert_can_view_physical_process(request.user, solarsimulator_measurement)
            return respond_in_json(solarsimulator_measurement.id)
        else:
            return respond_in_json(None)


@login_required
@never_cache
@require_http_methods(["GET"])
def get_current_structuring(request, sample_id):
    """Find the structuring process which is active for the given sample at a
    given timestamp.  The “``timestamp``” is an optional parameter in the query
    string in the format ``YYYY-MM-YY HH:MM:SS``.  If given, find the latest
    structuring process before that timestamp.  Otherwise, find the lastest
    structuring of the sample.  Typically, the timestamp is the timestamp of
    the process which needs the structuring, e.g. a solarsimulator measurement.

    It returns the ID of the structuring process, or ``None`` if none was
    found.

    :Parameters:
      - `request`: the HTTP request object
      - `sample_id`: the ID of the sample

    :type request: ``HttpRequest``
    :type sample_id: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample = get_object_or_404(models.Sample, id=sample_id)
    try:
        timestamp = datetime.datetime.strptime(request.GET["timestamp"].partition(".")[0], "%Y-%m-%d %H:%M:%S")
    except KeyError:
        timestamp = None
    except ValueError:
        raise JSONRequestException(5, '"timestamp" has invalid format')
    try:
        structuring = layouts.get_current_structuring(sample, timestamp)
    except layouts.NoStructuringFound:
        result = None
    else:
        permissions.assert_can_fully_view_sample(request.user, sample)
        permissions.assert_can_view_physical_process(request.user, structuring)
        result = structuring.id
    return respond_in_json(result)
