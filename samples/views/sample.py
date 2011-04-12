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


u"""All views and helper routines directly connected with samples themselves
(no processes!).  This includes adding, editing, and viewing samples.
"""

from __future__ import absolute_import

import time, copy, hashlib, urllib, os.path
from cStringIO import StringIO
import PIL, PIL.ImageOps
from django.views.decorators.http import condition
from django.db.models import Q
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.conf import settings
from django.http import Http404
import django.forms as forms
from django.core.cache import cache
from samples import models, permissions
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import urlquote_plus
import django.core.urlresolvers
from chantal_common.utils import append_error, HttpResponseSeeOther, adjust_timezone_information, is_json_requested, \
    respond_in_json, get_all_models, mkdirs
from chantal_common.signals import storage_changed
from samples.views import utils, form_utils, feed_utils, table_export
import chantal_common.search
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
        exclude = ("name", "split_origin", "processes", "watchers")


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
    u"""View for editing existing samples.  You can't use it to add new
    samples.

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
    user_details = request.user.samples_user_details
    sample_details = sample.get_sample_details()
    if request.method == "POST":
        sample_form = SampleForm(request.user, request.POST, instance=sample)
        edit_description_form = form_utils.EditDescriptionForm(request.POST)
        all_valid = all([sample_form.is_valid(), edit_description_form.is_valid()])
        referentially_valid = is_referentially_valid(sample, sample_form, edit_description_form)
        if sample_details:
            sample_details_context, sample_details_valid = \
                sample_details.process_post(request.user, request.POST, sample_form, edit_description_form)
            all_valid = all_valid and sample_details_valid
        else:
            sample_details_context = {}
        if all_valid and referentially_valid:
            sample = sample_form.save()
            if sample_details:
                sample_details.save_form_data(sample_details_context)
            feed_reporter = feed_utils.Reporter(request.user)
            if sample.currently_responsible_person != old_responsible_person:
                sample.currently_responsible_person.my_samples.add(sample)
                feed_reporter.report_new_responsible_person_samples([sample], edit_description_form.cleaned_data)
            if sample.topic and sample.topic != old_topic:
                for watcher in (user_details.user for user_details in sample.topic.auto_adders.all()):
                    watcher.my_samples.add(sample)
                feed_reporter.report_changed_sample_topic([sample], old_topic, edit_description_form.cleaned_data)
            feed_reporter.report_edited_samples([sample], edit_description_form.cleaned_data)
            return utils.successful_response(
                request, _(u"Sample {sample} was successfully changed in the database.").format(sample=sample),
                by_id, {"sample_id": sample.id, "path_suffix": u""})
    else:
        sample_form = SampleForm(request.user, instance=sample)
        edit_description_form = form_utils.EditDescriptionForm()
        sample_details_context = sample_details.process_get(request.user) if sample_details else {}
    context = {"title": _(u"Edit sample “{sample}”").format(sample=sample), "sample": sample_form,
               "edit_description": edit_description_form}
    context.update(sample_details_context)
    return render_to_response("samples/edit_sample.html", context, context_instance=RequestContext(request))


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
        sample_processes.append({"label": _(u"split"), "url": sample.get_absolute_url() + "-/split/", "type": "split"})
        # Translators: Of a sample
        sample_processes.append({"label": _(u"cease of existence"), "url": sample.get_absolute_url() + "-/kill/",
                                 "type": "death"})
    general_processes = []
    if permissions.has_permission_to_add_result_process(user, sample):
        general_processes.append({"label": models.Result._meta.verbose_name, "type": "result",
                                  "url": django.core.urlresolvers.reverse("add_result")})
    general_processes.extend(permissions.get_allowed_physical_processes(user))
    if not sample_processes and not general_processes:
        raise permissions.PermissionError(user, _(u"You are not allowed to add any processes to the sample {sample} "
                                                  u"because neither are you its currently responsible person, "
                                                  u"nor in its topic, nor do you have special permissions for a "
                                                  u"physical process.").format(sample=sample), new_topic_would_help=True)
    return sample_processes, general_processes


class SamplesAndProcesses(object):
    u"""This is a container data structure for holding (almost) all data for
    the “show sample” template.  It represents one sample.  By nesting it,
    child samples can be embedded, too.

    Thus, the purpose of this class is two-fold: First, it contains one sample
    and all processes associated with it.  And secondly, it contains further
    instances of `SamplesAndProcesses` of child samples.

    Objects of this class are cached so that they can be re-used for another
    user.  Therefore, it is necessary to have methods that adaps the object to
    the current user.

    We make extensive use of dictionaries mapping strings to arbitrary objects
    here.  This is because such a data structure can be passed as a context to
    templates very easily.

    :ivar process_contexts: List of processes associated with the sample.  This
      is a list of dictionaries rather than a list of model instances.  The
      dictionaries can be used as contexts for both the “inner” templates
      (the ``show_….html`` templates for single processes) as well as the
      “outer” template ``show_sample.html``.

    :ivar process_lists: Data of child samples

    :type process_lists: list of `SamplesAndProcesses`

    :type process_contexts: list of dict mapping str to ``object``
    """

    @staticmethod
    def samples_and_processes(sample_name, user, post_data=None):
        u"""Returns the data structure used in the template to display the
        sample with all its processes.

        :Parameters:
          - `sample_name`: the sample or alias of the sample to display
          - `user`: the currently logged-in user
          - `post_data`: the POST dictionary if it was an HTTP POST request, or
            ``None`` otherwise

        :type sample_name: unicode
        :type user: ``django.contrib.auth.models.User``
        :type post_data: ``QueryDict``

        :Return:
          a list with all result processes of this sample in chronological
          order.

        :rtype: `SamplesAndProcesses`
        """
        sample, clearance = utils.lookup_sample(sample_name, user, with_clearance=True)
        cache_key = "sample:{0}-{1}".format(sample.pk, models.get_user_settings_hash(user))
        samples_and_processes = cache.get(cache_key)
        if samples_and_processes is None:
            samples_and_processes = SamplesAndProcesses(sample, clearance, user, post_data)
            cache.set(cache_key, samples_and_processes)
            sample.append_cache_key(cache_key)
        else:
            samples_and_processes.personalize(user, clearance, post_data)
        return samples_and_processes

    def __init__(self, sample, clearance, user, post_data):
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
        # This will be filled with more, once child samples are displayed, too.
        self.sample_context = {"sample": sample}
        self.update_sample_context_for_user(user, clearance, post_data)
        self.process_contexts = []
        def collect_process_contexts(local_context=None):
            u"""Constructs the list of process context dictionaries.  This
            internal helper function directly populates
            ``self.process_contexts``.  It consists of three parts: First, we
            ascend through the ancestors of the sample to the first parent.
            Then, for every ancestor and for the sample itself, the relevant
            processes are found in form of a ``QuerySet``, paying attention to
            a possible clearance and to the so-called “cutoff timestamps”.  And
            finally, we iterate over the ``QuerySet`` and get the process
            context dictionary, possibly from the cache.

            :Parameters:
              - `local_context`: Information about the current sample to
                process.  This is important when we walk through the ancestors
                and need to keep track of where we are currently.  In
                particular, this is used for sample splits because they must
                know which is the current sample, which is the main sample
                which will be actually displayed etc.

            :type local_context: dict mapping str to ``object``
            """
            if local_context is None:
                local_context = self.sample_context.copy()
                local_context.update({"original_sample": sample, "latest_descendant": None, "cutoff_timestamp": None})
            split = local_context["sample"].split_origin
            if split:
                new_local_context = local_context.copy()
                new_local_context["sample"] = split.parent
                new_local_context["latest_descendant"] = local_context["sample"]
                new_local_context["cutoff_timestamp"] = split.timestamp
                collect_process_contexts(new_local_context)
            if local_context["clearance"]:
                basic_query = local_context["clearance"].processes.filter(samples=local_context["sample"])
            else:
                basic_query = models.Process.objects. \
                    filter(Q(samples=local_context["sample"]) | Q(result__sample_series__samples=local_context["sample"]))
            if local_context["cutoff_timestamp"] is None:
                processes = basic_query.distinct()
            else:
                processes = basic_query.filter(timestamp__lte=local_context["cutoff_timestamp"]).distinct()
            for process in processes:
                process_context = utils.digest_process(process, user, local_context)
                self.process_contexts.append(process_context)
        collect_process_contexts()
        self.process_lists = []

    def update_sample_context_for_user(self, user, clearance, post_data):
        u"""Updates the sample data in this data structure according to the
        current user.  If the ``SamplesAndProcesses`` object was taken from the
        cache, it was probably for another user, so I must modify the
        user-dependent fields.  In particular, the “is-my-sample” checkboxes
        are generated here, as well as the icons to edit the sample or to add
        processes.

        This method is also called if the ``SamplesAndProcesses`` object is
        constructed from scratch.

        :Parameters:
          - `user`: the currently logged-in user
          - `clearance`: the clearance object that was used to show the sample,
            or ``None`` if no clearance was necessary (though maybe existing)
          - `post_data`: the POST data if it was an HTTP POST request, and
            ``None`` otherwise

        :type user: ``django.contrib.auth.models.User``
        :type clearance: `models.Clearance`
        :type post_data: ``QueryDict`` or ``NoneType``
        """
        self.user = user
        self.user_details = user.samples_user_details
        sample = self.sample_context["sample"]
        self.is_my_sample = self.user.my_samples.filter(id__exact=sample.id).exists()
        self.is_my_sample_form = IsMySampleForm(
            prefix=str(sample.pk), initial={"is_my_sample": self.is_my_sample}) if post_data is None \
            else IsMySampleForm(post_data, prefix=str(sample.pk))
        self.sample_context.update({"is_my_sample_form": self.is_my_sample_form, "clearance": clearance})
        try:
            # FixMe: calling get_allowed_processes is too expensive
            get_allowed_processes(self.user, sample)
            self.sample_context["can_add_process"] = True
        except permissions.PermissionError:
            self.sample_context["can_add_process"] = False
        self.sample_context["can_edit"] = permissions.has_permission_to_edit_sample(self.user, sample)
        if self.sample_context["can_edit"] and utils.sample_name_format(sample.name) in ["provisional", "old"]:
            self.sample_context["id_for_rename"] = str(sample.pk)
        else:
            self.sample_context["id_for_rename"] = None
        sample_details = sample.get_sample_details()
        if sample_details:
            self.sample_context.update(sample_details.get_context_for_user(user, self.sample_context))

    def personalize(self, user, clearance, post_data):
        u"""Change the ``SamplesAndProcesses`` object so that it is suitable
        for the current user.  If the object was taken from the cache, it was
        probably for another user, so many things need to be adapted.  Here, I
        walk through all processes to change them.  In particular, the
        edit/duplicate/resplit icons are corrected.

        :Parameters:
          - `user`: the currently logged-in user
          - `clearance`: the clearance object that was used to show the sample,
            or ``None`` if no clearance was necessary (though maybe existing)
          - `post_data`: the POST data if it was an HTTP POST request, and
            ``None`` otherwise

        :type user: ``django.contrib.auth.models.User``
        :type clearance: `models.Clearance`
        :type post_data: ``QueryDict`` or ``NoneType``
        """
        self.update_sample_context_for_user(user, clearance, post_data)
        for process_context in self.process_contexts:
            process_context.update(
                process_context["process"].get_context_for_user(user, process_context))
        for process_list in self.process_lists:
            process_list.personalize(user, clearance, post_data)

    def __iter__(self):
        u"""Returns an iterator over all samples and processes.  It is used in
        the template to generate the whole page.  Note that because no
        recursion is allowed in Django's template language, this generator
        method must flatten the nested structure, and it must return sample and
        process at the same time, although the process may be ``None``.  The
        template must be able to cope with that fact.

        Additionally, as the first value of the returned 3-tuples, a boolean is
        given.  If it is ``True``, at a new section with a new sample starts,
        and that all subsequent processes belong to that sample – until the
        next sample.

        Note that both sample and process aren't model instances.  Instead,
        they are dictionaries containing everything the template needs.  In
        particular, the actual sample instance is ``sample["sample"]`` or, in
        template code syntax, ``sample.sample``.

        :Return:
          Generator for iterating over all samples and processes.  It returns a
          tuple with three values, ``sample_start``, ``sample`` and
          ``process``.  Either one or none of ``sample`` and ``process`` may be
          ``None``.

        :rtype: ``generator``
        """
        if self.process_contexts:
            yield True, self.sample_context, self.process_contexts[0]
            for process_context in self.process_contexts[1:]:
                yield False, self.sample_context, process_context
        else:
            yield True, self.sample_context, None
        for process_list in self.process_lists:
            for sample_start, sample_context, process_context in process_list:
                yield sample_start, sample_context, process_context

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
        sample = self.sample_context["sample"]
        if self.is_my_sample_form.cleaned_data["is_my_sample"] and not self.is_my_sample:
            added.add(sample)
            self.user.my_samples.add(sample)
        elif not self.is_my_sample_form.cleaned_data["is_my_sample"] and self.is_my_sample:
            removed.add(sample)
            self.user.my_samples.remove(sample)
        for process_list in self.process_lists:
            added_, removed_ = process_list.save_to_database()
            added.update(added_)
            removed.update(removed_)
        return added, removed


def embed_timestamp(request, sample_name):
    u"""Put a timestamp field in the request object that is used by both
    `sample_timestamp` and `sample_etag`.  It's really a pity that you can't
    give *one* function for returning both with Django's API for conditional
    view processing.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode
    """
    if not hasattr(request, "_sample_timestamp"):
        timestamps = []
        try:
            sample = models.Sample.objects.get(name=sample_name)
        except models.Sample.DoesNotExist:
            request._sample_timestamp = None
        else:
            timestamps.append(sample.last_modified)
            try:
                clearance = models.Clearance.objects.get(user=request.user, sample=sample)
            except models.Clearance.DoesNotExist:
                pass
            else:
                timestamps.append(clearance.last_modified)
            user_details = request.user.samples_user_details
            timestamps.append(user_details.display_settings_timestamp)
            timestamps.append(user_details.my_samples_timestamp)
            request._sample_timestamp = adjust_timezone_information(max(timestamps))


def sample_timestamp(request, sample_name):
    u"""Calculate the timestamp of a sample.  For this, the timestamp of last
    modification of the sample is taken, and that of other things that
    influence the sample datasheet (language, “My Samples”).  The latest
    timestamp is chosen and returned.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the timestamp of the last modification of the sample's datasheet

    :rtype: ``datetime.datetime``
    """
    embed_timestamp(request, sample_name)
    return request._sample_timestamp


def sample_etag(request, sample_name):
    u"""Calculate an ETag for the sample datasheet.  For this, the timestamp of
    last modification of the sample is taken, and the primary key of the
    current user.  The checksum of both is returned.

    This routine is necessary because browsers don't handle the "Vary: Cookie"
    header well.  In order to avoid one user getting cached pages of another
    user who used the same browser instance befor (e.g. in a lab), I must
    create an ETag.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the ETag of the sample's datasheet

    :rtype: str
    """
    embed_timestamp(request, sample_name)
    if request._sample_timestamp:
        hash_ = hashlib.sha1()
        hash_.update(str(request._sample_timestamp))
        hash_.update(str(request.user.pk))
        return hash_.hexdigest()


@login_required
@condition(sample_etag, sample_timestamp)
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
    if request.method == "POST":
        samples_and_processes = SamplesAndProcesses.samples_and_processes(sample_name, request.user, request.POST)
        if samples_and_processes.is_valid():
            added, removed = samples_and_processes.save_to_database()
            if is_json_requested(request):
                return respond_in_json(True)
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
        if is_json_requested(request):
            sample = utils.lookup_sample(sample_name, request.user)
            return respond_in_json(sample.get_data().to_dict())
        samples_and_processes = SamplesAndProcesses.samples_and_processes(sample_name, request.user)
    messages.debug(request, "DB-Zugriffszeit: {0:.1f} ms".format((time.time() - start) * 1000))
    return render_to_response(
        "samples/show_sample.html",
        {"title": _(u"Sample “{sample}”").format(sample=samples_and_processes.sample_context["sample"]),
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
    if is_json_requested(request):
        # No redirect for the remote client.  This also makes a POST request
        # possible.
        if path_suffix == "/edit/":
            return edit(request, sample.name)
        else:  # FixMe: More path_suffixes should be tested
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
        process["url"] += "?sample={0}&next={1}".format(urlquote_plus(sample_name), sample.get_absolute_url())
    return render_to_response("samples/add_process.html",
                              {"title": _(u"Add process to sample “{sample}”").format(sample=sample),
                               "processes": sample_processes + general_processes},
                              context_instance=RequestContext(request))


class SearchSamplesForm(forms.Form):
    u"""Form for searching for samples.  So far, you can only enter a name
    substring for looking for samples.
    """
    _ = ugettext_lazy
    name_pattern = forms.CharField(label=_(u"Name pattern"), max_length=30, required=False)
    aliases = forms.BooleanField(label=_(u"Include alias names"), required=False)


class AddToMySamplesForm(forms.Form):
    _ = ugettext_lazy
    add_to_my_samples = forms.BooleanField(required=False)


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


max_results = 50
@login_required
def search(request):
    u"""View for searching for samples.  The rule is: Everyone can see the
    *names* (not the data sheets) of all samples, unless they are in a
    confidential topic, unless the user is a member in that topic, its
    currently responsible person, or you have a clearance for the sample.

    A POST request on this URL will add samples to the “My Samples” list.
    *All* search parameters are in the query string, so if you just want to
    search, this is a GET requets.  Therefore, this view has two submit
    buttons.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    too_many_results = False
    base_query = restricted_samples_query(request.user)
    search_samples_form = SearchSamplesForm(request.GET)
    found_samples = []
    if search_samples_form.is_valid():
        name_pattern = search_samples_form.cleaned_data["name_pattern"]
        if name_pattern:
            if search_samples_form.cleaned_data["aliases"]:
                found_samples = base_query.filter(Q(name__icontains=name_pattern) | Q(aliases__name__icontains=name_pattern))
            else:
                found_samples = base_query.filter(name__icontains=name_pattern)
            too_many_results = found_samples.count() > max_results
            found_samples = found_samples[:max_results] if too_many_results else found_samples
    my_samples = request.user.my_samples.all()
    if request.method == "POST":
        sample_ids = set(utils.int_or_zero(key.partition("-")[0]) for key, value in request.POST.items()
                         if value == u"on")
        samples = base_query.in_bulk(sample_ids).values()
        request.user.my_samples.add(*samples)
    add_to_my_samples_forms = [AddToMySamplesForm(prefix=str(sample.pk)) if sample not in my_samples else None
                               for sample in found_samples]
    return render_to_response("samples/search_samples.html", {"title": _(u"Search for sample"),
                                                              "search_samples": search_samples_form,
                                                              "found_samples": zip(found_samples, add_to_my_samples_forms),
                                                              "too_many_results": too_many_results,
                                                              "max_results": max_results},
                              context_instance=RequestContext(request))


@login_required
def advanced_search(request):
    u"""View for searching for samples, sample series, physical processes, and
    results.  The visibility rules of the search results are the same as for
    the sample search.  Additionally, you can only see sample series you are
    the currently responsible person of or that are in one of your topics.

    A POST request on this URL will add samples to the “My Samples” list.
    *All* search parameters are in the query string, so if you just want to
    search, this is a GET requets.  Therefore, this view has two submit
    buttons.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    model_list = [model for model in chantal_common.search.get_all_searchable_models() if hasattr(model, "get_absolute_url")]
    search_tree = None
    results, add_forms = [], []
    too_many_results = False
    root_form = chantal_common.search.SearchModelForm(model_list, request.GET)
    search_performed = False
    if root_form.is_valid() and root_form.cleaned_data["_model"]:
        search_tree = get_all_models()[root_form.cleaned_data["_model"]].get_search_tree_node()
        parse_tree = root_form.cleaned_data["_model"] == root_form.cleaned_data["_old_model"]
        search_tree.parse_data(request.GET if parse_tree else None, "")
        if search_tree.is_valid():
            if search_tree.model_class == models.Sample:
                base_query = restricted_samples_query(request.user)
            elif search_tree.model_class == models.SampleSeries:
                base_query = models.SampleSeries.objects.filter(
                    Q(topic__confidential=False) | Q(topic__members=request.user) |
                    Q(currently_responsible_person=request.user)).distinct()
            else:
                base_query = None
            results, too_many_results = chantal_common.search.get_search_results(search_tree, max_results, base_query)
            if search_tree.model_class == models.Sample:
                if request.method == "POST":
                    sample_ids = set(utils.int_or_zero(key[2:].partition("-")[0]) for key, value in request.POST.items()
                                     if value == u"on")
                    samples = base_query.in_bulk(sample_ids).values()
                    request.user.my_samples.add(*samples)
                my_samples = request.user.my_samples.all()
                add_forms = [AddToMySamplesForm(prefix="0-" + str(sample.pk)) if sample not in my_samples else None
                             for sample in results]
            else:
                add_forms = len(results) * [None]
            search_performed = True
        root_form = chantal_common.search.SearchModelForm(
            model_list, initial={"_old_model": root_form.cleaned_data["_model"], "_model": root_form.cleaned_data["_model"]})
    else:
        root_form = chantal_common.search.SearchModelForm(model_list)
    root_form.fields["_model"].label = u""
    content_dict = {"title": _(u"Advanced search"), "search_root": root_form, "search_tree": search_tree,
                    "results": zip(results, add_forms), "search_performed": search_performed,
                    "something_to_add": any(add_forms), "too_many_results": too_many_results, "max_results": max_results}
    return render_to_response("samples/advanced_search.html", content_dict, context_instance=RequestContext(request))


@login_required
def export(request, sample_name):
    u"""View for exporting sample data in CSV or JSON format.  Thus, the return
    value is not an HTML response.

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
    return table_export.export(request, sample.get_data_for_table_export(), _(u"process"))


def qr_code(request):
    u"""Generates the QR representation of the given data.  The data is given
    in the ``data`` query string parameter.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    try:
        data = request.GET["data"]
    except KeyError:
        raise Http404('GET parameter "data" missing.')
    return render_to_response("samples/qr_code.html", {"title": _(u"QR code"), "data": data},
                              context_instance=RequestContext(request))


def data_matrix_code(request):
    u"""Generates the Data Matrix representation of the given data.  The data
    is given in the ``data`` query string parameter.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    try:
        data = request.GET["data"]
    except KeyError:
        raise Http404('GET parameter "data" missing.')
    hash_ = hashlib.sha1()
    hash_.update(data.encode("utf-8"))
    filename = hash_.hexdigest() + ".png"
    filepath = os.path.join(settings.STATIC_ROOT, "data_matrix", filename)
    url = os.path.join(settings.STATIC_URL, "data_matrix", filename)
    if not os.path.exists(filepath):
        mkdirs(filepath)
        image = PIL.Image.open(StringIO(urllib.urlopen(
                    "http://www.bcgen.com/demo/IDAutomationStreamingDataMatrix.aspx?"
                    u"MODE=3&D={data}&PFMT=6&PT=F&X=0.13&O=0&LM=0".format(data=urlquote_plus(data, safe="/"))).read()))
        image = image.crop((38, 3, 118, 83))
        image = PIL.ImageOps.expand(image, border=16, fill=256).convert("1")
        image.save(filepath)
        storage_changed.send(data_matrix_code)
    return render_to_response("samples/data_matrix_code.html", {"title": _(u"Data Matrix code"), "url": url, "data": data},
                              context_instance=RequestContext(request))
