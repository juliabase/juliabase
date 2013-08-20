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


"""General helper functions for the views.  Try to avoid using it outside the
views package.  All symbols from `shared_utils` are also available here.  So
`shared_utils` should be useful only for the Remote Client.
"""

from __future__ import absolute_import, unicode_literals

from chantal_common import mimeparse
from chantal_common.models import Department
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import render_to_response
from django.template import Context, RequestContext
from django.utils.encoding import iri_to_uri
from django.utils.translation import ugettext as _
from django.contrib.contenttypes.models import ContentType
from functools import update_wrapper
from samples import models, permissions
from samples.views.shared_utils import *
from samples.views.table_export import build_column_group_list, ColumnGroupsForm, \
    ColumnsForm, generate_table_rows, flatten_tree, OldDataForm, SwitchRowForm, \
    defaultfilters, UnicodeWriter
import chantal_common.utils
import datetime
import copy
import json
import re
import string


old_sample_name_pattern = re.compile(r"\d\d[A-Z]-\d{3,4}([-A-Za-z_/][-A-Za-z_/0-9#()]*)?$")
new_sample_name_pattern = re.compile(r"""(\d\d-([A-Z]{2}\d{,2}|[A-Z]{3}\d?|[A-Z]{4})|  # initials of a user
                                         [A-Z]{2}\d\d|[A-Z]{3}\d|[A-Z]{4})             # external operator
                                         -[-A-Za-z_/0-9#()]+$""", re.VERBOSE)
provisional_sample_name_pattern = re.compile(r"\*(?P<id>\d+)$")
def sample_name_format(name):
    """Determines which sample name format the given name has.  It doesn't
    test whether the sample name is existing, nor if the initials are valid.

    :Parameters:
      - `name`: the sample name

    :type name: unicode

    :Return:
      ``"old"`` if the sample name is of the old format, ``"new"`` if it is of
      the new format (i.e. not derived from a deposition number), and
      ``"provisional"`` if it is a provisional sample name.  ``None`` if the
      name had no valid format.

    :rtype: str or ``NoneType``.
    """
    if old_sample_name_pattern.match(name):
        return "old"
    elif new_sample_name_pattern.match(name):
        return "new"
    elif provisional_sample_name_pattern.match(name):
        return "provisional"


def get_sample(sample_name):
    """Lookup a sample by name.  You may also give an alias.  If more than one
    sample is found (can only happen via aliases), it returns a list.  Matching
    is exact.

    :Parameters:
      - `sample_name`: the name or alias of the sample

    :type sample_name: unicode

    :Return:
      the found sample.  If more than one sample was found, a list of them.  If
      none was found, ``None``.

    :rtype: `models.Sample`, list of `models.Sample`, or ``NoneType``
    """
    try:
        sample = models.Sample.objects.get(name=sample_name)
    except models.Sample.DoesNotExist:
        aliases = [alias.sample for alias in models.SampleAlias.objects.filter(name=sample_name)]
        if len(aliases) == 1:
            return aliases[0]
        return aliases or None
    else:
        return sample


def does_sample_exist(sample_name):
    """Returns ``True`` if the sample name exists in the database.

    :Parameters:
      - `sample_name`: the name or alias of the sample

    :type sample_name: unicode

    :Return:
      whether a sample with this name exists

    :rtype: bool
    """
    return models.Sample.objects.filter(name=sample_name).exists() or \
        models.SampleAlias.objects.filter(name=sample_name).exists()


def normalize_sample_name(sample_name):
    """Returns the current name of the sample.

    :Parameters:
      - `sample_name`: the name or alias of the sample

    :type sample_name: unicode

    :Return:
      The current name of the sample.  This is only different from the input if
      you gave an alias.

    :rtype: unicode
    """
    if models.Sample.objects.filter(name=sample_name).exists():
        return sample_name
    try:
        sample_alias = models.SampleAlias.objects.get(name=sample_name)
    except models.SampleAlias.DoesNotExist:
        return
    else:
        return sample_alias.sample.name


deposition_index_pattern = re.compile(r"\d{3,4}")

def get_next_deposition_number(letter):
    """Find a good next deposition number.  For example, if the last run was
    called “08B-045”, this routine yields “08B-046” (unless the new year has
    begun).

    :Parameters:
      - `letter`: the indentifying letter of the deposition apparatus.  For
        example, it is ``"B"`` for the 6-chamber deposition.

    :type letter: str

    :Return:
      A so-far unused deposition number for the current calendar year for the
      given deposition apparatus.
    """
    prefix = r"{0}{1}-".format(datetime.date.today().strftime("%y"), letter)
    prefix_length = len(prefix)
    pattern_string = r"^{0}[0-9]+".format(re.escape(prefix))
    deposition_numbers = \
        models.Deposition.objects.filter(number__regex=pattern_string).values_list("number", flat=True).iterator()
    numbers = [int(deposition_index_pattern.match(deposition_number[prefix_length:]).group())
               for deposition_number in deposition_numbers]
    next_number = max(numbers) + 1 if numbers else 1
    return prefix + "{0:03}".format(next_number)


class AmbiguityException(Exception):
    """Exception if a sample lookup leads to more than one matching alias
    (remember that alias names needn't be unique).  It is raised in
    `lookup_sample` and typically caught in Chantal's own middleware.
    """

    def __init__(self, sample_name, samples):
        self.sample_name, self.samples = sample_name, samples


def lookup_sample(sample_name, user, with_clearance=False):
    """Looks up the ``sample_name`` in the database (also among the aliases),
    and returns that sample if it was found *and* the current user is allowed
    to view it.  Shortened provisional names like “*2” are also found.  If
    nothing is found or the permissions are not sufficient, it raises an
    exception.

    :Parameters:
      - `sample_name`: name of the sample
      - `user`: the currently logged-in user
      - `with_clearance`: whether also clearances should be serached for and
        returned

    :type sample_name: unicode
    :type user: ``django.contrib.auth.models.User``
    :type with_clearance: bool

    :Return:
      the single found sample; or the sample and the clearance instance if this
      is necessary to view the sample and ``with_clearance=True``

    :rtype: `models.Sample` or `models.Sample`, `models.Clearance`

    :Exceptions:
      - `Http404`: if the sample name could not be found
      - `AmbiguityException`: if more than one matching alias was found
      - `permissions.PermissionError`: if the user is not allowed to view the
        sample
    """
    match = provisional_sample_name_pattern.match(sample_name)
    if match:
        sample_name = "*{0:05}".format(int(match.group("id")))
    sample = get_sample(sample_name)
    if not sample:
        raise Http404("Sample {name} could not be found (neither as an alias).".format(name=sample_name))
    if isinstance(sample, list):
        raise AmbiguityException(sample_name, sample)
    if with_clearance:
        clearance = permissions.get_sample_clearance(user, sample)
        return sample, clearance
    else:
        permissions.assert_can_fully_view_sample(user, sample)
        return sample


def convert_id_to_int(process_id):
    """If the user gives a process ID via the browser, it must be converted to
    an integer because this is what's stored in the database.  (Well, actually
    SQL gives a string, too, but that's beside the point.)  This routine
    converts it to a real integer and tests also for validity (not for
    availability in the database).

    FixMe: This should be replaced with a function the gets the database model
    class as an additional parameter and returns the found object, along the
    lines of ``get_object_or_404``.  Then, it should also allow for ``None`` as
    the `process_id`.

    :Parameters:
      - `process_id`: the pristine process ID as given via the URL by the user

    :type process_id: str

    :Return:
      the process ID as an integer number

    :rtype: int

    :Exceptions:
      - `Http404`: if the process_id didn't represent an integer number.
    """
    try:
        return int(process_id)
    except ValueError:
        raise Http404("Invalid ID: “{id}”".format(id=process_id))


def successful_response(request, success_report=None, view=None, kwargs={}, query_string="", forced=False,
                        json_response=True):
    """After a POST request was successfully processed, there is typically a
    redirect to another page – maybe the main menu, or the page from where the
    add/edit request was started.

    The latter is appended to the URL as a query string with the ``next`` key,
    e.g.::

        /chantal/6-chamber_deposition/08B410/edit/?next=/chantal/samples/08B410a

    This routine generated the proper ``HttpResponse`` object that contains the
    redirection.  It always has HTTP status code 303 (“see other”).

    If the request came from the Chantal Remote Client, the response is a
    pickled ``json_response``.  (Normally, a simple ``True``.)

    :Parameters:
      - `request`: the current HTTP request
      - `success_report`: an optional short success message reported to the
        user on the next view
      - `view`: the view name/function to redirect to; defaults to the main
        menu page (same when ``None`` is given)
      - `kwargs`: group parameters in the URL pattern that have to be filled
      - `query_string`: the *quoted* query string to be appended, without the
        leading ``"?"``
      - `forced`: If ``True``, go to ``view`` even if a “next” URL is
        available.  Defaults to ``False``.  See `bulk_rename.bulk_rename` for
        using this option to generate some sort of nested forwarding.
      - `json_response`: object which is to be sent as a pickled response to
        the remote client; defaults to ``True``.

    :type request: ``HttpRequest``
    :type success_report: unicode
    :type view: str or function
    :type kwargs: dict
    :type query_string: unicode
    :type forced: bool
    :type json_response: ``object``

    :Return:
      the HTTP response object to be returned to the view's caller

    :rtype: ``HttpResponse``
    """
    if chantal_common.utils.is_json_requested(request):
        return chantal_common.utils.respond_in_json(json_response)
    return chantal_common.utils.successful_response(request, success_report, view or "samples.views.main.main_menu", kwargs,
                                                    query_string, forced)


def remove_samples_from_my_samples(samples, user):
    """Remove the given samples from the user's MySamples list

    :Parameters:
      - `samples`: the samples to be removed.  FixMe: How does it react if a
        sample hasn't been in ``my_samples``?
      - `user`: the user whose MySamples list is affected

    :type samples: list of `models.Sample`
    :type user: ``django.contrib.auth.models.User``
    """
    for sample in samples:
        sample.watchers.remove(user)


class StructuredSeries(object):
    """Helper class to pass sample series data to the main menu template.
    This is *not* a data strcuture for sample series.  It just stores all data
    needed to display a certain sample series to a certain user.  It is used in
    `StructuredTopic` and `build_structured_sample_list`.

    :ivar sample_series: the sample series for which data should be collected
      in this object
    :ivar name: the name of the sample series
    :ivar timestamp: the creation timestamp of the sample series
    :ivar samples: all samples belonging to this sample series, *and* being
      part the list of samples to be processed
    :ivar is_complete: a read-only property.  If ``False``, there are samples
      in the sample series not included into the list because they were missing
      on “My Samples”.  In other words, the user deliberately gets an
      incomplete list of samples and should be informed about it.

    :type sample_series: `models.SampleSeries`
    :type name: unicode
    :type timestamp: ``datetime.datetime``
    :type samples: list of `models.Sample`
    :type is_complete: bool
    """

    def __init__(self, sample_series):
        self.sample_series = sample_series
        self.name = sample_series.name
        self.timestamp = sample_series.timestamp
        self.samples = []
        self.__is_complete = None

    def append(self, sample):
        """Adds a sample to this sample series view.

        :Parameters:
          - `sample`: the sample

        :type sample: `models.Sample`
        """
        assert self.__is_complete is None
        self.samples.append(sample)

    @property
    def is_complete(self):
        if self.__is_complete is None:
            sample_series_length = self.sample_series.samples.count()
            assert sample_series_length >= len(self.samples)
            self.__is_complete = sample_series_length == len(self.samples)
        return self.__is_complete


class StructuredTopic(object):
    """Class that represents one topic which contains samples and sample
    series, used for `build_structured_sample_list`.

    :ivar topic: the underlying Chantal topic which is represented by this
      instance.

    :ivar topic_name: the underlying Chantal topic's name which is represented
      by this instance.  It may be a surrogate name if the user is not allowed
      to see the actual name.

    :ivar samples: the samples of this topic which belong to the “My Samples”
      of the user but which don't belong to any sample series.

    :ivar sample_series: the sample series which belong to this topic and
      which contain “My Samples” of the user.  They themselves contain a list
      of their samples.  See `StructuredSeries` for further information.

    :type topic: ``chantal_common.models.Topic``
    :type samples: list of `models.Sample`
    :type sample_series: list of `StructuredSeries`
    """

    def __init__(self, topic, user):
        self.topic = topic
        self.topic_name = topic.get_name_for_user(user)
        self.samples = []
        self.sample_series = []

    def sort_sample_series(self):
        self.sample_series.sort(key=lambda series: series.timestamp, reverse=True)


def build_structured_sample_list(samples, user):
    """Generate a nested datastructure which contains the given samples in a
    handy way to be layouted in a certain way.  This routine is used for the
    “My Samples” list in the main menu, and for the multiple-selection box for
    samples in various views.  It is a list of `StructuredTopic` at the
    top-level.

    As far as sorting is concerned, all topics are sorted by alphabet, all
    sample series by reverse timestamp of origin, and all samples by name.

    :Parameters:
      - `samples`: the samples to be processed; it doesn't matter if a sample
        occurs twice because this list is made unique first
      - `user`: the user which sees the sample list eventually

    :type samples: list of `models.Sample`
    :type user: ``django.contrib.auth.models.User``

    :Return:
      all topics of the user with his series and samples in them, all
      topicless samples; both is sorted

    :rtype: list of `StructuredTopic`, list of `models.Sample`
    """
    structured_series = {}
    structured_topics = {}
    topicless_samples = []
    for sample in sorted(set(samples), key=lambda sample: (sample.tags, sample.name)):
        containing_series = sample.series.all()
        if containing_series:
            for series in containing_series:
                if series.name not in structured_series:
                    structured_series[series.name] = StructuredSeries(series)
                    topicname = series.topic.name
                    if topicname not in structured_topics:
                        structured_topics[topicname] = StructuredTopic(series.topic, user)
                    structured_topics[topicname].sample_series.append(structured_series[series.name])
                structured_series[series.name].append(sample)
        elif sample.topic:
            topicname = sample.topic.name
            if topicname not in structured_topics:
                structured_topics[topicname] = StructuredTopic(sample.topic, user)
            structured_topics[topicname].samples.append(sample)
        else:
            topicless_samples.append(sample)
    structured_topics = sorted(structured_topics.itervalues(), key=lambda structured_topic: structured_topic.topic.id,
                               reverse=True)
    for structured_topic in structured_topics:
        structured_topic.sort_sample_series()
    return structured_topics, topicless_samples


def extract_preset_sample(request):
    """Extract a sample from a query string.  All physical processes as well
    as result processes may have an optional parameter in the query string,
    namely the sample to which they should be applied (results even a sample
    series, too).  If such a parameter is present, the given sample – if
    existing – must be added to the list of selectable samples, and it must be
    the initially marked sample.

    This routine is used in all views for creating physical processes.  It is
    not used for result processes because they need a given sample *series*,
    too, and this would have been over-generalisation.

    This routine extracts the sample name from the query string and returns the
    sample.  If nothing was given or the sample non-existing, it returns
    ``None``.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the sample given in the query string, if any

    :rtype: `models.Sample` or ``NoneType``
    """
    if "sample" in request.GET:
        try:
            return models.Sample.objects.get(name=request.GET["sample"])
        except models.Sample.DoesNotExist:
            pass


def format_enumeration(items):
    """Generates a pretty-printed enumeration of all given names.  For
    example, if the list contains ``["a", "b", "c"]``, it yields ``"a, b, and
    c"``.

    :Parameters:
      - `items`: iterable of names to be put into the enumeration

    :type items: iterable of unicode

    :Return:
      human-friendly enumeration of all names

    :rtype: unicode
    """
    items = sorted(unicode(item) for item in items)
    if len(items) > 2:
        return _(", ").join(items[:-1]) + _(", and ") + items[-1]
    elif len(items) == 2:
        return _(" and ").join(items)
    else:
        return "".join(items)


def digest_process(process, user, local_context={}):
    """Convert a process to a process context.  This conversion extracts the
    relevant information of the process and saves it in a form which can easily
    be processed in a template.

    :Parameters:
      - `process`: the process to be digest
      - `user`: current user
      - `local_context`: the local sample context; for example, this is
        relevant to ``SampleSplit``, see ``SampleSplit.get_cache_key``.

    :type process: `models.Process`
    :type user: ``django.contrib.auth.models.User``
    :type local_context: dict mapping str to ``object``

    :Return:
      the process context of the given process

    :rtype: dict mapping str to ``object``
    """
    process = process.actual_instance
    cache_key = process.get_cache_key(user.chantal_user_details.get_data_hash(), local_context)
    cached_context = chantal_common.utils.get_from_cache(cache_key) if cache_key else None
    if cached_context is None:
        process_context = process.get_context_for_user(user, local_context)
        if cache_key:
            keys_list_key = "process-keys:{0}".format(process.pk)
            with chantal_common.utils.cache_key_locked("process-lock:{0}".format(process.pk)):
                keys = cache.get(keys_list_key, [])
                keys.append(cache_key)
                cache.set(keys_list_key, keys, settings.CACHES["default"].get("TIMEOUT", 300) + 10)
                cache.set(cache_key, process_context)
    else:
        cached_context.update(local_context)
        process_context = process.get_context_for_user(user, cached_context)
    return process_context


def get_physical_processes(department=""):
    """Return a list with all registered physical processes, sorted by their name.
    The processes can be filtered with the related department.

    :Parameters:
     - `department`: the related department from the processes

    :type department: str

    :Return:
      all physical processes

    :rtype: sorted list of `models.PhysicalProcess`
    """
    all_physical_processes = [process for process in chantal_common.utils.get_all_models().itervalues()
                              if issubclass(process, models.PhysicalProcess) and not process._meta.abstract == True
                              and not process == models.Deposition]
    if department:
        try:
            department_processes = Department.objects.get(name=department).processes.all()
        except Department.DoesNotExist:
            all_physical_processes = []
        else:
            all_physical_processes = [process for process in all_physical_processes
                                      if ContentType.objects.get_for_model(process)
                                      in department_processes]
    all_physical_processes.sort(key=lambda process: process._meta.verbose_name_plural.lower())
    return all_physical_processes


def restricted_samples_query(user):
    """Returns a ``QuerySet`` which is restricted to samples the names of
    which the given user is allowed to see.  Note that this doesn't mean that
    the user is allowed to see all of the samples themselves necessarily.  It
    is only about the names.  See the `search` view for further information.
    """
    if user.is_staff:
        return models.Sample.objects.all().order_by("name")
    return models.Sample.objects.filter(Q(topic__confidential=False) | Q(topic__members=user) |
                                        Q(currently_responsible_person=user) | Q(clearances__user=user) |
                                        Q(topic__isnull=True)).order_by("name").distinct()


def round(value, digits):
    """Method for rounding a numeric value to a fixed number of significant
    digits.

    :Parameters:
      - `value`: the numeric value
      - `digit`: number of significant digits

    :type value: `float`
    :type digits: `int`

    :Return:
        rounded value

    :rtype: `str`
    """
    try:
        value = float(value)
    except (ValueError, TypeError):
        pass
    else:
        try:
            digits = int(digits)
        except (ValueError, TypeError):
            pass
        else:
            return "{{0:.{0}g}}".format(digits).format(float(value))


def enforce_clearance(user, clearance_processes, destination_user, sample, clearance=None, cutoff_timestamp=None):
    """Unblocks specified processes of a sample for a given user.

    :Parameters:
      - `user`: the user who unblocks the processes
      - `clearance_processes`: all process classes that the destination user
        should be able to see; ``"all"`` means all processes
      - `destination_user`: the user for whom the sample should be unblocked
      - `sample`: the sample to be unblocked
      - `clearance`: The current clearance to which further unblocked processes
        should be added.  This is only used in the internal recursion of this
        routine in order to traverse through sample splits upwards.
      - `cutoff_timestamp`: The timestamp after which no processes in the
        sample should be unblocked.  This is only used in the internal
        recursion of this routine in order to traverse through sample splits
        upwards.  It is a similar algorithm as the one used in
        `samples.views.sample.SamplesAndProcesses`.

    :type user: ``django.contrib.auth.models.User``
    :type clearance_processes: tuple of `models.Process`, or str
    :type destination_user: ``django.contrib.auth.models.User``
    :type sample: `models.Sample`
    :type clearance: `models.Clearance`
    :type cutoff_timestamp: ``datetime.datetime``
    """
    if not clearance:
        clearance, __ = models.Clearance.objects.get_or_create(user=destination_user, sample=sample)
    base_query = sample.processes.filter(finished=True)
    processes = base_query if not cutoff_timestamp else base_query.filter(timestamp__lte=cutoff_timestamp)
    for process in processes:
        process = process.actual_instance
        if isinstance(process, models.Result) and permissions.has_permission_to_view_result_process(user, process):
            clearance.processes.add(process)
        elif isinstance(process, models.PhysicalProcess) and \
                permissions.has_permission_to_view_physical_process(user, process):
            if clearance_processes == "all" or isinstance(process, clearance_processes):
                clearance.processes.add(process)
    split_origin = sample.split_origin
    if split_origin:
        enforce_clearance(user, clearance_processes, destination_user, split_origin.parent, clearance,
                          split_origin.timestamp)


def sorted_users(users):
    """Return a list of users sorted by family name.  In particular, it sorts
    case-insensitively.

    :Parameters:
      - `users`: the users to be sorted; it may also be a ``QuerySet``

    :type users: an iterable of ``django.contrib.auth.models.User``

    :Return:
      the sorted users

    :rtype: list of ``django.contrib.auth.models.User``
    """
    return sorted(users, key=lambda user: user.last_name.lower() if user.last_name else user.username)


def sorted_users_by_first_name(users):
    """Return a list of users sorted by first name.  In particular, it sorts
    case-insensitively.

    :Parameters:
      - `users`: the users to be sorted; it may also be a ``QuerySet``

    :type users: an iterable of ``django.contrib.auth.models.User``

    :Return:
      the sorted users

    :rtype: list of ``django.contrib.auth.models.User``
    """
    return sorted(users, key=lambda user: user.first_name.lower() if user.first_name else user.username)


def table_export(request, data, label_column_heading):
    """Helper function which does almost all work needed for a CSV table
    export view.  This is not a view per se, however, it is called by views,
    which have to do almost nothing anymore by themselves.  See for example
    `sample.export`.

    This function return the data in JSON format if this is requested by the
    ``Accept`` header field in the HTTP request.

    :Parameters:
      - `request`: the current HTTP Request object
      - `data`: the root node of the data tree
      - `label_column_heading`: Description of the very first column with the
        table row headings, see `generate_table_rows`.

    :type request: ``HttpRequest``
    :type data: `DataNode`
    :type label_column_heading: unicode

    :Returns:
      the HTTP response object or a tuple with all needed forms to create the export view

    :rtype: ``HttpResponse`` or tuple of ``django.forms.Form``
    """
    if not data.children:
        # We have no rows (e.g. a result process with only one row), so let's
        # turn the root into the only row.
        root_without_children = copy.copy(data)
        # Remove the label column (the zeroth column)
        root_without_children.descriptive_name = None
        data.children = [root_without_children]
    get_data = request.GET if any(key.startswith("__old_data") for key in request.GET) else None
    requested_mime_type = mimeparse.best_match(["text/csv", "application/json"], request.META.get("HTTP_ACCEPT", "text/csv"))
    data.find_unambiguous_names()
    data.complete_items_in_children()
    column_groups, columns = build_column_group_list(data)
    single_column_group = set([column_groups[0].name]) if len(column_groups) == 1 else []
    table = switch_row_forms = None
    selected_column_groups = set(single_column_group)
    selected_columns = set()
    column_groups_form = ColumnGroupsForm(column_groups, get_data) if not single_column_group else None
    previous_data_form = OldDataForm(get_data)
    if previous_data_form.is_valid():
        previous_column_groups = previous_data_form.cleaned_data["column_groups"]
        previous_columns = previous_data_form.cleaned_data["columns"]
    else:
        previous_column_groups = previous_columns = frozenset()
    columns_form = ColumnsForm(column_groups, columns, previous_column_groups, get_data)
    if single_column_group or column_groups_form.is_valid():
        selected_column_groups = single_column_group or column_groups_form.cleaned_data["column_groups"]
        if columns_form.is_valid():
            selected_columns = columns_form.cleaned_data["columns"]
            label_column = [row.descriptive_name for row in data.children]
            table = generate_table_rows(flatten_tree(data), columns, columns_form.cleaned_data["columns"],
                                        label_column, label_column_heading)
            start_column_index = 1 if any(label_column) else 0
            if not(previous_columns) and selected_columns:
                switch_row_forms = [SwitchRowForm(prefix=str(i), initial={"active": any(row[start_column_index:])})
                                    for i, row in enumerate(table)]
            else:
                switch_row_forms = [SwitchRowForm(get_data, prefix=str(i)) for i in range(len(table))]
            all_switch_row_forms_valid = all([switch_row_form.is_valid() for switch_row_form in switch_row_forms])
            if all_switch_row_forms_valid and \
                    previous_column_groups == selected_column_groups and previous_columns == selected_columns:
                reduced_table = [row for i, row in enumerate(table) if switch_row_forms[i].cleaned_data["active"] or i == 0]
                if requested_mime_type == "application/json":
                    data = [dict((reduced_table[0][i], cell) for i, cell in enumerate(row) if cell)
                            for row in reduced_table[1:]]
                    return chantal_common.utils.respond_in_json(data)
                else:
                    response = HttpResponse(content_type="text/csv; charset=utf-8")
                    response['Content-Disposition'] = \
                        "attachment; filename=chantal--{0}.txt".format(defaultfilters.slugify(data.descriptive_name))
                    writer = UnicodeWriter(response)
                    writer.writerows(reduced_table)
                return response
    if selected_column_groups != previous_column_groups:
        columns_form = ColumnsForm(column_groups, columns, selected_column_groups, initial={"columns": selected_columns})
    old_data_form = OldDataForm(initial={"column_groups": selected_column_groups, "columns": selected_columns})
    return (column_groups_form, columns_form, table, switch_row_forms, old_data_form)


def median(numeric_values):
    """Calculates the median from
    a list of numeric values.

    :Parameters:
     - `numeric_values`: a list with numeric values

    :type numeric_values:  list

    :Retrun:
     The median of the given values

    :rtype: int or float
    """
    if isinstance(numeric_values, (tuple, list)) and len(numeric_values) > 0:
        values = sorted(numeric_values)
        if len(values) % 2 == 1:
            return values[(len(values) + 1) / 2 - 1]
        else:
            lower = values[len(values) / 2 - 1]
            upper = values[len(values) / 2]
            return (float(lower + upper)) / 2


def average(numeric_values):
    """Calculates the average value from
    a list of numeric values.

    :Parameters:
     - `numeric_values`: a list with numeric values

    :type numeric_values:  list

    :Retrun:
     The average value of the given values

    :rtype: float
    """
    if isinstance(numeric_values, (tuple, list)) and len(numeric_values) > 0:
        return sum(map(float, numeric_values)) / len(numeric_values)
