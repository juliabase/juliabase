#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""General helper functions for the views.  Try to avoid using it outside the
views package.
"""

import re, string, copy, datetime, hashlib, pickle
from django.forms.util import ErrorList, ValidationError
from django.http import QueryDict, Http404, HttpResponse
from django.utils.encoding import iri_to_uri
from django.utils.translation import ugettext as _, ugettext_lazy
from functools import update_wrapper
from chantal.samples import models
from django.forms import ModelForm, ModelChoiceField
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response
from django.conf import settings
from django.utils.http import urlquote
import django.core.urlresolvers

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

class HttpResponseUnauthorized(HttpResponse):
    u"""The response sent back in case of a permission error.  This is another
    missing response class in Dango.  I have no clue why they leave out such
    trivial code.

    So far, it is only used in `main.permission_error`.
    """
    status_code = 401

class DataModelForm(ModelForm):
    u"""Model form class for accessing the data fields of a bound form, whether
    it is valid or not.  This is sometimes useful if you want to do structural
    changes to the forms in a view, and you don't want to do that only if the
    data the user has given is totally valid.

    Actually, using this class is bad style nevertheless.  It is used in the
    module `six_chamber_deposition`, however, for upcoming process, it should
    be avoided and extra forms used instead.
    """
    def uncleaned_data(self, fieldname):
        u"""Get the field value of a *bound* form, even if it is invalid.

        :Parameters:
          - `fieldname`: name (=key) of the field

        :type fieldname: str

        :Return:
          the value of the field

        :rtype: unicode
        """
        return self.data.get(self.prefix + "-" + fieldname)

class OperatorChoiceField(ModelChoiceField):
    u"""A specialised ``ModelChoiceField`` for displaying users in a choice
    field in forms.  It's only purpose is that you don't see the dull username
    then, but the beautiful full name of the user.
    """
    def label_from_instance(self, operator):
        return models.get_really_full_name(operator)

time_pattern = re.compile(r"^\s*((?P<H>\d{1,3}):)?(?P<M>\d{1,2}):(?P<S>\d{1,2})\s*$")
u"""Standard regular expression pattern for time durations in Chantal:
HH:MM:SS, where hours can also be 3-digit and are optional."""
def clean_time_field(value):
    u"""General helper function for use in the ``clean_...`` methods in forms.
    It tests whether the time format is correct, and normalises the duration so
    that minutes and seconds are 2-digit, and leading zeros are eliminated from
    the hours.

    :Parameters:
      - `value`: the value input by the user.  Usually this is the result of a
        ``cleaned_data[...]`` call.

    :type value: str

    :Return:
      the normalised time

    :rtype: str

    :Exceptions:
      - `ValidationError`: if the value given was not a valid duration time.
    """
    if not value:
        return ""
    match = time_pattern.match(value)
    if not match:
        raise ValidationError(_(u"Time must be given in the form HH:MM:SS."))
    hours, minutes, seconds = match.group("H"), int(match.group("M")), int(match.group("S"))
    hours = int(hours) if hours is not None else 0
    if minutes >= 60 or seconds >= 60:
        raise ValidationError(_(u"Minutes and seconds must be smaller than 60."))
    if not hours:
        return "%d:%02d" % (minutes, seconds)
    else:
        return "%d:%02d:%02d" % (hours, minutes, seconds)

quantity_pattern = re.compile(ur"^\s*(?P<number>[-+]?\d+(\.\d+)?(e[-+]?\d+)?)\s*(?P<unit>[a-uA-Zµ]+)\s*$")
u"""Regular expression pattern for valid physical quantities."""
def clean_quantity_field(value, units):
    u"""General helper function for use in the ``clean_...`` methods in forms.
    It tests whether the format of the physical quantity is correct, and
    normalises it so that it only contains decimal points (no commas), a proper
    »µ«, and exactly one space sign between value and unit.

    :Parameters:
      - `value`: the value input by the user.  Usually this is the result of a
        ``cleaned_data[...]`` call.

    :type value: str

    :Return:
      the normalised physical quantity

    :rtype: str

    :Exceptions:
      - `ValidationError`: if the value given was not a valid physical
        quantity.
    """
    if not value:
        return ""
    value = unicode(value).replace(",", ".").replace(u"μ", u"µ")  # No, these µ are not the same!
    match = quantity_pattern.match(value)
    if not match:
        raise ValidationError(_(u"Must be a physical quantity with number and unit."))
    original_unit = match.group("unit").lower()
    for unit in units:
        if unit.lower() == original_unit.lower():
            break
    else:
        raise ValidationError(_(u"The unit is invalid.  Valid units are: %s")%", ".join(units))
    return match.group("number") + " " + unit
    
def int_or_zero(number):
    u"""
    :Parameters:
      - `number`: a string that is supposed to contain an integer number

    :type number: str or unicode

    :Return:
      the ``int`` representation of ``number``, or 0 if it didn't represent a
      valid integer number

    :rtype: int
    """
    try:
        return int(number)
    except ValueError:
        return 0
    except TypeError:
        if number is None:
            return 0

def append_error(form, error_message, fieldname="__all__"):
    u"""This function is called if a validation error is found in form data
    which cannot be found by the ``is_valid`` method itself.  The reason is
    very simple: For many types of invalid data, you must take other forms in
    the same view into account.

    See, for example, `split_after_process.is_referentially_valid`.

    :Parameters:
      - `form`: the form to which the erroneous field belongs
      - `error_message`: the message to be presented to the user
      - `fieldname`: the name of the field that triggered the validation
        error.  It is optional, and if not given, the error is considered an
        error of the form as a whole.

    :type form: ``forms.Form`` or ``forms.ModelForm``.
    :type fieldname: str
    :type error_message: unicode
    """
    form._errors.setdefault(fieldname, ErrorList()).append(error_message)

class _PermissionCheck(object):
    u"""Internal helper class in order to realise the `check_permission`
    function decorator.
    """
    def __init__(self, original_view_function, permissions):
        self.original_view_function = original_view_function
        try:
            self.permissions = set("samples." + permission for permission in permissions)
        except TypeError:
            self.permissions = set(["samples." + permissions])
        update_wrapper(self, original_view_function)
    def __call__(self, request, *args, **kwargs):
        if any(request.user.has_perm(permission) for permission in self.permissions):
            return self.original_view_function(request, *args, **kwargs)
        return utils.HttpResponseSeeOther("permission_error")
    
def check_permission(permissions):
    u"""Function decorator for views functions to detect whether the user has a
    certain permission.  If the user doesn't have this permission, he is
    redirected to the “permission error” page.  If more than one permission is
    given, he must have at least one of them.

    :Parameters:
      - `permissions`: the permission(s) the user has to have.

    :type permissions: str or list of str
    """
    # If more than one permission is given, any of them would unlock the view.
    def decorate(original_view_function):
        return _PermissionCheck(original_view_function, permissions)
    return decorate

class _AddHelpLink(object):
    u"""Internal helper class in order to realise the `help_link` function
    decorator.
    """
    def __init__(self, original_view_function, help_link):
        self.original_view_function = original_view_function
        self.help_link = help_link
        update_wrapper(self, original_view_function)
    def __call__(self, request, *args, **kwargs):
        request.session["help_link"] = self.help_link
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

level0_pattern = re.compile(ur"(?P<level0_index>\d+)-(?P<id>.+)")
level1_pattern = re.compile(ur"(?P<level0_index>\d+)_(?P<level1_index>\d+)-(?P<id>.+)")
def normalize_prefixes(post_data):
    u"""Manipulates the prefixes of POST data keys for bringing then in
    consecutive order.  It only works for at most two-level numeric prefixes,
    which is sufficient for most purposes.  For example, in the 6-chamber
    deposition view, top-level is the layer index, and second-level is the
    channel index.

    The format of prefixes must be "1" for layers, and "1_1" for channels.

    By deleting layers or channels, the indeces might be sparse, so this
    routine re-indexes everything so that the gaps are filled.

    :Parameters:
      - `post_data`: the POST data as returned by ``request.POST``.

    :type post_data: ``QueryDict``

    :Return:
      the normalised POST data, the number of top-level prefixes, and a list
      with the number of all second-level prefixes.

    :rtype: ``QueryDict``, int, list of int
    """
    level0_indices = set()
    level1_indices = {}
    digested_post_data = {}
    for key in post_data:
        match = level0_pattern.match(key)
        if match:
            level0_index = int(match.group("level0_index"))
            level0_indices.add(level0_index)
            level1_indices.setdefault(level0_index, set())
            digested_post_data[(level0_index, match.group("id"))] = post_data.getlist(key)
        else:
            match = level1_pattern.match(key)
            if match:
                level0_index, level1_index = int(match.group("level0_index")), int(match.group("level1_index"))
                level1_indices.setdefault(level0_index, set()).add(level1_index)
                digested_post_data[(level1_index, level0_index, match.group("id"))] = post_data.getlist(key)
            else:
                digested_post_data[key] = post_data.getlist(key)
    level0_indices = sorted(level0_indices)
    normalization_necessary = level0_indices and level0_indices[-1] != len(level0_indices) - 1
    for key, value in level1_indices.iteritems():
        level1_indices[key] = sorted(value)
        normalization_necessary = normalization_necessary or (
            level1_indices[key] and level1_indices[key][-1] != len(level1_indices[key]) - 1)
    if normalization_necessary:
        new_post_data = QueryDict("").copy()
        for key, value in digested_post_data.iteritems():
            if isinstance(key, basestring):
                new_post_data.setlist(key, value)
            elif len(key) == 2:
                new_post_data.setlist("%d-%s" % (level0_indices.index(key[0]), key[1]), value)
            else:
                new_level0_index = level0_indices.index(key[1])
                new_post_data.setlist("%d_%d-%s" % (new_level0_index, level1_indices[key[1]].index(key[0]), key[2]), value)
    else:
        new_post_data = post_data
    return new_post_data, len(level0_indices), [len(level1_indices[i]) for i in level0_indices]

def get_my_layers(user_details, deposition_model):
    u"""Parse the ``my_layers`` string of a user and convert it to valid input
    for a form selection field (``ChoiceField``).  Notethat the user is not
    forced to select a layer.  Instead, the result always includes a “nothing
    selected” option.

    :Parameters:
      - `user_details`: the details of the current user
      - `deposition_model`: the model class for which “MyLayers” should be
        generated

    :type user_details: `models.UserDetails`
    :type deposition_model: class, descendent of `models.Deposition`

    :Return:
      a list ready-for-use as the ``choices`` attribute of a ``ChoiceField``.
      The MyLayer IDs are given as strings in the form “<deposition id>-<layer
      number>”.

    :rtype: list of (MyLayer-ID, nickname)
    """
    if not user_details.my_layers:
        return []
    items = [item.split(":", 1) for item in user_details.my_layers.split(",")]
    items = [(item[0].strip(),) + tuple(item[1].rsplit("-", 1)) for item in items]
    items = [(item[0], int(item[1]), int(item[2])) for item in items]
    fitting_items = [(u"", u"---------")]
    for nickname, deposition_id, layer_number in items:
        try:
            deposition = deposition_model.objects.get(pk=deposition_id)
        except deposition_model.DoesNotExist:
            continue
        try:
            layer = deposition.layers.get(number=layer_number)
        except:
            continue
        # FixMe: Maybe it is possible to avoid serialising the deposition ID
        # and layer number, so that change_structure() doesn't have to re-parse
        # it.  In other words: Maybe the first element of the tuples can be of
        # any type and needn't be strings.
        fitting_items.append((u"%d-%d" % (deposition_id, layer_number), nickname))
    return fitting_items

def has_permission_for_sample_or_series(user, sample_or_series):
    u"""Returns ``True`` if the user is allowed to see a sample series.

    :Parameters:
      - `user`: the currently logged-in user
      - `sample_or_series`: the sample or sample series for which the
        permission should be checked

    :type user: ``django.contrib.auth.models.User``
    :type sample_or_series: `models.Sample` or `models.SampleSeries`

    :Returns:
      whether the user is allowed to see the sample or sample series.

    :rtype: bool
    """
    return user.has_perm("samples.can_view_all_samples") or sample_or_series.group in user.groups.all() \
        or sample_or_series.currently_responsible_person == user

def camel_case_to_underscores(name):
    u"""Converts a CamelCase identifier to one using underscores.  For example,
    ``"MySamples"`` is converted to ``"my_samples"``.

    :Parameters:
      - `name`: the camel-cased identifier

    :type name: str

    :Return:
      the identifier in underscore notation

    :rtype: str
    """
    result = []
    for i, character in enumerate(name):
        if i == 0:
            result.append(character.lower())
        elif character in string.ascii_uppercase:
            result.extend(("_", character.lower()))
        else:
            result.append(character)
    return "".join(result)

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
        name = unicode(process._meta.verbose_name)
        template_context = self.get_template_context(process)
        context_dict = {"name": name[0].upper()+name[1:], "operator": process.operator,
                        "timestamp": process.timestamp,
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
    called “08B045”, this routine yields “08B046” (unless the new year has
    begun).
    
    :Parameters:
      - `letter`: the indentifying letter of the deposition apparatus.  For
        example, it is ``"B"`` for the 6-chamber deposition.  It needn't be a
        single letter: ``"V-"``.

    :type letter: str

    :Return:
      A so-far unused deposition number for the current calendar year for the
      given deposition apparatus.
    """
    prefix = ur"%02d%s" % (datetime.date.today().year % 100, letter)
    prefix_length = len(prefix)
    pattern_string = ur"^%s[0-9]+" % re.escape(prefix)
    deposition_numbers = \
        models.Deposition.objects.filter(number__regex=pattern_string).values_list("number", flat=True).iterator()
    try:
        next_number = max(int(deposition_number[prefix_length:]) for deposition_number in deposition_numbers) + 1
    except ValueError, e:
        if e.message != "max() arg is an empty sequence":
            raise
        next_number = 0
    return prefix + u"%03d" % next_number

def lookup_sample(sample_name, request):
    u"""Looks up the `sample_name` in the database (also among the aliases),
    and returns that sample if it was found *and* the current user is allowed
    to view it.  If not, it either raises an exception or returns an HTTP
    response object that the calling view should return immediately to its
    caller.
    
    :Parameters:
      - `sample_name`: name of the sample
      - `request`: the HTTP request object

    :type sample_name: unicode
    :type request: ``HttpRequest``

    :Return:
      the single found sample, and an HTTP response object.  Exactly one of
      both is ``None``.  So if the HTTP response object is given, this is some
      sort of mild exception.

    :rtype: `models.Sample`, ``HttpResponse``

    :Exceptions:
      - `Http404`: of the sample name could not be found.
    """
    sample = get_sample(sample_name)
    if not sample:
        raise Http404(_(u"Sample %s could not be found (neither as an alias).") % sample_name)
    if isinstance(sample, list):
        return None, render_to_response(
            "disambiguation.html", {"alias": sample_name, "samples": sample, "title": _("Ambiguous sample name")},
            context_instance=RequestContext(request))
    if not has_permission_for_sample_or_series(request.user, sample):
        return None, utils.HttpResponseSeeOther("permission_error")
    return sample, None

def convert_id_to_int(process_id):
    u"""If the user gives a process ID via the browser, it must be converted to
    an integer ecause this is what's stored in the database.  (Well, actually
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

def get_allowed_result_processes(user, samples=[], sample_series=[]):
    u"""Generates a list of all result processes that the user is allowed to
    add to the given sample(-series).  It's a list of dictionaries containing
    two keys: ``"name"`` and ``"link"``.  The name is a human-friendly name of
    the result process, and the link points to the add view of the respective
    process.

    Actually, it is an all-or-nothing situation.  Either the result is the
    empty list, or the full list of result processes.  At least at the moment,
    I see no reason to have something more fine-grained.

    :Parameters:
      - `user`: the current user
      - `samples`: a list with samples for which the user wants to add result
        processes
      - `sample_series`: a list with sample series for which the user wants to
        add result processes

    :type user: ``django.contrib.auth.models.User``
    :type samples: list of `models.Sample`
    :type sample_series: list of `models.SampleSeries`

    :Return:
      all result processes that the user is allowed to add to the given
      sample(-series).

    :rtype: list of dict
    """
    user_groups = user.groups.all()
    for sample in samples:
        if sample.currently_responsible_person != user and sample.group and sample.group not in user_groups:
            return []
    for sample_series in sample_series:
        if sample_series.currently_responsible_person != user and sample_series.group not in user_groups:
            return []
    return [{"name": cls._meta.verbose_name, "link": cls.get_add_url()} for cls in models.result_process_classes]

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

def get_user_hash(user):
    u"""Generates a secret hash that is connected with a user.  It is means as
    some sort of URL-based login for fetching feeds.  If the user accesses his
    feed via his aggregator, he is possibly not logged-in.  Because the
    aggregator cannot login by itself, the URL must be made unguessable.  This
    is done by appending the secret hash.

    Technically, it is the fist 10 characters of a salted SHA-1 hash of the
    user's name.
    
    :Parameters:
      - `user`: the current user

    :type user: ``django.contrib.auth.models.User``

    :Return:
      The user's secret hash

    :rtype: str
    """
    user_hash = hashlib.sha1()
    user_hash.update(settings.SECRET_KEY)
    user_hash.update(user.username)
    return user_hash.hexdigest()[:10]

def http_response_go_next(request, view="samples.views.main.main_menu", kwargs={}):
    u"""After a POST request was successfully processed, there si typically a
    redirect to another page – maybe the main menu, or the page from where the
    add/edit request was started.

    The latter is appended to the URL as a query string with the ``next`` key,
    e.g.::

        /chantal/6-chamber_deposition/08B410/edit/?next=/chantal/samples/08B410a

    This routine generated the proper ``HttpResponse`` object that contains the
    redirection.  It always has HTPP status code 303 (“see other”).

    :Parameters:
      - `request`: the current HTTP request
      - `view`: the view name/function to redirect to
      - `kwargs`: group parameters in the URL pattern that have to be filled

    :type request: ``HttpRequest``
    :type view: str or function
    :type kwargs: dict

    :Return:
      the HTTP response object to be returned to the view's caller

    :rtype: ``HttpResponse``
    """
    next_url = parse_query_string(request).get("next")
    if next_url is not None:
        return HttpResponseSeeOther(next_url)
    else:
        return HttpResponseSeeOther(django.core.urlresolvers.reverse(view, kwargs=kwargs))

def is_remote_client(request):
    u"""Tests whether the current request was not done by an ordinary browser
    like Firefox or Google Chome but by the Chantal Remote Client.

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
