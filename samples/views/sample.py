# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""All views and helper routines directly connected with samples themselves
(no processes!).  This includes adding, editing, and viewing samples.
"""

import hashlib, os.path, time, urllib, json
from io import BytesIO
import PIL
import PIL.ImageOps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib.staticfiles.storage import staticfiles_storage
import django.urls
import django.forms as forms
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils.http import urlquote_plus
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.views.decorators.http import condition
from django.utils.text import capfirst
from django.forms.utils import ValidationError
import jb_common.search
from jb_common.signals import storage_changed
from jb_common.utils.base import format_enumeration, unquote_view_parameters, HttpResponseSeeOther, is_json_requested, \
    respond_in_json, get_all_models, mkdirs, cache_key_locked, get_from_cache, int_or_zero, help_link
from jb_common.utils.views import UserField, TopicField
from samples import models, permissions, data_tree
import samples.utils.views as utils
from samples.utils import sample_names


class IsMySampleForm(forms.Form):
    """Form class just for the checkbox marking that the current sample is
    amongst “My Samples”.
    """
    is_my_sample = forms.BooleanField(label=_("is amongst My Samples"), required=False)


class SampleForm(forms.ModelForm):
    """Model form class for a sample.  All unusual I do here is overwriting
    `samples.models.Sample.currently_responsible_person` in oder to be able to see
    *full* person names (not just the login name).
    """
    currently_responsible_person = UserField(label=capfirst(_("currently responsible person")))
    topic = TopicField(label=capfirst(_("topic")), required=False)

    class Meta:
        model = models.Sample
        exclude = ("name", "split_origin", "processes", "watchers")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topic"].set_topics(user, kwargs["instance"].topic if kwargs.get("instance") else None)
        self.fields["currently_responsible_person"].set_users(user,
            kwargs["instance"].currently_responsible_person if kwargs.get("instance") else None)


def is_referentially_valid(sample, sample_form, edit_description_form):
    """Checks that the “important” checkbox is marked if the topic or the
    currently responsible person were changed.

    :param sample: the currently edited sample
    :param sample_form: the bound sample form
    :param edit_description_form: a bound form with description of edit changes

    :type sample: `samples.models.Sample`
    :type sample_form: `SampleForm`
    :type edit_description_form: `samples.utils.views.EditDescriptionForm`
        or NoneType

    :return:
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
        edit_description_form.add_error("important", ValidationError(
            _("Changing the topic or the responsible person must be marked as important."), code="required"))
    return referentially_valid


@help_link("demo.html#edit-samples")
@login_required
@unquote_view_parameters
def edit(request, sample_name):
    """View for editing existing samples.  You can't use it to add new
    samples.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample = utils.lookup_sample(sample_name, request.user)
    permissions.assert_can_edit_sample(request.user, sample)
    old_topic, old_responsible_person = sample.topic, sample.currently_responsible_person
    user_details = request.user.samples_user_details
    sample_details = sample.get_sample_details()
    if request.method == "POST":
        sample_form = SampleForm(request.user, request.POST, instance=sample)
        edit_description_form = utils.EditDescriptionForm(request.POST)
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
            feed_reporter = utils.Reporter(request.user)
            if sample.currently_responsible_person != old_responsible_person:
                sample.currently_responsible_person.my_samples.add(sample)
                feed_reporter.report_new_responsible_person_samples([sample], edit_description_form.cleaned_data)
            if sample.topic and sample.topic != old_topic:
                for watcher in (user_details.user for user_details in sample.topic.auto_adders.all()):
                    watcher.my_samples.add(sample)
                feed_reporter.report_changed_sample_topic([sample], old_topic, edit_description_form.cleaned_data)
            feed_reporter.report_edited_samples([sample], edit_description_form.cleaned_data)
            return utils.successful_response(
                request, _("Sample {sample} was successfully changed in the database.").format(sample=sample),
                "samples:show_sample_by_id", {"sample_id": sample.pk, "path_suffix": ""})
    else:
        sample_form = SampleForm(request.user, instance=sample)
        edit_description_form = utils.EditDescriptionForm()
        sample_details_context = sample_details.process_get(request.user) if sample_details else {}
    context = {"title": _("Edit sample “{sample}”").format(sample=sample), "sample": sample_form,
               "edit_description": edit_description_form}
    context.update(sample_details_context)
    return render(request, "samples/edit_sample.html", context)


@login_required
@require_http_methods(["POST"])
@unquote_view_parameters
def delete(request, sample_name):
    """View for delete the given sample.  Note that this view is POST-only.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample = utils.lookup_sample(sample_name, request.user)
    affected_objects = permissions.assert_can_delete_sample(request.user, sample)
    for instance in affected_objects:
        if isinstance(instance, models.Sample):
            utils.Reporter(request.user).report_deleted_sample(instance)
        elif isinstance(instance, models.Process):
            utils.Reporter(request.user).report_deleted_process(instance)
    success_message = _("Sample {sample} was successfully deleted in the database.").format(sample=sample)
    sample.delete()
    return utils.successful_response(request, success_message)


@login_required
@require_http_methods(["GET"])
@unquote_view_parameters
def delete_confirmation(request, sample_name):
    """View for confirming that you really want to delete the given sample.
    Typically, it is visited by clicking on an icon.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample = utils.lookup_sample(sample_name, request.user)
    affected_objects = permissions.assert_can_delete_sample(request.user, sample)
    digested_affected_objects = {}
    for instance in affected_objects:
        try:
            class_name = instance.__class__._meta.verbose_name_plural.title()
        except AttributeError:
            class_name = capfirst(_("miscellaneous"))
        digested_affected_objects.setdefault(class_name, set()).add(instance)
    return render(request, "samples/delete_sample_confirmation.html",
                  {"title": _("Delete sample “{sample}”").format(sample=sample), "sample": sample,
                   "affected_objects": digested_affected_objects})


def get_allowed_processes(user, sample):
    """Return all processes the user is allowed to add to the sample.

    :param user: the current user
    :param sample: the sample to be edit or displayed

    :type user: django.contrib.auth.models.User
    :type sample: `samples.models.Sample`

    :return:
      two lists with the allowed processes.  Every process is returned as a
      dict with three keys: ``"label"``, ``"url"``, and ``"type"``.
      ``"label"`` is the human-friendly descriptive name of the process,
      ``"url"`` is the URL to the process (processing `sample`!), and
      ``"type"`` is the computer-friendly name of the process.  ``"type"`` may
      be ``"split"``, ``"death"``, ``"result"``, or the class name of a
      physical process (e.g. ``"PDSMeasurement"``).

      The first list is sample split and sample death, the second list are
      results and physical processes.

    :rtype: list of dict mapping str to str, list of dict mapping str to str

    :raises permissions.PermissionError: if the user is not allowed to add any
        process to the sample
    """
    sample_processes = []
    if permissions.has_permission_to_edit_sample(user, sample) and not sample.is_dead():
        sample_processes.append({"label": _("split"),
                                 "url": django.urls.reverse("samples:split_and_rename", kwargs={"parent_name": sample.name}),
                                 "type": "split"})
        # Translators: Of a sample
        sample_processes.append({"label": _("cease of existence"),
                                 "url": django.urls.reverse("samples:kill_sample", kwargs={"sample_name": sample.name}),
                                 "type": "death"})
    general_processes = []
    if permissions.has_permission_to_add_result_process(user, sample):
        general_processes.append({"label": models.Result._meta.verbose_name, "type": "result",
                                  "url": django.urls.reverse("samples:add_result")})
    general_processes.extend(permissions.get_allowed_physical_processes(user))
    if not sample_processes and not general_processes:
        raise permissions.PermissionError(user, _("You are not allowed to add any processes to the sample {sample} "
                                                  "because neither are you its currently responsible person, "
                                                  "nor in its topic, nor do you have special permissions for a "
                                                  "physical process.").format(sample=sample), new_topic_would_help=True)
    return sample_processes, general_processes


class SamplesAndProcesses:
    """This is a container data structure for holding (almost) all data for
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

    :ivar process_ids: Set of all process IDs of the sample

    :ivar process_lists: Data of child samples

    :type process_lists: list of `SamplesAndProcesses`

    :type process_contexts: list of dict mapping str to ``object``

    :type process_ids: set of int
    """

    @staticmethod
    def samples_and_processes(sample_name, user, post_data=None):
        """Returns the data structure used in the template to display the
        sample with all its processes.

        :param sample_name: the sample or alias of the sample to display
        :param user: the currently logged-in user
        :param post_data: the POST dictionary if it was an HTTP POST request, or
            ``None`` otherwise

        :type sample_name: str
        :type user: django.contrib.auth.models.User
        :type post_data: QueryDict

        :return:
          a list with all result processes of this sample in chronological
          order.

        :rtype: `SamplesAndProcesses`
        """
        sample, clearance = utils.lookup_sample(sample_name, user, with_clearance=True)
        cache_key = "sample:{0}-{1}".format(sample.pk, user.jb_user_details.get_data_hash())
        # The following ``10`` is the expectation value of the number of
        # processes.  To get accurate results, use
        # ``samples.processes.count()`` instead.  However, this would slow down
        # JuliaBase.
        samples_and_processes = get_from_cache(cache_key, hits=10)
        if samples_and_processes is None:
            samples_and_processes = SamplesAndProcesses(sample, clearance, user, post_data)
            keys_list_key = "sample-keys:{0}".format(sample.pk)
            with cache_key_locked("sample-lock:{0}".format(sample.pk)):
                keys = cache.get(keys_list_key, [])
                keys.append(cache_key)
                cache.set(keys_list_key, keys, settings.CACHES["default"].get("TIMEOUT", 300) + 10)
                cache.set(cache_key, samples_and_processes)
            samples_and_processes.remove_noncleared_process_contexts(user, clearance)
        else:
            samples_and_processes.personalize(user, clearance, post_data)
        return samples_and_processes

    def __init__(self, sample, clearance, user, post_data):
        """
        :param sample: the sample to which the processes belong
        :param clearance: the clearance object that was used to show the sample,
            or ``None`` if no clearance was necessary (though maybe existing)
        :param user: the currently logged-in user
        :param post_data: the POST data if it was an HTTP POST request, and
            ``None`` otherwise

        :type sample: `samples.models.Sample`
        :type clearance: `samples.models.Clearance`
        :type user: django.contrib.auth.models.User
        :type post_data: QueryDict or NoneType
        """
        # This will be filled with more, once child samples are displayed, too.
        self.sample_context = {"sample": sample}
        self.update_sample_context_for_user(user, clearance, post_data)
        self.process_contexts = []
        self.process_ids = set()
        def collect_process_contexts(local_context=None):
            """Constructs the list of process context dictionaries.  This
            internal helper function directly populates
            ``self.process_contexts``.  It consists of three parts: First, we
            ascend through the ancestors of the sample to the first parent.
            Then, for every ancestor and for the sample itself, the relevant
            processes are found in form of a QuerySet, paying attention to
            a possible clearance and to the so-called “cutoff timestamps”.  And
            finally, we iterate over the QuerySet and get the process
            context dictionary, possibly from the cache.

            :param local_context: Information about the current sample to
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
            processes = models.Process.objects. \
                filter(Q(samples=local_context["sample"]) | Q(result__sample_series__samples=local_context["sample"])). \
                distinct()
            if local_context["cutoff_timestamp"]:
                processes = processes.filter(timestamp__lte=local_context["cutoff_timestamp"])
            for process in processes:
                process_context = utils.digest_process(process, user, local_context)
                self.process_contexts.append(process_context)
                self.process_ids.add(process.id)
        collect_process_contexts()
        self.process_lists = []

    def update_sample_context_for_user(self, user, clearance, post_data):
        """Updates the sample data in this data structure according to the
        current user.  If the ``SamplesAndProcesses`` object was taken from the
        cache, it was probably for another user, so I must modify the
        user-dependent fields.  In particular, the “is-my-sample” checkboxes
        are generated here, as well as the icons to edit the sample or to add
        processes.

        This method is also called if the `SamplesAndProcesses` object is
        constructed from scratch.

        :param user: the currently logged-in user
        :param clearance: the clearance object that was used to show the sample,
            or ``None`` if no clearance was necessary (though maybe existing)
        :param post_data: the POST data if it was an HTTP POST request, and
            ``None`` otherwise

        :type user: django.contrib.auth.models.User
        :type clearance: `samples.models.Clearance`
        :type post_data: QueryDict or NoneType
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
        self.sample_context["can_delete"] = permissions.has_permission_to_delete_sample(self.user, sample)
        if self.sample_context["can_edit"] and \
           sample_names.sample_name_format(sample.name) in sample_names.get_renamable_name_formats():
            self.sample_context["id_for_rename"] = str(sample.pk)
        else:
            self.sample_context["id_for_rename"] = None
        sample_details = sample.get_sample_details()
        if sample_details:
            self.sample_context.update(sample_details.get_context_for_user(user, self.sample_context))
        if permissions.has_permission_to_rename_sample(self.user, sample):
            self.sample_context["id_for_rename"] = str(sample.pk)
            self.sample_context["can_rename_sample"] = True

    def remove_noncleared_process_contexts(self, user, clearance):
        """Removes all items from ``self.process_contexts`` which the `user`
        is not allowed to see due to the `clearance`.  Obviously, this routine
        is a no-op if `clearance` is ``None``.

        :param user: the currently logged-in user
        :param clearance: the clearance object that was used to show the sample,
            or ``None`` if no clearance was necessary (though maybe existing)

        :type user: django.contrib.auth.models.User
        :type clearance: `samples.models.Clearance`
        """
        if clearance:
            viewable_process_contexts = []
            for process_context in self.process_contexts:
                process = process_context["process"]
                if process.operator == user or \
                        issubclass(process.content_type.model_class(), models.PhysicalProcess) and \
                        permissions.has_permission_to_view_physical_process(user, process):
                    viewable_process_contexts.append(process_context)
                else:
                    self.process_ids.remove(process.id)
            self.process_contexts = viewable_process_contexts

    def personalize(self, user, clearance, post_data):
        """Change the ``SamplesAndProcesses`` object so that it is suitable
        for the current user.  If the object was taken from the cache, it was
        probably for another user, so many things need to be adapted.  Here, I
        walk through all processes to change them.  In particular, the
        edit/duplicate/resplit icons are corrected.

        :param user: the currently logged-in user
        :param clearance: the clearance object that was used to show the sample,
            or ``None`` if no clearance was necessary (though maybe existing)
        :param post_data: the POST data if it was an HTTP POST request, and
            ``None`` otherwise

        :type user: django.contrib.auth.models.User
        :type clearance: `samples.models.Clearance`
        :type post_data: QueryDict or NoneType
        """
        self.update_sample_context_for_user(user, clearance, post_data)
        self.remove_noncleared_process_contexts(user, clearance)
        for process_context in self.process_contexts:
            process_context.update(
                process_context["process"].get_context_for_user(user, process_context))
        for process_list in self.process_lists:
            process_list.personalize(user, clearance, post_data)

    def __iter__(self):
        """Returns an iterator over all samples and processes.  It is used in
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

        :return:
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
        """Checks whether all “is My Sample” forms of the “show sample” view
        are valid.  Actually, this method is rather silly because the forms
        consist only of checkboxes and they can never be invalid.  But sticking
        to rituals reduces errors …

        :return:
          whether all forms are valid

        :rtype: bool
        """
        all_valid = self.is_my_sample_form.is_valid()
        all_valid = all_valid and all([process_list.is_valid() for process_list in self.process_lists])
        return all_valid

    def save_to_database(self):
        """Changes the members of the “My Samples” list according to what the
        user selected.

        :return:
          names of added samples, names of removed samples

        :rtype: set of str, set of str
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

    def get_all_process_ids(self):
        """Returns all process IDs of this sample.  When child samples are
        shown on the sample's data sheet, too, also their process IDs are
        included.

        :return:
          all process ids of the sample data sheet

        :rtype: set of int
        """
        all_process_ids = self.process_ids
        for process_list in self.process_lists:
            all_process_ids.update(process_list.get_all_process_ids())
        return all_process_ids


def embed_timestamp(request, sample_name):
    """Put a timestamp field in the request object that is used by both
    `sample_timestamp` and `sample_etag`.  It's really a pity that you can't
    give *one* function for returning both with Django's API for conditional
    view processing.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str
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
            timestamps.append(request.user.jb_user_details.layout_last_modified)
            request._sample_timestamp = max(timestamps)


def sample_timestamp(request, sample_name):
    """Calculate the timestamp of a sample.  For this, the timestamp of last
    modification of the sample is taken, and that of other things that
    influence the sample datasheet (language, “My Samples”).  The latest
    timestamp is chosen and returned.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the timestamp of the last modification of the sample's datasheet

    :rtype: datetime.datetime
    """
    embed_timestamp(request, sample_name)
    return request._sample_timestamp


def sample_etag(request, sample_name):
    """Calculate an ETag for the sample datasheet.  For this, the timestamp of
    last modification of the sample is taken, and the primary key of the
    current user.  The checksum of both is returned.

    This routine is necessary because browsers don't handle the "Vary: Cookie"
    header well.  In order to avoid one user getting cached pages of another
    user who used the same browser instance before (e.g. in a lab), I must
    create an ETag.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the ETag of the sample's datasheet

    :rtype: str
    """
    embed_timestamp(request, sample_name)
    if request._sample_timestamp:
        hash_ = hashlib.sha1()
        hash_.update(str(request._sample_timestamp).encode())
        hash_.update(str(request.user.pk).encode())
        return hash_.hexdigest()


@help_link("demo.html#sample-data-sheet")
@login_required
@unquote_view_parameters
@condition(sample_etag, sample_timestamp)
def show(request, sample_name):
    """A view for showing existing samples.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    start = time.time()
    if request.method == "POST":
        samples_and_processes = SamplesAndProcesses.samples_and_processes(sample_name, request.user, request.POST)
        if samples_and_processes.is_valid():
            added, removed = samples_and_processes.save_to_database()
            if is_json_requested(request):
                return respond_in_json(True)
            if added:
                success_message = ungettext("Sample {samples} was added to My Samples.",
                                            "Samples {samples} were added to My Samples.",
                                            len(added)).format(samples=format_enumeration(added))
            else:
                success_message = ""
            if removed:
                if added:
                    success_message += "  "
                success_message += ungettext("Sample {samples} was removed from My Samples.",
                                             "Samples {samples} were removed from My Samples.",
                                             len(removed)).format(samples=format_enumeration(removed))
            elif not added:
                success_message = _("Nothing was changed.")
            messages.success(request, success_message)
    else:
        if is_json_requested(request):
            sample = utils.lookup_sample(sample_name, request.user)
            return respond_in_json(sample.get_data())
        samples_and_processes = SamplesAndProcesses.samples_and_processes(sample_name, request.user)
    messages.debug(request, "DB-Zugriffszeit: {0:.1f} ms".format((time.time() - start) * 1000))
    return render(request, "samples/show_sample.html",
                  {"title": _("Sample “{sample}”").format(sample=samples_and_processes.sample_context["sample"]),
                   "samples_and_processes": samples_and_processes})


@login_required
def by_id(request, sample_id, path_suffix):
    """Pure re-direct view in case a sample is accessed by ID instead of by
    name.  It redirects to the URL with the name.  The query string, if given,
    is passed, too.

    :param request: the current HTTP Request object
    :param sample_id: the numeric ID of the sample
    :param path_suffix: the trailing path, e.g. ``"/split/"``; if you just view
        a sample, it is empty (or only the query string)

    :type request: HttpRequest
    :type sample_id: str
    :type path_suffix: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
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
    permissions.get_sample_clearance(request.user, sample)
    query_string = request.META["QUERY_STRING"] or ""
    return HttpResponseSeeOther(
        django.urls.reverse("samples:show_sample_by_name", kwargs={"sample_name": sample.name}) + path_suffix +
        ("?" + query_string if query_string else ""))


@login_required
@unquote_view_parameters
def add_process(request, sample_name):
    """View for appending a new process to the process list of a sample.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample = utils.lookup_sample(sample_name, request.user)
    sample_processes, general_processes = get_allowed_processes(request.user, sample)
    for process in general_processes:
        process["url"] += "?sample={0}&next={1}".format(urlquote_plus(sample_name), sample.get_absolute_url())
    return render(request, "samples/add_process.html",
                  {"title": _("Add process to sample “{sample}”").format(sample=sample),
                   "processes": sample_processes + general_processes})


class SearchSamplesForm(forms.Form):
    """Form for searching for samples.  So far, you can only enter a name
    substring for looking for samples.
    """
    name_pattern = forms.CharField(label=_("Name pattern"), max_length=30, required=False)
    aliases = forms.BooleanField(label=_("Include alias names"), required=False)


class AddToMySamplesForm(forms.Form):
    add_to_my_samples = forms.BooleanField(required=False)


max_results = 1000
@login_required
def search(request):
    """View for searching for samples.  The rule is: Everyone can see the
    *names* (not the data sheets) of all samples, unless they are in a
    confidential topic, unless the user is a member in that topic, its
    currently responsible person, or you have a clearance for the sample.

    A POST request on this URL will add samples to the “My Samples” list.
    *All* search parameters are in the query string, so if you just want to
    search, this is a GET requets.  Therefore, this view has two submit
    buttons.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    too_many_results = False
    base_query = utils.restricted_samples_query(request.user)
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
        sample_ids = {int_or_zero(key.partition("-")[0]) for key, value in request.POST.items() if value == "on"}
        samples = base_query.in_bulk(sample_ids).values()
        request.user.my_samples.add(*samples)
    add_to_my_samples_forms = [AddToMySamplesForm(prefix=str(sample.pk)) if sample not in my_samples else None
                               for sample in found_samples]
    return render(request, "samples/search_samples.html", {"title": _("Search for sample"),
                                                           "search_samples": search_samples_form,
                                                           "found_samples": list(zip(found_samples, add_to_my_samples_forms)),
                                                           "too_many_results": too_many_results,
                                                           "max_results": max_results})


@help_link("demo.html#advanced-search")
@login_required
def advanced_search(request):
    """View for searching for samples, sample series, physical processes, and
    results.  The visibility rules of the search results are the same as for
    the sample search.  Additionally, you can only see sample series you are
    the currently responsible person of or that are in one of your topics.

    A POST request on this URL will add samples to the “My Samples” list.
    *All* search parameters are in the query string, so if you just want to
    search, this is a GET requets.  Therefore, this view has two submit
    buttons.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    model_list = [model for model in jb_common.search.get_all_searchable_models() if hasattr(model, "get_absolute_url")]
    search_tree = None
    results, add_forms = [], []
    too_many_results = False
    root_form = jb_common.search.SearchModelForm(model_list, request.GET)
    search_performed = False
    no_permission_message = None
    _search_parameters_hash = hashlib.sha1(json.dumps(sorted(
        {key: value for key, value in request.GET.items() if not "__" in key and key != "_search_parameters_hash"}
        .items())).encode()).hexdigest()
    column_groups_form = columns_form = table = switch_row_forms = old_data_form = None
    if root_form.is_valid() and root_form.cleaned_data["_model"]:
        search_tree = get_all_models()[root_form.cleaned_data["_model"]].get_search_tree_node()
        parse_tree = root_form.cleaned_data["_model"] == root_form.cleaned_data["_old_model"]
        search_tree.parse_data(request.GET if parse_tree else None, "")
        if search_tree.is_valid():
            if search_tree.model_class == models.Sample:
                base_query = utils.restricted_samples_query(request.user)
            elif search_tree.model_class == models.SampleSeries:
                base_query = models.SampleSeries.objects.filter(
                    Q(topic__confidential=False) | Q(topic__members=request.user) |
                    Q(currently_responsible_person=request.user)).distinct()
            else:
                base_query = None
            results, too_many_results = jb_common.search.get_search_results(search_tree, max_results, base_query)
            if search_tree.model_class == models.Sample:
                if request.method == "POST":
                    sample_ids = {int_or_zero(key[2:].partition("-")[0]) for key, value in request.POST.items()
                                  if value == "on"}
                    samples = base_query.in_bulk(sample_ids).values()
                    request.user.my_samples.add(*samples)
                my_samples = request.user.my_samples.all()
                add_forms = [AddToMySamplesForm(prefix="0-" + str(sample.pk)) if sample not in my_samples else None
                             for sample in results]
            else:
                add_forms = len(results) * [None]
            if results and root_form.cleaned_data["_search_parameters_hash"] == _search_parameters_hash:
                data_node = data_tree.DataNode(_("search results"))
                for result in results:
                    insert = False
                    if isinstance(result, models.PhysicalProcess) \
                        and permissions.has_permission_to_view_physical_process(request.user, result):
                            insert = True
                    elif isinstance(result, models.Result) \
                        and permissions.has_permission_to_view_result_process(request.user, result):
                            insert = True
                    elif isinstance(result, models.Sample) \
                        and permissions.has_permission_to_fully_view_sample(request.user, result):
                            insert = True
                    elif isinstance(result, models.SampleSeries) \
                        and permissions.has_permission_to_view_sample_series(request.user, result):
                            insert = True
                    if insert:
                        data_node.children.append(result.get_data_for_table_export())
                if len(data_node.children) == 0:
                    no_permission_message = _("You don't have the permission to see any content of the search results.")
                else:
                    export_result = utils.table_export(request, data_node, "")
                    if isinstance(export_result, tuple):
                        column_groups_form, columns_form, table, switch_row_forms, old_data_form = export_result
                    elif isinstance(export_result, HttpResponse):
                        return export_result
            search_performed = True
        root_form = jb_common.search.SearchModelForm(
            model_list, initial={"_old_model": root_form.cleaned_data["_model"], "_model": root_form.cleaned_data["_model"],
                                 "_search_parameters_hash": _search_parameters_hash})
    else:
        root_form = jb_common.search.SearchModelForm(model_list)
    root_form.fields["_model"].label = ""
    content_dict = {"title": capfirst(_("advanced search")), "search_root": root_form, "search_tree": search_tree,
                    "results": list(zip(results, add_forms)), "search_performed": search_performed,
                    "something_to_add": any(add_forms), "too_many_results": too_many_results, "max_results": max_results,
                    "column_groups": column_groups_form, "columns": columns_form, "old_data": old_data_form,
                    "rows": list(zip(table, switch_row_forms)) if table else None,
                    "no_permission_message": no_permission_message}
    return render(request, "samples/advanced_search.html", content_dict)


@login_required
@unquote_view_parameters
def export(request, sample_name):
    """View for exporting sample data in CSV or JSON format.  Thus, the return
    value is not an HTML response.

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample = utils.lookup_sample(sample_name, request.user)
    data = sample.get_data_for_table_export()
    result = utils.table_export(request, data, _("process"))
    if isinstance(result, tuple):
        column_groups_form, columns_form, table, switch_row_forms, old_data_form = result
    elif isinstance(result, HttpResponse):
        return result
    title = _("Table export for “{name}”").format(name=data.descriptive_name)
    return render(request, "samples/table_export.html", {"title": title, "column_groups": column_groups_form,
                                                         "columns": columns_form,
                                                         "rows": list(zip(table, switch_row_forms)) if table else None,
                                                         "old_data": old_data_form,
                                                         "backlink": request.GET.get("next", "")})


def qr_code(request):
    """Generates the QR representation of the given data.  The data is given
    in the ``data`` query string parameter.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    try:
        data = request.GET["data"]
    except KeyError:
        raise Http404('GET parameter "data" missing.')
    return render(request, "samples/qr_code.html", {"title": _("QR code"), "data": data})


def data_matrix_code(request):
    """Generates the Data Matrix representation of the given data.  The data
    is given in the ``data`` query string parameter.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    raise Http404()
    # FixMe: This non-working currently because it write the dara matrix PNG
    # into STATIC_ROOT.  It is poorly coded for two reasons: First, STATIC_ROOT
    # may not exist because another system is serving static content.  And
    # Secondly, retrieving the actual PNG must also work even if the
    # corresponding HTML has not been retrieved yet.
    try:
        data = request.GET["data"]
    except KeyError:
        raise Http404('GET parameter "data" missing.')
    hash_ = hashlib.sha1()
    hash_.update(data.encode())
    filename = hash_.hexdigest() + ".png"
    filepath = os.path.join(settings.STATIC_ROOT, "data_matrix", filename)
    url = staticfiles_storage.url("data_matrix/" + filename)
    if not os.path.exists(filepath):
        mkdirs(filepath)
        image = PIL.Image.open(BytesIO(urllib.urlopen(
                    "http://www.bcgen.com/demo/IDAutomationStreamingDataMatrix.aspx?"
                    "MODE=3&D={data}&PFMT=6&PT=F&X=0.13&O=0&LM=0".format(data=urlquote_plus(data, safe="/"))).read()))
        image = image.crop((38, 3, 118, 83))
        image = PIL.ImageOps.expand(image, border=16, fill=256).convert("1")
        image.save(filepath)
        storage_changed.send(data_matrix_code)
    return render(request, "samples/data_matrix_code.html", {"title": _("Data Matrix code"),
                                                             "data_matrix_url": url,
                                                             "data": data})


class SampleRenameForm(forms.Form):
    """Form for rename a sample.
    """
    old_name = forms.CharField(label=capfirst(_("old sample name")), max_length=30, required=True)
    new_name = forms.CharField(label=capfirst(_("new sample name")), max_length=30, required=True)
    create_alias = forms.BooleanField(label=capfirst(_("keep old name as sample alias name")),
                                      required=False)

    def __init__(self, user, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.user = user

    def clean_old_name(self):
        old_name = self.cleaned_data["old_name"]
        try:
            sample = models.Sample.objects.get(name=old_name)
        except models.Sample.DoesNotExist:
            raise ValidationError(_("This sample does not exist."), code="invalid")
        if not permissions.has_permission_to_rename_sample(self.user, sample):
            raise ValidationError(_("You are not allowed to rename the sample."), code="invalid")
        return old_name

    def clean_new_name(self):
        new_name = self.cleaned_data["new_name"]
        name_format, match = sample_names.sample_name_format(new_name, with_match_object=True)
        if name_format is None:
            raise ValidationError(_("This sample name is not valid."), code="invalid")
        utils.check_sample_name(match, self.user)
        if sample_names.does_sample_exist(new_name):
            raise ValidationError(_("This sample name exists already."), code="duplicate")
        return new_name

    def clean(self):
        cleaned_data = super().clean()
        old_name = cleaned_data.get("old_name")
        new_name = cleaned_data.get("new_name")
        if old_name is not None and new_name is not None:
            if new_name == old_name:
                self.add_error("new_name", ValidationError(_("The new name must be different from the old name."),
                                                           code="invalid"))
            old_name_format = sample_names.sample_name_format(old_name)
            possible_new_name_formats = settings.SAMPLE_NAME_FORMATS[old_name_format].get("possible_renames", set()) \
                if old_name_format else set()
            name_format = sample_names.sample_name_format(new_name)
            if name_format not in possible_new_name_formats:
                error_message = ungettext("New name must be a valid “%(sample_formats)s” name.",
                                          "New name must be a valid name of one of these types: %(sample_formats)s.",
                                          len(possible_new_name_formats))
                self.add_error("new_name", ValidationError(
                    error_message,
                    params={"sample_formats": format_enumeration(
                        sample_names.verbose_sample_name_format(name_format) for name_format in possible_new_name_formats)},
                    code="invalid"))

        return cleaned_data


@login_required
def rename_sample(request):
    """Rename a sample given by its id.  Note that for bulk renames (usually
    immediately after sample creation), there exists
    ``samples.views.bulk_rename.bulk_rename``.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample_id = request.GET.get("sample_id")
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_id)) if sample_id else None
    if request.method == "POST":
        sample_rename_form = SampleRenameForm(request.user, request.POST)
        if sample_rename_form.is_valid():
            old_name = sample_rename_form.cleaned_data["old_name"]
            sample = models.Sample.objects.get(name=old_name)
            permissions.assert_can_rename_sample(request.user, sample)
            sample.name = sample_rename_form.cleaned_data["new_name"]
            sample.save()
            if sample_rename_form.cleaned_data["create_alias"] and \
               not models.SampleAlias.objects.filter(name=old_name, sample=sample).exists():
                models.SampleAlias.objects.create(name=old_name, sample=sample)
            feed_reporter = utils.Reporter(request.user)
            feed_reporter.report_edited_samples([sample], {"important": True,
               "description": _("Sample {old_name} was renamed to {new_name}").
                                                           format(new_name=sample.name, old_name=old_name)})
            return utils.successful_response(
                request, _("Sample {sample} was successfully changed in the database.").format(sample=sample))
    else:
        sample_rename_form = SampleRenameForm(request.user, initial={"old_name": sample.name if sample else ""})
    title = capfirst(_("rename sample")) + " “{sample}”".format(sample=sample) if sample else ""
    return render(request, "samples/rename_sample.html", {"title": title, "sample_rename": sample_rename_form})


_ = ugettext
