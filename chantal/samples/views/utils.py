#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""General helper functions for the views.  Try to avoid using it outside the
views package.
"""

import re, string, copy, datetime, pickle
from django.http import Http404, HttpResponse
from django.utils.encoding import iri_to_uri
from django.utils.translation import ugettext as _
from functools import update_wrapper
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response
import django.core.urlresolvers
from chantal.samples import models, permissions
from chantal.samples.views.shared_utils import *

class HttpResponseSeeOther(HttpResponse):
    u"""Response class for HTTP 303 redirects.  Unfortunately, Django does the
    same wrong thing as most other web frameworks: it knows only one type of
    redirect, with the HTTP status code 302.  However, this is very often not
    desirable.  In Chantal, we've frequently the use case where an HTTP POST
    request was successful, and we want to redirect the user back to the main
    page, for example.

    This must be done with status code 303, and therefore, this class exists.
    It can simply be used as a drop-in replacement of HttpResponseRedirect.
    """
    status_code = 303
    def __init__(self, redirect_to):
        super(HttpResponseSeeOther, self).__init__()
        self["Location"] = iri_to_uri(redirect_to)

old_sample_name_pattern = re.compile(r"\d\d[BVHLCS]-\d{3,4}([-A-Za-z_/][-A-Za-z_/0-9]*)?$")
new_sample_name_pattern = re.compile(r"\d\d-([A-Z]{2}\d{,2}|[A-Z]{3}\d?|[A-Z]{4})-[-A-Za-z_/0-9]+$")
provisional_sample_name_pattern = re.compile(r"\*\d+")
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

class _AddHelpLink(object):
    u"""Internal helper class in order to realise the `help_link` function
    decorator.
    """
    def __init__(self, original_view_function, help_link):
        self.original_view_function = original_view_function
        self.help_link = help_link
        update_wrapper(self, original_view_function)
    def __call__(self, request, *args, **kwargs):
        request.chantal_help_link = self.help_link
        return self.original_view_function(request, *args, **kwargs)
    
def help_link(link):
    u"""Function decorator for views functions to set a help link for the view.
    The help link is embedded into the top line in the layout, see the template
    ``base.html``.  Currently, it is prepended with ``"/trac/chantal/wiki/"``.

    :Parameters:
      - `link`: the relative URL to the help page.

    :type link: str
    """
    def decorate(original_view_function):
        return _AddHelpLink(original_view_function, link)
    return decorate

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
    return (models.Sample.objects.filter(name=sample_name).count() or
            models.SampleAlias.objects.filter(name=sample_name).count())

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
    if models.Sample.objects.filter(name=sample_name).count():
        return sample_name
    try:
        sample_alias = models.SampleAlias.objects.get(name=sample_name)
    except models.SampleAlias.DoesNotExist:
        return
    else:
        return sample_alias.sample.name

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
        u"""
        :Parameters:
          - `user`: the user that wants to see all the generated HTML
          - `sample_series`: the sample series the history of which is about to
            be generated

        :type user: django.contrib.auth.models.User
        :type sample_series: `models.SampleSeries`
        """
        self.sample_series = sample_series
        self.user = user
    def get_template_context(self, process):
        u"""Generate the complete context that the template of the process
        needs.  The process itself is always part of ot; further key/value
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
        of the process rendering.  Additionally, ``"edit_url"`` and
        ``"duplicate_url"`` are inserted, if the
        ``get_additional_template_context`` of the process had provided them.

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
        template = loader.get_template("show_" + camel_case_to_underscores(process.__class__.__name__) + ".html")
        name = unicode(process._meta.verbose_name) if not isinstance(process, models.Result) else process.title
        template_context = self.get_template_context(process)
        context_dict = {"name": name[:1].upper()+name[1:], "operator": process.operator,
                        "timestamp": process.timestamp, "timestamp_inaccuracy": process.timestamp_inaccuracy,
                        "html_body": template.render(Context(template_context))}
        for key in ["edit_url", "duplicate_url"]:
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
            assert result.find_actual_instance().__class__ in models.result_process_classes
            results.append(self.digest_process(result))
        return results

class ProcessContext(ResultContext):
    u"""Contains all info that processes must know in order to render
    themselves as HTML.  It does the same as the parent class `ResultContext`
    (see there for full information), however, it extends its functionality a
    little bit for being useful for *samples* instead of sample series.

    :ivar original_sample: the sample for which the history is about to be
      generated

    :ivar current_sample: the sample the processes of which are *currently*
      collected an processed.  This is an ancestor of `original_sample`.  In
      other words, `original_sample` is a direct or indirect split piece of
      ``current_sample``.

    :ivar cutoff_timestamp: the timestamp of the split of `current_sample`
      which generated the (ancestor of) the `original_sample`.  Thus, processes
      of `current_sample` that came *after* the cutoff timestamp must not be
      included into the history.
    """
    def __init__(self, user, original_sample=None):
        u"""
        :Parameters:
          - `user`: the user that wants to see all the generated HTML
          - `original_sample`: the sample the history of which is about to be
            generated

        :type user: django.contrib.auth.models.User
        :type original_sample: `models.Sample`
        """
        self.original_sample = self.current_sample = original_sample
        self.latest_descendant = None
        self.user = user
        self.cutoff_timestamp = None
    def split(self, split):
        u"""Generate a copy of this `ProcessContext` for the parent of the
        current sample.

        :Parameters:
          - `split`: the split process

        :type split: `models.SampleSplit`

        :Return:
          a new process context for collecting the processes of the parent in
          order to add them to the complete history of the `original_sample`.

        :rtype: `ProcessContext`
        """
        result = copy.copy(self)
        result.current_sample = split.parent
        result.latest_descendant = self.current_sample
        result.cutoff_timestamp = split.timestamp
        return result
    def get_processes(self):
        u"""Get all relevant processes of the `current_sample`.

        :Return:
          all processes of the `current_sample` that must be included into the
          history of `original_sample`, i.e. up to `cutoff_timestamp`.

        :rtype: list of `models.Process`
        """
        if self.cutoff_timestamp is None:
            return self.current_sample.processes.all()
        else:
            return self.current_sample.processes.filter(timestamp__lte=self.cutoff_timestamp)
    def collect_processes(self):
        u"""Make a list of all processes for `current_sample`.  This routine is
        called recursively in order to resolve all upstream sample splits,
        i.e. it also collects all processes of ancestors that the current
        sample has experienced, too.

        :Return:
          a list with all result processes of this sample in chronological
          order.  Every list item is a dictionary with the information
          described in `digest_process`.

        :rtype: list of dict
        """
        processes = []
        split_origin = self.current_sample.split_origin
        if split_origin:
            processes.extend(self.split(split_origin).collect_processes())
        for process in self.get_processes():
            processes.append(self.digest_process(process))
        return processes

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
    prefix = ur"%02d%s-" % (datetime.date.today().year % 100, letter)
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

def lookup_sample(sample_name, request):
    u"""Looks up the ``sample_name`` in the database (also among the aliases),
    and returns that sample if it was found *and* the current user is allowed
    to view it.  If not, it raises an exception.
    
    :Parameters:
      - `sample_name`: name of the sample
      - `request`: the HTTP request object

    :type sample_name: unicode
    :type request: ``HttpRequest``

    :Return:
      the single found sample

    :rtype: `models.Sample`

    :Exceptions:
      - `Http404`: if the sample name could not be found
      - `AmbiguityException`: if more than one matching alias was found
      - `permissions.PermissionError`: if the user is not allowed to view the
        sample
    """
    sample = get_sample(sample_name)
    if not sample:
        raise Http404(_(u"Sample %s could not be found (neither as an alias).") % sample_name)
    if isinstance(sample, list):
        raise AmbiguityException(sample_name, sample)
    permissions.assert_can_view_sample(request.user, sample)
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
        raise Http404

def parse_query_string(request):
    u"""Parses an URL query string.

    :Parameters:
      - `request`: the current HTTP request object

    :type request: ``HttpRequest``

    :Return:
      All found key/value pairs in the query string.  The URL escaping is resolved.

    :rtype: dict mapping unicode to unicode
    """
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
    redirection.  It always has HTPP status code 303 (“see other”).

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
    if success_report:
        request.session["success_report"] = success_report
    next_url = parse_query_string(request).get("next")
    if next_url is not None and not forced:
        return HttpResponseSeeOther(next_url)
    if query_string:
        query_string = "?" + query_string
    return HttpResponseSeeOther(django.core.urlresolvers.reverse(view or "samples.views.main.main_menu", kwargs=kwargs)
                                + query_string)

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
    responses are Python objects, serialised by the “pickle” module.

    This views that should be accessed by both the Remote Client and the normal
    users should distinguish between both by using `is_remote_client`.

    :Parameters:
      - `value`: the data to be sent back to the remote client.

    :type value: ``object`` (an arbitrary Python object)

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return HttpResponse(pickle.dumps(value), content_type="text/x-python-pickle; charset=ascii")

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
        return user.get_profile()
    except models.UserDetails.DoesNotExist:
        # FixMe: Should be fleshed out with e.g. FZJ homepage data
        user_details = models.UserDetails(user=user)
        user_details.save()
        return user_details
