#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""General helper functions for the views.  Try to avoid using it outside the
views package.  All symbols from `shared_utils` are also available here.  So
`shared_utils` should be useful only for the Remote Client.
"""

from __future__ import absolute_import

import re, string, datetime, json, hashlib
from django.http import Http404, HttpResponse
from django.utils.encoding import iri_to_uri
from django.utils.translation import ugettext as _
from django.core.cache import cache
from functools import update_wrapper
from django.template import Context, RequestContext
from django.template.loader import render_to_string
from django.shortcuts import render_to_response
import django.core.urlresolvers
import chantal_common.utils
from samples import models, permissions
from samples.views.shared_utils import *


old_sample_name_pattern = re.compile(r"\d\d[BVHLCS]-\d{3,4}([-A-Za-z_/][-A-Za-z_/0-9#]*)?$")
new_sample_name_pattern = re.compile(r"\d\d-([A-Z]{2}\d{,2}|[A-Z]{3}\d?|[A-Z]{4})-[-A-Za-z_/0-9#]+$")
provisional_sample_name_pattern = re.compile(r"\*(?P<id>\d+)")
def sample_name_format(name):
    u"""Determines which sample name format the given name has.

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


def get_session_settings_hash(user):
    hash_ = hashlib.sha1()
    hash_.update(user.chantal_user_details.language)
    return hash_.hexdigest()


class ResultContext(object):
    u"""Contains all info that result processes must know in order to render
    themselves as HTML.  It retrieves all processes, resolve the polymorphism
    (see `models.find_actual_instance`), and executes the proper template with
    the proper context dictionary in order to het HTML fragments.  These
    fragments are then collected in a list structure together with other info.

    This list is the final output of this class.  It can be passed to a
    template for creating the whole history of a sample or sample series.

    ``ResultContext`` is specialised in sample *series*, though.  However, it
    is expanded by the child class `ProcessContext`, which is about rendering
    histories of samples themselves.
    """

    def __init__(self, user, sample_series):
        u"""Class constructor.

        :Parameters:
          - `user`: the user that wants to see all the generated HTML
          - `sample_series`: the sample series the history of which is about to
            be generated

        :type user: ``django.contrib.auth.models.User``
        :type sample_series: `models.SampleSeries`
        """
        self.sample_series = sample_series
        self.user = user

    def get_template_context(self, process):
        u"""Generate the complete context that the template of the process
        needs.  The process itself is always part of it; further key/value
        pairs may be added by the process class'
        ``get_additional_template_context`` method – which in turn gets this
        ``ResultContext`` instance as a parameter.

        :Parameters:
          - `process`: the process for which the context dictionary should be
            generated.

        :type process: `models.Process`

        :Return:
          the context dictionary to be passed to the template of this process.

        :rtype: dict
        """
        context_dict = {"process": process}
        if hasattr(process, "get_additional_template_context"):
            context_dict.update(process.get_additional_template_context(self))
        return context_dict

    def digest_process(self, process):
        u"""Return one item for the list of processes, which is later passed to
        the main template for the sample's/sample series' history.  Each item
        is a dictionary which always contains ``"name"``, ``"operator"``,
        ``"timestamp"``, and ``"html_body"``.  The latter contains the result
        of the process rendering.  Additionally, ``"edit_url"``,
        ``"export_url"``, ``"duplicate_url"``, and ``"resplit_url"`` are
        inserted, if the ``get_additional_template_context`` of the process had
        provided them.

        All these things are used in the “outer” part of the history rendering.
        The inner part is the value of ``"html_body"``.

        :Parameters:
          - `process`: the process for which the element for the processes list
            should be generated.

        :type process: `models.Process`

        :Return:
          everything the show-history template needs to know for displaying the
          process.

        :rtype: dict
        """
        process = process.find_actual_instance()
        name = unicode(process._meta.verbose_name) if not isinstance(process, models.Result) else process.title
        template_context = self.get_template_context(process)
        cache_key = "{0}-{1}".format(process.pk, get_session_settings_hash(self.user))
        html_body = cache.get(cache_key)
        if html_body is None:
            html_body = render_to_string("samples/show_" + camel_case_to_underscores(process.__class__.__name__) + ".html",
                                         context_instance=Context(template_context))
            cache.set(cache_key, html_body)
            process.append_cache_key(cache_key)
        context_dict = {"name": name[:1].upper()+name[1:], "operator": process.external_operator or process.operator,
                        "timestamp": process.timestamp, "timestamp_inaccuracy": process.timestamp_inaccuracy,
                        "html_body": html_body}
        for key in ["edit_url", "export_url", "duplicate_url", "resplit_url"]:
            if key in template_context:
                context_dict[key] = template_context[key]
        return context_dict

    def collect_processes(self):
        u"""Make a list of all result processes for the sample series.

        :Return:
          a list with all result processes of this sample in chronological
          order.  Every list item is a dictionary with the information
          described in `digest_process`.

        :rtype: list of dict
        """
        results = []
        for result in self.sample_series.results.all():
            results.append(self.digest_process(result))
        return results


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
    prefix = ur"%s%s-" % (datetime.date.today().strftime(u"%y"), letter)
    prefix_length = len(prefix)
    pattern_string = ur"^%s[0-9]+" % re.escape(prefix)
    deposition_numbers = \
        models.Deposition.objects.filter(number__regex=pattern_string).values_list("number", flat=True).iterator()
    try:
        next_number = max(int(deposition_number[prefix_length:]) for deposition_number in deposition_numbers) + 1
    except ValueError, e:
        if e.message != "max() arg is an empty sequence":
            raise
        next_number = 1
    return prefix + u"%03d" % next_number


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
        sample_name = "*%05d" % int(match.group("id"))
    sample = get_sample(sample_name)
    if not sample:
        raise Http404(_(u"Sample %s could not be found (neither as an alias).") % sample_name)
    if isinstance(sample, list):
        raise AmbiguityException(sample_name, sample)
    if with_clearance:
        clearance = None
        try:
            permissions.assert_can_fully_view_sample(user, sample)
        except permissions.PermissionError as error:
            try:
                clearance = models.Clearance.objects.get(user=user, sample=sample)
            except models.Clearance.DoesNotExist:
                raise error
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
        raise Http404(u"Invalid ID: “%s”" % process_id)


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
                        remote_client_response=True):
    u"""After a POST request was successfully processed, there is typically a
    redirect to another page – maybe the main menu, or the page from where the
    add/edit request was started.

    The latter is appended to the URL as a query string with the ``next`` key,
    e.g.::

        /chantal/6-chamber_deposition/08B410/edit/?next=/chantal/samples/08B410a

    This routine generated the proper ``HttpResponse`` object that contains the
    redirection.  It always has HTTP status code 303 (“see other”).

    If the request came from the Chantal Remote Client, the response is a
    pickled ``remote_client_response``.  (Normally, a simple ``True``.)

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
      - `remote_client_response`: object which is to be sent as a pickled
        response to the remote client; defaults to ``True``.

    :type request: ``HttpRequest``
    :type success_report: unicode
    :type view: str or function
    :type kwargs: dict
    :type query_string: unicode
    :type forced: bool
    :type remote_client_response: ``object``

    :Return:
      the HTTP response object to be returned to the view's caller

    :rtype: ``HttpResponse``
    """
    if is_remote_client(request):
        return respond_to_remote_client(remote_client_response)
    return chantal_common.utils.successful_response(request, success_report, view or "samples.views.main.main_menu", kwargs,
                                                    query_string, forced)


def is_remote_client(request):
    u"""Tests whether the current request was not done by an ordinary browser
    like Firefox or Google Chrome but by the Chantal Remote Client.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      whether the request was made with the Remote Client

    :rtype: bool
    """
    return request.META.get("HTTP_USER_AGENT", "").startswith("Chantal-Remote")


def respond_to_remote_client(value):
    u"""The communication with the Chantal Remote Client should be done without
    generating HTML pages in order to have better performance.  Thus, all
    responses are Python objects, serialised in JSON notation.

    This views that should be accessed by both the Remote Client and the normal
    users should distinguish between both by using `is_remote_client`.

    :Parameters:
      - `value`: the data to be sent back to the remote client.

    :type value: ``object`` (an arbitrary Python object)

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return HttpResponse(json.dumps(value), content_type="application/json; charset=ascii")


def remove_samples_from_my_samples(samples, user_details):
    u"""Remove the given samples from the user's MySamples list

    :Parameters:
      - `samples`: the samples to be removed.  FixMe: How does it react if a
        sample hasn't been in ``my_samples``?
      - `user_details`: details of the user whose MySamples list is affected

    :type samples: list of `models.Sample`
    :type user_details: `models.UserDetails`
    """
    for sample in samples:
        user_details.my_samples.remove(sample)


# FixMe: Assure that every user has a UserDetails by using signals.  Then,
# remove this function and access the user details directly.

def get_profile(user):
    u"""Retrieve the user details for the given user.  If this user hasn't yet
    any record in the ``UserDetails`` table, create one with sane defaults and
    return it.

    :Parameters:
      - `user`: the user the profile of which should be fetched

    :type user: ``django.contrib.auth.models.User``

    :Return:
      the user details (aka profile) for the user

    :rtype: `models.UserDetails`
    """
    try:
        return user.samples_user_details
    except models.UserDetails.DoesNotExist:
        # FixMe: Should be fleshed out with e.g. FZJ homepage data
        user_details = models.UserDetails(user=user)
        user_details.save()
        return user_details


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

    :ivar topic: the underlying Chantal topic which is represented by this
      instance.

    :ivar samples: the samples of this topic which belong to the “My Samples”
      of the user but which don't belong to any sample series.

    :ivar sample_series: the sample series which belong to this topic and
      which contain “My Samples” of the user.  They themselves contain a list
      of their samples.  See `StructuredSeries` for further information.

    :type topic: ``chantal_common.models.Topic``
    :type samples: list of `models.Sample`
    :type sample_series: list of `StructuredSeries`
    """

    def __init__(self, topic):
        self.topic = topic
        self.samples = []
        self.sample_series = []

    def sort_sample_series(self):
        self.sample_series.sort(key=lambda series: series.timestamp, reverse=True)


def build_structured_sample_list(samples):
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

    :type samples: list of `models.Sample`

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
                        structured_topics[topicname] = StructuredTopic(series.topic)
                    structured_topics[topicname].sample_series.append(structured_series[series.name])
                structured_series[series.name].append(sample)
        elif sample.topic:
            topicname = sample.topic.name
            if topicname not in structured_topics:
                structured_topics[topicname] = StructuredTopic(sample.topic)
            structured_topics[topicname].samples.append(sample)
        else:
            topicless_samples.append(sample)
    structured_topics = sorted(structured_topics.itervalues(),
                                 key=lambda structured_topic: structured_topic.topic.name)
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
