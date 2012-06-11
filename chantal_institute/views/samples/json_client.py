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


"""Views that are intended only for the Remote Client and AJAX code.  While
also users can visit these links with their browser directly, it is not really
useful what they get there.  Note that the whole communication to the remote
client happens in JSON format.
"""

from __future__ import absolute_import, unicode_literals

import os.path, re, datetime
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.conf import settings
from samples.views import utils
from samples import models, permissions
from chantal_institute import models as institute_models, layouts
from chantal_common.utils import respond_in_json, JSONRequestException
from django.db.models import Q


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


raman_path_pattern = re.compile(r".*?(?P<number>\d+)\..+$")

@login_required
@never_cache
@require_http_methods(["GET"])
def raman_file_path(request):
    try:
        sample_id = request.GET["sample_id"]
        apparatus = request.GET["apparatus"]
        central_wavelength = request.GET["central_wavelength"]
    except KeyError:
        raise JSONRequestException(3, '"sample_id", "apparatus", or "central_wavelength" missing')
    try:
        apparatus_path = {"1": "raman", "2": "raman_2", "3": "raman_3"}[apparatus]
    except KeyError:
        raise JSONRequestException(5, '"apparatus" must be 1, 2, or 3')
    if central_wavelength not in [choice[0] for choice in institute_models.raman_excitation_choices if choice[0] != "??"]:
        raise JSONRequestException(5, '"central_wavelength" has an invalid value')
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id))
    sample_name_normalized = sample.name.lower().replace("/", "-")
    substrate = get_substrate(sample)
    if permissions.has_permission_to_view_physical_process(request.user, substrate):
        if substrate.material == "corning":
            suffix = "c"
        elif substrate.material == "aluminium foil":
            suffix = "a"
        elif substrate.material == "quartz":
            suffix = "q"
        else:
            # FixMe: We need a real fallback letter, and more coverage of the other
            # letters.
            suffix = "c"
    else:
        suffix = "c"
    path = os.path.join(apparatus_path, sample.currently_responsible_person.username if apparatus in ["1", "2"]
                        else request.user.username, central_wavelength, sample_name_normalized + suffix)
    raman_model = {"1": institute_models.RamanMeasurementOne, "2": institute_models.RamanMeasurementTwo,
                   "3": institute_models.RamanMeasurementThree}[apparatus]
    similar_paths = list(raman_model.objects.filter(
            datafile__regex="/" + re.escape(sample_name_normalized + suffix) + r"[0-9]+\.").
                         values_list("datafile", flat=True))
    numbers = [0]
    for existing_path in similar_paths:
        match = raman_path_pattern.match(existing_path)
        if match:
            numbers.append(int(match.group("number")))
    path += str(max(numbers) + 1)
    path += ".txt" if apparatus == "3" else ".asc"
    return respond_in_json(path)


@login_required
@never_cache
@require_http_methods(["GET"])
def raman_by_filepath(request, filepath):
    """Searches for the Raman measurement by its filepath.  It returns the
    apparatus number and the measurement number.

    :Parameters:
      - `request`: the HTTP request object
      - `filepath`: the filepath of the Raman measurement

    :type request: ``HttpRequest``
    :type sample_id: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    filepath = filepath.replace("\\", "/")
    try:
        measurement = institute_models.RamanMeasurementOne.objects.get(datafile__iexact=filepath)
    except institute_models.RamanMeasurementOne.DoesNotExist:
        try:
            measurement = institute_models.RamanMeasurementTwo.objects.get(datafile__iexact=filepath)
        except institute_models.RamanMeasurementTwo.DoesNotExist:
            measurement = get_object_or_404(institute_models.RamanMeasurementThree, datafile__iexact=filepath)
    permissions.assert_can_view_physical_process(request.user, measurement)
    return respond_in_json([measurement.get_apparatus_number(), measurement.number])


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
    dark_cells = institute_models.SolarsimulatorDarkCellMeasurement.objects.filter(data_file=filepath)
    if photo_cells.exists():
        measurement = photo_cells[0].measurement
    elif dark_cells.exists():
        measurement = dark_cells[0].measurement
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
        matching_measurements = institute_models.SolarsimulatorDarkMeasurement.objects.filter(
            samples__id=sample_id, irradiance=irradiance, timestamp__gte=start_date, timestamp__lt=end_date). \
            exclude(dark_cells__position=cell_position).order_by("timestamp") \
            if irradiance == "dark" else \
            institute_models.SolarsimulatorPhotoMeasurement.objects.filter(
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


@login_required
@never_cache
@require_http_methods(["GET"])
def get_current_conductivity_measurement_set(request, apparatus, sample_id):
    """Returns the ID of the conductivity measurement set to which the single
    conductivity measurement should be appended.  The latter is given by its
    timestamp in the ``timestamp`` GET parameter.  Its format must be
    ``YYYY-MM-DD HH:MM:SS``.

    If no matching measurement set is found, ``None`` is returned.

    Note that this function only works if the single measurement is the last
    one so far.  In other words, there must not be another single conductivity
    measurement for this sample and apparatus in the database which has a
    timestamp after the given one.

    :Parameters:
      - `request`: the HTTP request object
      - `apparatus`: the apparatus number of the measurement setup; must be
        “conductivity0”, “conductivity1”, or “conductivity2”
      - `sample_id`: the primary key of the sample

    :type request: ``HttpRequest``
    :type apparatus: unicode
    :type sample_id: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """

    def only_one_working_night_inbetween(timestamp1, timestamp2):
        if timestamp1 >= timestamp2:
            raise JSONRequestException(5, '"timestamp" too early')
        difference = timestamp2.toordinal() - timestamp1.toordinal()
        return difference <= 1 or difference <= 3 and timestamp1.weekday() == 4

    sample = get_object_or_404(models.Sample, id=sample_id)
    permissions.get_sample_clearance(request.user, sample)
    try:
        timestamp = datetime.datetime.strptime(request.GET["timestamp"].partition(".")[0], "%Y-%m-%d %H:%M:%S")
    except KeyError:
        raise JSONRequestException(3, '"timestamp" missing')
    except ValueError:
        raise JSONRequestException(5, '"timestamp" has invalid format')
    try:
        latest_set = sample.processes.filter(conductivitymeasurementset__apparatus=apparatus).latest()
    except models.Process.DoesNotExist:
        pass
    else:
        if only_one_working_night_inbetween(latest_set.timestamp, timestamp):
            if not sample.processes.filter(timestamp__range=(latest_set.timestamp, timestamp)). \
                    exclude(id=latest_set.id).exists():
                if not institute_models.SingleConductivityMeasurement.objects.filter(
                    measurement_set__apparatus=apparatus, timestamp__range=(latest_set.timestamp, timestamp)). \
                    exclude(measurement_set=latest_set).exists():
                    return respond_in_json(latest_set.pk)
    return respond_in_json(None)


def _get_dsr_by_filepath(filepath, user):
    """Returns the ID of a dsr measurement with the given filepath.

    :Parameters:
      - `filepath`: the path of the measurement file, as it is stored in the
        database
      - `user`: the logged-in user

    :type filepath: unicode
    :type user: ``django.contrib.auth.models.User``

    :Return:
      the ID of the dsr measurement which contains results from the
      given data file

    :rtype: int

    :Exceptions:
      - `permissions.PermissionError`: if the user is not allowed to see the
        dsr measurement
      - `Http404`: if the filepath was not found in the database
    """
    measurements = institute_models.DSRMeasurement.objects.filter(parameter_file=filepath)
    if measurements.exists():
        measurement = measurements[0]
    else:
        raise Http404("No matching dsr measurement found.")
    permissions.assert_can_view_physical_process(user, measurement)
    return measurement.id


@login_required
@never_cache
@require_http_methods(["GET"])
def get_dsr_by_filepath(request):
    """Returns the measurement ID of the dsr measurement which
    contains the given filepath.  See `_get_dsr_by_filepath`.  The filepath
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
    return respond_in_json(_get_dsr_by_filepath(filepath, request.user))
