#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""All views and helper routines directly connected with samples themselves
(no processes!).  This includes adding, editing, and viewing samples.
"""

from __future__ import absolute_import

import time, copy
from django.db.models import Q
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
import django.forms as forms
from samples import models, permissions
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import urlquote_plus
import django.core.urlresolvers
from chantal_common.utils import append_error, HttpResponseSeeOther
from samples.views import utils, form_utils, feed_utils, csv_export
from django.utils.translation import ugettext as _, ugettext_lazy, ungettext


class IsMySampleForm(forms.Form):
    u"""Form class just for the checkbox marking that the current sample is
    amongst “My Samples”.
    """
    _ = ugettext_lazy
    is_my_sample = forms.BooleanField(label=_(u"is amongst My Samples"), required=False)


class SampleForm(forms.ModelForm):
    u"""Model form class for a sample.  All unusual I do here is overwriting
    `models.Sample.currently_responsible_person` in oder to be able to see
    *full* person names (not just the login name).
    """
    _ = ugettext_lazy
    currently_responsible_person = form_utils.UserField(label=_(u"Currently responsible person"))
    topic = form_utils.TopicField(label=_(u"Topic"), required=False)

    def __init__(self, user, *args, **kwargs):
        super(SampleForm, self).__init__(*args, **kwargs)
        self.fields["topic"].set_topics(user, kwargs["instance"].topic if kwargs.get("instance") else None)
        self.fields["currently_responsible_person"].set_users(
            kwargs["instance"].currently_responsible_person if kwargs.get("instance") else None)

    class Meta:
        model = models.Sample
        exclude = ("name", "split_origin", "processes")


def is_referentially_valid(sample, sample_form, edit_description_form):
    u"""Checks that the “important” checkbox is marked if the topic or the
    currently responsible person were changed.

    :Parameters:
      - `sample`: the currently edited sample
      - `sample_form`: the bound sample form
      - `edit_description_form`: a bound form with description of edit changes

    :type sample: `models.Sample`
    :type sample_form: `SampleForm`
    :type edit_description_form: `form_utils.EditDescriptionForm` or ``NoneType``

    :Return:
      whether the “important” tickbox was really marked in case of significant
      changes

    :rtype: bool
    """
    referentially_valid = True
    if sample_form.is_valid() and edit_description_form.is_valid() and \
            (sample_form.cleaned_data["topic"] != sample.topic or
             sample_form.cleaned_data["currently_responsible_person"] != sample.currently_responsible_person) and \
             not edit_description_form.cleaned_data["important"]:
        referentially_valid = False
        append_error(edit_description_form,
                     _(u"Changing the topic or the responsible person must be marked as important."), "important")
    return referentially_valid


@login_required
def edit(request, sample_name):
    u"""View for editing existing samples.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample = utils.lookup_sample(sample_name, request.user)
    permissions.assert_can_edit_sample(request.user, sample)
    old_topic, old_responsible_person = sample.topic, sample.currently_responsible_person
    user_details = utils.get_profile(request.user)
    if request.method == "POST":
        sample_form = SampleForm(request.user, request.POST, instance=sample)
        edit_description_form = form_utils.EditDescriptionForm(request.POST)
        referentially_valid = is_referentially_valid(sample, sample_form, edit_description_form)
        if all([sample_form.is_valid(), edit_description_form.is_valid()]) and referentially_valid:
            sample = sample_form.save()
            feed_reporter = feed_utils.Reporter(request.user)
            if sample.currently_responsible_person != old_responsible_person:
                utils.get_profile(sample.currently_responsible_person).my_samples.add(sample)
                feed_reporter.report_new_responsible_person_samples([sample], edit_description_form.cleaned_data)
            if sample.topic and sample.topic != old_topic:
                for watcher in sample.topic.auto_adders.all():
                    watcher.my_samples.add(sample)
                feed_reporter.report_changed_sample_topic([sample], old_topic, edit_description_form.cleaned_data)
            feed_reporter.report_edited_samples([sample], edit_description_form.cleaned_data)
            return utils.successful_response(request,
                                             _(u"Sample %s was successfully changed in the database.") % sample,
                                             sample.get_absolute_url())
    else:
        sample_form = SampleForm(request.user, instance=sample)
        edit_description_form = form_utils.EditDescriptionForm()
    return render_to_response("samples/edit_sample.html", {"title": _(u"Edit sample “%s”") % sample,
                                                           "sample": sample_form,
                                                           "edit_description": edit_description_form},
                              context_instance=RequestContext(request))


def get_allowed_processes(user, sample):
    u"""Return all processes the user is allowed to add to the sample.

    :Parameters:
      - `user`: the current user
      - `sample`: the sample to be edit or displayed

    :type user: ``django.contrib.auth.models.User``
    :type sample: `models.Sample`

    :Return:
      two lists with the allowed processes.  Every process is returned as a
      dict with three keys: ``"label"``, ``"url"``, and ``"type"``.
      ``"label"`` is the human-friendly descriptive name of the process,
      ``"url"`` is the URL to the process (processing `sample`!), and
      ``"type"`` is the computer-friendly name of the process.  ``"type"`` may
      be ``"split"``, ``"death"``, ``"result"``, or the class name of a
      physical process (e.g. ``"PDSMeasurement"``).

      The first list is sample split and sample death, the second list are
      results and physical processes.

    :rtype: list of dict mapping str to unicode/str, list of dict mapping str
      to unicode/str

    :Exceptions:
      - `permissions.PermissionError`: if the user is not allowed to add any
        process to the sample
    """
    sample_processes = []
    if permissions.has_permission_to_edit_sample(user, sample) and not sample.is_dead():
        sample_processes.append({"label": _(u"split"), "url": sample.get_absolute_url() + "/split/", "type": "split"})
        # Translation hint: Of a sample
        sample_processes.append({"label": _(u"cease of existence"), "url": sample.get_absolute_url() + "/kill/",
                                 "type": "death"})
    general_processes = []
    if permissions.has_permission_to_add_result_process(user, sample):
        general_processes.append({"label": models.Result._meta.verbose_name, "type": "result",
                                  "url": django.core.urlresolvers.reverse("add_result")})
    general_processes.extend(permissions.get_allowed_physical_processes(user))
    if not sample_processes and not general_processes:
        raise permissions.PermissionError(user, _(u"You are not allowed to add any processes to the sample %s "
                                                  u"because neither are you its currently responsible person, "
                                                  u"nor in its topic, nor do you have special permissions for a "
                                                  u"physical process.") % sample, new_topic_would_help=True)
    return sample_processes, general_processes


class SamplesAndProcesses(object):
    u"""This is a container data structure for holding (almost) all data for
    the “show sample” template.  It represents one sample.  By nesting it,
    child samples can be embedded, too.

    Thus, the purpose of this class is two-fold: First, it contains one sample
    and all processes associated with it.  And secondly, it contains further
    instances of `SamplesAndProcesses` of child samples.

    :ivar processes: List of processes associated with the sample.  This is a
      list of dictionaries rather than a list of model instances.

    :ivar process_lists: list of `SamplesAndProcesses` of child samples.
    """

    def __init__(self, sample, full_view, user, post_data):
        u"""
        :Parameters:
          - `sample`: the sample to which the processes belong
          - `full_view`: whether the user can fully view the sample; ``False``
            currently means that the sample is accessed through a clearance
          - `user`: the currently logged-in user
          - `post_data`: the POST data if it was an HTTP POST request, and
            ``None`` otherwise

        :type sample: `models.Sample`
        :type full_view: bool
        :type user: ``django.contrib.auth.models.User``
        :type post_data: ``QueryDict`` or ``NoneType``
        """
        self.sample = sample
        self.full_view = full_view
        self.user = user
        self.user_details = utils.get_profile(user)
        self.is_my_sample = self.user_details.my_samples.filter(id__exact=sample.id).exists()
        self.is_my_sample_form = IsMySampleForm(
            prefix=str(sample.pk), initial={"is_my_sample": self.is_my_sample}) if post_data is None \
            else IsMySampleForm(post_data, prefix=str(sample.pk))
        self.processes = []
        self.process_lists = []

    def samples_and_processes(self):
        u"""Returns an iterator over all samples and processes.  It is used in
        the template to generate the whole page.  Note that because no
        recursion is allowed in Django's template language, this generator
        method must flatten the nested structure, and it must return sample and
        process at the same time, although one of them may be ``None``.  The
        template must be able to cope with that fact.

        If the sample is not ``None``, this means that a new section with a new
        sample starts, and that all subsequent processes belong to that sample
        – until the next sample.

        Note that both sample and process aren't model instances.  Instead,
        they are dictionaries containing everything the template needs.  In
        particular, the actual sample instance is ``sample["sample"]`` or, in
        template code syntax, ``sample.sample``.

        :Return:
          Generator for iterating over all samples and processes.  It returns a
          tuple with two values, ``sample`` and ``process``.  Either one or
          none of them may be ``None``.

        :rtype: ``generator``
        """
        sample = {"sample": self.sample, "is_my_sample_form": self.is_my_sample_form, "full_view": self.full_view}
        try:
            # FixMe: calling get_allowed_processes is too expensive
            get_allowed_processes(self.user, self.sample)
            sample["can_add_process"] = True
        except permissions.PermissionError:
            sample["can_add_process"] = False
        sample["can_edit"] = permissions.has_permission_to_edit_sample(self.user, self.sample)
        sample["number_for_rename"] = \
            self.sample.name[1:] if self.sample.name.startswith("*") and sample["can_edit"] else None
        if self.processes:
            yield sample, self.processes[0]
            for process in self.processes[1:]:
                yield None, process
        else:
            yield sample, None
        for process_list in self.process_lists:
            for sample, process in process_list.samples_and_processes():
                yield sample, process

    def is_valid(self):
        u"""Checks whether all “is My Sample” forms of the “show sample” view
        are valid.  Actually, this method is rather silly because the forms
        consist only of checkboxes and they can never be invalid.  But sticking
        to rituals reduces errors …

        :Return:
          whether all forms are valid

        :rtype: bool
        """
        all_valid = self.is_my_sample_form.is_valid()
        all_valid = all_valid and all([process_list.is_valid() for process_list in self.process_lists])
        return all_valid

    def save_to_database(self):
        u"""Changes the members of the “My Samples” list according to what the
        user selected.

        :Return:
          names of added samples, names of removed samples

        :rtype: set of unicode, set of unicode
        """
        added = set()
        removed = set()
        if self.is_my_sample_form.cleaned_data["is_my_sample"] and not self.is_my_sample:
            added.add(self.sample)
            self.user_details.my_samples.add(self.sample)
        elif not self.is_my_sample_form.cleaned_data["is_my_sample"] and self.is_my_sample:
            removed.add(self.sample)
            self.user_details.my_samples.remove(self.sample)
        for process_list in self.process_lists:
            added_, removed_ = process_list.save_to_database()
            added.update(added_)
            removed.update(removed_)
        return added, removed


class ProcessContext(utils.ResultContext):
    u"""Contains all info that processes must know in order to render
    themselves as HTML.  It does the same as the parent class
    `utils.ResultContext` (see there for full information), however, it extends
    its functionality a little bit for being useful for *samples* instead of
    sample series.

    Its main purpose is to create the datastructure built of nested
    `SamplesAndProcesses`, which is later used in the template.

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

    :ivar latest_descendant: This is used in ``show_sample_split.html`` for
      identifying direct ancestors of the sample when displaying a sample split
      of an ancestor which is not the parent.  When walking up through the
      ancestors, `latest_descendant` contains the respectively previous sample.
    """

    def __init__(self, user, sample_name):
        u"""
        :Parameters:
          - `user`: the user that wants to see all the generated HTML
          - `sample_name`: the sample or alias of the sample to display

        :type user: django.contrib.auth.models.User
        :type original_sample: `models.Sample`

        :Exceptions:
          - `Http404`: if the sample name could not be found
          - `AmbiguityException`: if more than one matching alias was found
          - `permissions.PermissionError`: if the user is not allowed to view the
            sample
        """
        self.original_sample, self.clearance = utils.lookup_sample(sample_name, user, with_clearance=True)
        self.current_sample = self.original_sample
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
        if self.clearance:
            basic_query = self.clearance.processes.filter(samples=self.current_sample)
        else:
            basic_query = models.Process.objects.filter(Q(samples=self.current_sample) |
                                                        Q(result__sample_series__samples=self.current_sample))
        if self.cutoff_timestamp is None:
            return basic_query.distinct()
        else:
            return basic_query.filter(timestamp__lte=self.cutoff_timestamp).distinct()

    def collect_processes(self):
        u"""Make a list of all processes for `current_sample`.  This routine is
        called recursively in order to resolve all upstream sample splits,
        i.e. it also collects all processes of ancestors that the current
        sample has experienced, too.

        :Return:
          all processes of `current_sample`, including those of ancestors

        :rtype: list of `model.Process`
        """
        processes = []
        split_origin = self.current_sample.split_origin
        if split_origin:
            processes.extend(self.split(split_origin).collect_processes())
        for process in self.get_processes():
            processes.append(self.digest_process(process))
        return processes

    def samples_and_processes(self, post_data=None):
        u"""Returns the data structure used in the template to display the
        sample with all its processes.

        :Parameters:
          - `post_data`: the POST dictionary if it was an HTTP POST request, or
            ``None`` otherwise

        :type post_data: ``QueryDict``

        :Return:
          a list with all result processes of this sample in chronological
          order.  Every list item is a dictionary with the information
          described in `digest_process`.

        :rtype: `SamplesAndProcesses`
        """
        process_list = SamplesAndProcesses(self.original_sample, self.clearance is None, self.user, post_data)
        process_list.processes = self.collect_processes()
        return process_list


@login_required
def show(request, sample_name):
    u"""A view for showing existing samples.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    start = time.time()
    is_remote_client = utils.is_remote_client(request)
    if request.method == "POST":
        samples_and_processes = ProcessContext(request.user, sample_name).samples_and_processes(request.POST)
        if samples_and_processes.is_valid():
            added, removed = samples_and_processes.save_to_database()
            if added:
                success_message = ungettext(u"Sample {samples} was added to My Samples.",
                                            u"Samples {samples} were added to My Samples.",
                                            len(added)).format(samples=utils.format_enumeration(added))
            else:
                success_message = u""
            if removed:
                if added:
                    success_message += u"  "
                success_message += ungettext(u"Sample {samples} was removed from My Samples.",
                                             u"Samples {samples} were removed from My Samples.",
                                             len(removed)).format(samples=utils.format_enumeration(removed))
            elif not added:
                success_message = _(u"Nothing was changed.")
            messages.success(request, success_message)
    else:
        samples_and_processes = ProcessContext(request.user, sample_name).samples_and_processes()
    messages.debug(request, "DB-Zugriffszeit: %.1f ms" % ((time.time() - start) * 1000))
    return render_to_response("samples/show_sample.html", {"title": _(u"Sample “{0}”").format(samples_and_processes.sample),
                                                           "samples_and_processes": samples_and_processes},
                              context_instance=RequestContext(request))


@login_required
def by_id(request, sample_id, path_suffix):
    u"""Pure re-direct view in case a sample is accessed by ID instead of by
    name.  It redirects to the URL with the name.  The query string, if given,
    is passed, too.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_id`: the numberic ID of the sample
      - `path_suffix`: the trailing path, e.g. ``"/split/"``; if you just view
        a sample, it is empty (or only the query string)

    :type request: ``HttpRequest``
    :type sample_id: unicode
    :type path_suffix: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id))
    if utils.is_remote_client(request):
        # No redirect for the remote client
        return show(request, sample.name)
    # Necessary so that the sample's name isn't exposed through the URL
    try:
        permissions.assert_can_fully_view_sample(request.user, sample)
    except permissions.PermissionError:
        if not models.Clearance.objects.filter(user=request.user, sample=sample).exists():
            raise
    query_string = request.META["QUERY_STRING"] or u""
    return HttpResponseSeeOther(
        django.core.urlresolvers.reverse("show_sample_by_name", kwargs={"sample_name": sample.name}) + path_suffix +
        ("?" + query_string if query_string else u""))


@login_required
def add_process(request, sample_name):
    u"""View for appending a new process to the process list of a sample.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample = utils.lookup_sample(sample_name, request.user)
    sample_processes, general_processes = get_allowed_processes(request.user, sample)
    for process in general_processes:
        process["url"] += "?sample=%s&next=%s" % (urlquote_plus(sample_name), sample.get_absolute_url())
    return render_to_response("samples/add_process.html",
                              {"title": _(u"Add process to sample “%s”") % sample,
                               "processes": sample_processes + general_processes},
                              context_instance=RequestContext(request))


class SearchSamplesForm(forms.Form):
    u"""Form for searching for samples.  So far, you can only enter a name
    substring for looking for samples.
    """
    _ = ugettext_lazy
    name_pattern = forms.CharField(label=_(u"Name pattern"), max_length=30)


class AddToMySamplesForm(forms.Form):
    _ = ugettext_lazy
    add_to_my_samples = forms.BooleanField(required=False)


max_results = 50
@login_required
def search(request):
    u"""View for searching for samples.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user_details = utils.get_profile(request.user)
    found_samples = []
    too_many_results = False
    if request.method == "POST":
        search_samples_form = SearchSamplesForm(request.POST)
        if search_samples_form.is_valid():
            # FixMe: Currently, if you add samples to “My Samples”, the search
            # results must not change because otherwise, only those are added
            # that are also found by the new search (search and adding happens
            # at the sample time).  Thus, instead of using the primary keys of
            # all found samples to find the prefixes, the routine should
            # collect all prefixes from ``request.POST``.  Then nothing can be
            # missed.
            found_samples = \
                models.Sample.objects.filter(name__icontains=search_samples_form.cleaned_data["name_pattern"])
            too_many_results = found_samples.count() > max_results
            found_samples = found_samples[:max_results] if too_many_results else found_samples
        else:
            found_samples = []
        my_samples = user_details.my_samples.all()
        add_to_my_samples_forms = [AddToMySamplesForm(request.POST, prefix=str(sample.pk))
                                   if sample not in my_samples else None for sample in found_samples]
        new_forms = []
        for add_to_my_samples_form in add_to_my_samples_forms:
            if add_to_my_samples_form and add_to_my_samples_form.is_valid() and \
                    add_to_my_samples_form.cleaned_data["add_to_my_samples"]:
                user_details.my_samples.add(get_object_or_404(models.Sample, pk=int(add_to_my_samples_form.prefix)))
                new_forms.append(None)
            else:
                new_forms.append(add_to_my_samples_form)
        add_to_my_samples_forms = new_forms
    else:
        search_samples_form = SearchSamplesForm()
        add_to_my_samples_forms = [AddToMySamplesForm(sample, prefix=str(sample.pk)) if sample not in my_samples else None
                                   for sample in found_samples]
    return render_to_response("samples/search_samples.html", {"title": _(u"Search for sample"),
                                                              "search_samples": search_samples_form,
                                                              "found_samples": zip(found_samples, add_to_my_samples_forms),
                                                              "too_many_results": too_many_results,
                                                              "max_results": max_results},
                              context_instance=RequestContext(request))


@login_required
def export(request, sample_name):
    u"""View for exporting a sample to CSV data.  Thus, the return value is not
    an HTML response but a text/csv response.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample = utils.lookup_sample(sample_name, request.user)
    return csv_export.export(request, sample.get_data(), _(u"process"))
