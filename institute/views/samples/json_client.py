# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


"""Views that are intended only for the Remote Client and AJAX code.  While
also users can visit these links with their browser directly, it is not really
useful what they get there.  Note that the whole communication to the remote
client happens in JSON format.
"""

import datetime
from django.db.utils import IntegrityError
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import get_object_or_404
from django.http import Http404
import django.utils.timezone
from jb_common.models import Topic
from jb_common.utils.base import respond_in_json, JSONRequestException
import samples.utils.views as utils
from samples import models, permissions
import institute.models
from institute import layouts
import institute.utils.base


def get_substrates(sample):
    """Returns the substrate processes of a sample.  Of course normally, this
    should be exactly one.  They are returned in chronological order.

    :param sample: the sample whose substrate should be returned.

    :type sample: `samples.models.Sample`

    :return:
      the substrate processes of the sample

    :rtype: list of `institute.models.Substrate`
    """
    substrates = list(institute.models.Substrate.objects.filter(samples=sample))
    if sample.split_origin:
        substrates = get_substrates(sample.split_origin.parent) + substrates
    return substrates


def get_substrate(sample):
    """Returns the earliest substrate process of a sample.  The routine
    performs no checks it all.  It will fail loudly if the sample and its
    ancestors all don't have a substrate.  This is an interal error anyway.

    :param sample: the sample whose substrate should be returned.

    :type sample: `samples.models.Sample`

    :return:
      the substrate process of the sample

    :rtype: `institute.models.Substrate`
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

    :param request: the HTTP request object
    :param sample_id: the primary key of the sample

    :type request: HttpRequest
    :type sample_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    if not request.user.is_superuser:
        return respond_in_json(False)
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id))
    substrate = get_substrate(sample)
    return respond_in_json(substrate.get_data())


@never_cache
@require_http_methods(["GET"])
def next_deposition_number(request, letter):
    """Send the next free deposition number to a JSON client.

    :param request: the current HTTP Request object
    :param letter: the letter of the deposition system, see
        `utils.get_next_deposition_number`.

    :type request: HttpRequest
    :type letter: str

    :return:
      the next free deposition number for the given apparatus.

    :rtype: HttpResponse
    """
    return respond_in_json(institute.utils.base.get_next_deposition_number(letter))


def _get_solarsimulator_measurement_by_filepath(filepath, user):
    """Returns the ID of a solarsimulator measurement with the given filepath.
    Every solarsimulator measurement consists of single measurements which are
    associated with a data filepath each.  This function finds the measurement
    which contains a single (“cell”) measurement with the filepath.

    :param filepath: the path of the measurement file, as it is stored in the
        database
    :param user: the logged-in user

    :type filepath: str
    :type user: django.contrib.auth.models.User

    :return:
      the ID of the solarsimulator measurement which contains results from the
      given data file

    :rtype: int

    :raises permissions.PermissionError: if the user is not allowed to see the
        solarsimulator measurement
    :raises Http404: if the filepath was not found in the database
    """
    cells = institute.models.SolarsimulatorCellMeasurement.objects.filter(data_file=filepath)
    if cells.exists():
        measurement = cells[0].measurement
    else:
        raise Http404("No matching solarsimulator measurement found.")
    permissions.assert_can_view_physical_process(user, measurement)
    return measurement.id


@login_required
@never_cache
@require_http_methods(["GET"])
def get_solarsimulator_measurement_by_filepath(request):
    """Returns the measurement ID of the solarsimulator measurement which
    contains the given filepath.  See `_get_solarsimulator_measurement_by_filepath`.  The filepath
    is given in the query string parameter “``filepath``”.

    :param request: the HTTP request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    try:
        filepath = request.GET["filepath"]
    except KeyError:
        raise JSONRequestException(3, '"filepath" missing')
    return respond_in_json(_get_solarsimulator_measurement_by_filepath(filepath, request.user))


@login_required
@never_cache
@require_http_methods(["GET"])
def get_matching_solarsimulator_measurement(request, sample_id, irradiation, cell_position, date):
    """Finds the solarsimulator measurement which is best suited for the given
    data file.  This view is to solve the problem that for non-standard-Jülich
    cell layouts, many single data files must be merged into one solarsimulator
    measurements.  When importing them one by one, one has to find the already
    existing measurement to which they must be added.  This is done by this
    view.

    It returns the ID of the measurement, or ``None`` if none was found.

    :param request: the HTTP request object
    :param sample_id: the ID of the sample which was measured
    :param irradiation: the irradiation (AM1.5, BG7 etc) which was used
    :param cell_position: the position of the cell on the layout; don't mix it
        up with the *index* of the cell, which is the number used in the
        Solarsimulator datafile in the first column
    :param date: the day (not the time) of the measurement in YYYY-MM-DD format

    :type request: HttpRequest
    :type sample_id: str
    :type irradiation: str
    :type cell_position: str
    :type date: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    try:
        filepath = request.GET["filepath"]
    except KeyError:
        raise JSONRequestException(3, '"filepath" missing')
    try:
        return respond_in_json(_get_solarsimulator_measurement_by_filepath(filepath, request.user))
    except Http404:
        sample = get_object_or_404(models.Sample, id=sample_id)
        start_date = django.utils.timezone.make_aware(datetime.datetime.strptime(date, "%Y-%m-%d"))
        end_date = start_date + datetime.timedelta(days=1)
        matching_measurements = institute.models.SolarsimulatorMeasurement.objects.filter(
            samples__id=sample_id, irradiation=irradiation, timestamp__gte=start_date, timestamp__lt=end_date). \
            exclude(cells__position=cell_position).order_by("timestamp")
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

    :param request: the HTTP request object
    :param sample_id: the ID of the sample

    :type request: HttpRequest
    :type sample_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample = get_object_or_404(models.Sample, id=sample_id)
    try:
        timestamp = django.utils.timezone.make_aware(
            datetime.datetime.strptime(request.GET["timestamp"].partition(".")[0], "%Y-%m-%d %H:%M:%S"))
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
