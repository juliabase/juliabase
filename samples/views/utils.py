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


u"""General helper functions for the views.  Try to avoid using it outside the
views package.  All symbols from `shared_utils` are also available here.  So
`shared_utils` should be useful only for the Remote Client.
"""

from __future__ import absolute_import

import re, string, datetime
from django.http import Http404
from django.core.cache import cache
from django.db.models import Q
from django.utils.encoding import iri_to_uri
from django.utils.translation import ugettext as _
from functools import update_wrapper
from django.template import Context, RequestContext
from django.shortcuts import render_to_response
import chantal_common.utils
from samples import models, permissions
from samples.views.shared_utils import *


old_sample_name_pattern = re.compile(r"\d\d[A-Z]-\d{3,4}([-A-Za-z_/][-A-Za-z_/0-9#()]*)?$")
new_sample_name_pattern = re.compile(r"""(\d\d-([A-Z]{2}\d{,2}|[A-Z]{3}\d?|[A-Z]{4})|  # initials of a user
                                         [A-Z]{2}\d\d|[A-Z]{3}\d|[A-Z]{4})             # external operator
                                         -[-A-Za-z_/0-9#()]+$""", re.VERBOSE)
provisional_sample_name_pattern = re.compile(r"\*(?P<id>\d+)$")
def sample_name_format(name):
    u"""Determines which sample name format the given name has.  It doesn't
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
    u"""Lookup a sample by name.  You may also give an alias.  If more than one
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
    u"""Returns ``True`` if the sample name exists in the database.

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


deposition_index_pattern = re.compile(ur"\d{3,4}")

def get_next_deposition_number(letter):
    u"""Find a good next deposition number.  For example, if the last run was
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
    prefix = ur"{0}{1}-".format(datetime.date.today().strftime(u"%y"), letter)
    prefix_length = len(prefix)
    pattern_string = ur"^{0}[0-9]+".format(re.escape(prefix))
    deposition_numbers = \
        models.Deposition.objects.filter(number__regex=pattern_string).values_list("number", flat=True).iterator()
    numbers = [int(deposition_index_pattern.match(deposition_number[prefix_length:]).group())
               for deposition_number in deposition_numbers]
    next_number = max(numbers) + 1 if numbers else 1
    return prefix + u"{0:03}".format(next_number)


class AmbiguityException(Exception):
    u"""Exception if a sample lookup leads to more than one matching alias
    (remember that alias names needn't be unique).  It is raised in
    `lookup_sample` and typically caught in Chantal's own middleware.
    """

    def __init__(self, sample_name, samples):
        self.sample_name, self.samples = sample_name, samples


def lookup_sample(sample_name, user, with_clearance=False):
    u"""Looks up the ``sample_name`` in the database (also among the aliases),
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
        raise Http404(u"Sample {name} could not be found (neither as an alias).".format(name=sample_name))
    if isinstance(sample, list):
        raise AmbiguityException(sample_name, sample)
    if with_clearance:
        clearance = permissions.get_sample_clearance(user, sample)
        return sample, clearance
    else:
        permissions.assert_can_fully_view_sample(user, sample)
        return sample


def convert_id_to_int(process_id):
    u"""If the user gives a process ID via the browser, it must be converted to
    an integer because this is what's stored in the database.  (Well, actually
    SQL gives a string, too, but that's beside the point.)  This routine
    converts it to a real integer and tests also for validity (not for
    availability in the database).

    FixMe: This should be replaced with a function the gets the database model
    class as an additional parameter and returns the found object.

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
        raise Http404(u"Invalid ID: “{id}”".format(id=process_id))


# FixMe: Possibly the whole function is superfluous because there is
# "request.GET".
def parse_query_string(request):
    u"""Parses an URL query string.

    :Parameters:
      - `request`: the current HTTP request object

    :type request: ``HttpRequest``

    :Return:
      All found key/value pairs in the query string.  The URL escaping is resolved.

    :rtype: dict mapping unicode to unicode
    """
    # FixMe: Use urlparse.parse_qs() for this
    def decode(string):
        string = string.replace("+", " ")
        string = re.sub('%(..)', lambda match: chr(int(match.group(1), 16)), string)
        return string.decode("utf-8")
    query_string = request.META["QUERY_STRING"] or u""
    items = [item.split("=", 1) for item in query_string.split("&")]
    result = []
    for item in items:
        if len(item) == 1:
            item.append(u"")
        result.append((decode(item[0]), decode(item[1])))
    return dict(result)


def successful_response(request, success_report=None, view=None, kwargs={}, query_string=u"", forced=False,
                        json_response=True):
    u"""After a POST request was successfully processed, there is typically a
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
    u"""Remove the given samples from the user's MySamples list

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
    u"""Helper class to pass sample series data to the main menu template.
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
        u"""Adds a sample to this sample series view.

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
    u"""Class that represents one topic which contains samples and sample
    series, used for `build_structured_sample_list`.

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

    def __init__(self, topic_name):
        self.topic_name = topic_name
        self.samples = []
        self.sample_series = []

    def sort_sample_series(self):
        self.sample_series.sort(key=lambda series: series.timestamp, reverse=True)


def build_structured_sample_list(samples, user):
    u"""Generate a nested datastructure which contains the given samples in a
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
    for sample in sorted(set(samples), key=lambda sample: sample.name):
        containing_series = sample.series.all()
        if containing_series:
            for series in containing_series:
                if series.name not in structured_series:
                    structured_series[series.name] = StructuredSeries(series)
                    topicname = series.topic.name
                    if topicname not in structured_topics:
                        structured_topics[topicname] = StructuredTopic(series.topic.get_name_for_user(user))
                    structured_topics[topicname].sample_series.append(structured_series[series.name])
                structured_series[series.name].append(sample)
        elif sample.topic:
            topicname = sample.topic.name
            if topicname not in structured_topics:
                structured_topics[topicname] = StructuredTopic(sample.topic.get_name_for_user(user))
            structured_topics[topicname].samples.append(sample)
        else:
            topicless_samples.append(sample)
    structured_topics = sorted(structured_topics.itervalues(),
                                 key=lambda structured_topic: structured_topic.topic_name)
    for structured_topic in structured_topics:
        structured_topic.sort_sample_series()
    return structured_topics, topicless_samples


def extract_preset_sample(request):
    u"""Extract a sample from a query string.  All physical processes as well
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
    query_string_dict = parse_query_string(request)
    if "sample" in query_string_dict:
        try:
            return models.Sample.objects.get(name=query_string_dict["sample"])
        except models.Sample.DoesNotExist:
            pass


def format_enumeration(items):
    u"""Generates a pretty-printed enumeration of all given names.  For
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
        return _(u", ").join(items[:-1]) + _(u", and ") + items[-1]
    elif len(items) == 2:
        return _(u" and ").join(items)
    else:
        return u"".join(items)


def digest_process(process, user, local_context={}):
    u"""Convert a process to a process context.  This conversion extracts the
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
    cache_key = process.get_cache_key(models.get_user_settings_hash(user), local_context)
    cached_context = cache.get(cache_key) if cache_key else None
    if cached_context is None:
        process_context = process.get_context_for_user(user, local_context)
        if cache_key:
            cache.set(cache_key, process_context)
            process.append_cache_key(cache_key)
    else:
        cached_context.update(local_context)
        process_context = process.get_context_for_user(user, cached_context)
    return process_context


def get_physical_processes():
    u"""Return a list with all registered physical processes, sorted by their name.

    :Return:
      all physical processes

    :rtype: sorted list of `models.PhysicalProcess`
    """
    all_physical_processes = [process for process in chantal_common.utils.get_all_models().itervalues()
                              if issubclass(process, models.PhysicalProcess)]
    all_physical_processes.sort(key=lambda process: process._meta.verbose_name_plural.lower())
    return all_physical_processes


def restricted_samples_query(user):
    u"""Returns a ``QuerySet`` which is restricted to samples the names of
    which the given user is allowed to see.  Note that this doesn't mean that
    the user is allowed to see all of the samples themselves necessary.  It is
    only about the names.  See the `search` view for further information.
    """
    if user.is_staff:
        return models.Sample.objects.all()
    return models.Sample.objects.filter(Q(topic__confidential=False) | Q(topic__members=user) |
                                        Q(currently_responsible_person=user) | Q(clearances__user=user) |
                                        Q(topic__isnull=True)).distinct()

def round(value, digits):
    u"""Method for rounding a numeric value to a fixed number of significant
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
    return "{{0:.{0}g}}".format(digits).format(float(value))
