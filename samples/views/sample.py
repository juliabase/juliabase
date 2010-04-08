#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""All views and helper routines directly connected with samples themselves
(no processes!).  This includes adding, editing, and viewing samples.
"""

from __future__ import absolute_import

import time, datetime
from django.db import transaction, IntegrityError
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
import django.forms as forms
from samples.models import Sample
from samples import models, permissions
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django.contrib import messages
from django.utils.http import urlquote_plus
import django.core.urlresolvers
from chantal_common.utils import append_error, get_really_full_name, HttpResponseSeeOther
from samples.views import utils, form_utils, feed_utils, csv_export
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext


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
    project = form_utils.ProjectField(label=_(u"Project"), required=False)

    def __init__(self, user, *args, **kwargs):
        super(SampleForm, self).__init__(*args, **kwargs)
        self.fields["project"].set_projects(user, kwargs["instance"].project if kwargs.get("instance") else None)
        self.fields["currently_responsible_person"].set_users(
            kwargs["instance"].currently_responsible_person if kwargs.get("instance") else None)

    class Meta:
        model = models.Sample
        exclude = ("name", "split_origin", "processes")


def is_referentially_valid(sample, sample_form, edit_description_form):
    u"""Checks that the “important” checkbox is marked if the project or the
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
            (sample_form.cleaned_data["project"] != sample.project or
             sample_form.cleaned_data["currently_responsible_person"] != sample.currently_responsible_person) and \
             not edit_description_form.cleaned_data["important"]:
        referentially_valid = False
        append_error(edit_description_form,
                     _(u"Changing the project or the responsible person must be marked as important."), "important")
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
    sample = utils.lookup_sample(sample_name, request)
    permissions.assert_can_edit_sample(request.user, sample)
    old_project, old_responsible_person = sample.project, sample.currently_responsible_person
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
            if sample.project and sample.project != old_project:
                for watcher in sample.project.auto_adders.all():
                    watcher.my_samples.add(sample)
                feed_reporter.report_changed_sample_project([sample], old_project, edit_description_form.cleaned_data)
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
                                                  u"nor in its project, nor do you have special permissions for a "
                                                  u"physical process.") % sample, new_project_would_help=True)
    return sample_processes, general_processes


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
    sample = utils.lookup_sample(sample_name, request)
    user_details = utils.get_profile(request.user)
    if request.method == "POST":
        is_my_sample_form = IsMySampleForm(request.POST)
        if is_my_sample_form.is_valid():
            if is_my_sample_form.cleaned_data["is_my_sample"]:
                user_details.my_samples.add(sample)
                if is_remote_client:
                    return utils.respond_to_remote_client(True)
                else:
                    messages.success(request, _(u"Sample %s was added to Your Samples.") % sample)
            else:
                user_details.my_samples.remove(sample)
                if is_remote_client:
                    return utils.respond_to_remote_client(True)
                else:
                    messages.success(request, _(u"Sample %s was removed from Your Samples.") % sample)
    else:
        is_my_sample_form = IsMySampleForm(
            initial={"is_my_sample": user_details.my_samples.filter(id__exact=sample.id).count()})
    processes = utils.ProcessContext(request.user, sample).collect_processes()
    messages.debug(request, "DB-Zugriffszeit: %.1f ms" % ((time.time() - start) * 1000))
    try:
        # FixMe: calling get_allowed_processes is too expensive
        get_allowed_processes(request.user, sample)
        can_add_process = True
    except permissions.PermissionError:
        can_add_process = False
    can_edit = permissions.has_permission_to_edit_sample(request.user, sample)
    number_for_rename = sample.name[1:] if sample.name.startswith("*") and can_edit else None
    return render_to_response("samples/show_sample.html", {"processes": processes, "sample": sample,
                                                           "can_edit": can_edit,
                                                           "number_for_rename": number_for_rename,
                                                           "can_add_process": can_add_process,
                                                           "is_my_sample_form": is_my_sample_form},
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
    permissions.assert_can_view_sample(request.user, sample)
    query_string = request.META["QUERY_STRING"] or u""
    return HttpResponseSeeOther(
        django.core.urlresolvers.reverse("show_sample_by_name", kwargs={"sample_name": sample.name}) + path_suffix +
        ("?" + query_string if query_string else u""))

    
class AddSamplesForm(forms.Form):
    u"""Form for adding new samples.

    FixMe: Although this form can never represent *one* sample but allows the
    user to add arbitrary samples with the same properties (except for the name
    of course), this should be converted to a *model* form in order to satisfy
    the dont-repeat-yourself principle.
    """
    _ = ugettext_lazy
    number_of_samples = forms.IntegerField(label=_(u"Number of samples"), min_value=1, max_value=100)
    substrate = forms.ChoiceField(label=_(u"Substrate"), choices=models.substrate_materials + ((u"<>", 9*u"-"),))
    substrate_comments = forms.CharField(label=_(u"Substrate comments"), required=False)
    substrate_originator = forms.ChoiceField(label=_(u"Substrate originator"), required=False)
    timestamp = forms.DateTimeField(label=_(u"timestamp"), initial=datetime.datetime.now())
    timestamp_inaccuracy = forms.IntegerField(required=False)
    current_location = forms.CharField(label=_(u"Current location"), max_length=50)
    purpose = forms.CharField(label=_(u"Purpose"), max_length=80, required=False)
    tags = forms.CharField(label=_(u"Tags"), max_length=255, required=False,
                           help_text=_(u"separated with commas, no whitespace"))
    project = form_utils.ProjectField(label=_(u"Project"), required=False)
    bulk_rename = forms.BooleanField(label=_(u"Give names"), required=False)

    def __init__(self, user, data=None, **kwargs):
        _ = ugettext
        super(AddSamplesForm, self).__init__(data, **kwargs)
        self.fields["project"].set_projects(user)
        self.fields["substrate_comments"].help_text = \
            u"""<span class="markdown-hint">""" + _(u"""with %(markdown_link)s syntax""") \
            % {"markdown_link": u"""<a href="%s">Markdown</a>""" %
               django.core.urlresolvers.reverse("chantal_common.views.markdown_sandbox")} + u"</span>"
        self.fields["substrate_originator"].choices = [(u"<>", get_really_full_name(user))]
        if user.external_contacts.count() > 0:
            for external_operator in user.external_contacts.all():
                self.fields["substrate_originator"].choices.append((external_operator.pk, external_operator.name))
            self.fields["substrate_originator"].required = True
        self.user = user

    def clean_timestamp(self):
        u"""Forbid timestamps that are in the future.
        """
        timestamp = self.cleaned_data["timestamp"]
        if timestamp > datetime.datetime.now():
            raise ValidationError(_(u"The timestamp must not be in the future."))
        return timestamp

    def clean_substrate(self):
        substrate = self.cleaned_data["substrate"]
        return substrate if substrate != u"<>" else None

    def clean_substrate_originator(self):
        u"""Return the cleaned substrate originator.  Note that something is
        returned only if it is an external operator.
        """
        key = self.cleaned_data["substrate_originator"]
        if not key or key == u"<>":
            return None
        return models.ExternalOperator.objects.get(pk=int(key))

    def clean(self):
        _ = ugettext
        cleaned_data = self.cleaned_data
        if "substrate" in cleaned_data and "substrate_comments" in cleaned_data:
            if cleaned_data["substrate"] == "custom" and not cleaned_data["substrate_comments"]:
                append_error(self, _(u"For a custom substrate, you must give substrate comments."), "substrate_comments")
            if cleaned_data["substrate"] == "" and cleaned_data["substrate_comments"]:
                append_error(self, _(u"You selected “no substrate”, so your substrate comments would be lost."),
                             "substrate_comments")
        if "substrate" in cleaned_data and "substrate_originator" in cleaned_data:
            if cleaned_data["substrate"] == "" and cleaned_data["substrate_originator"] != self.user:
                append_error(self,_(u"You selected “no substrate”, so the external originator would be lost."),
                             "substrate_originator")
        return cleaned_data


def add_samples_to_database(add_samples_form, user):
    u"""Create the new samples and add them to the database.  This routine
    consists of two parts: First, it tries to find a consecutive block of
    provisional sample names.  Then, in actuall creates the samples.

    :Parameters:
      - `add_samples_form`: the form with the samples' common data, including
        the substrate
      - `user`: the current user

    :type add_samples_form: `AddSamplesForm`
    :type user: ``django.contrib.auth.models.User``

    :Return:
      the names of the new samples

    :rtype: list of unicode
    """
    if add_samples_form.cleaned_data["substrate"]:
        substrate = models.Substrate.objects.create(operator=user, timestamp=add_samples_form.cleaned_data["timestamp"],
                                                    material=add_samples_form.cleaned_data["substrate"],
                                                    comments=add_samples_form.cleaned_data["substrate_comments"],
                                                    external_operator=add_samples_form.cleaned_data["substrate_originator"])
        inaccuracy = add_samples_form.cleaned_data["timestamp_inaccuracy"]
        if inaccuracy:
            substrate.timestamp_inaccuracy = inaccuracy
            substrate.save()
    else:
        substrate = None
    provisional_sample_names = \
        models.Sample.objects.filter(name__startswith=u"*").values_list("name", flat=True)
    occupied_provisional_numbers = [int(name[1:]) for name in provisional_sample_names]
    occupied_provisional_numbers.sort()
    occupied_provisional_numbers.insert(0, 0)
    number_of_samples = add_samples_form.cleaned_data["number_of_samples"]
    for i in range(len(occupied_provisional_numbers) - 1):
        if occupied_provisional_numbers[i+1] - occupied_provisional_numbers[i] - 1 >= number_of_samples:
            starting_number = occupied_provisional_numbers[i] + 1
            break
    else:
        starting_number = occupied_provisional_numbers[-1] + 1
    user_details = utils.get_profile(user)
    names = [u"*%05d" % i for i in range(starting_number, starting_number + number_of_samples)]
    new_names = []
    samples = []
    for new_name in names:
        sample_project = add_samples_form.cleaned_data["project"]
        sample = models.Sample.objects.create(name=new_name,
                                              current_location=add_samples_form.cleaned_data["current_location"],
                                              currently_responsible_person=user,
                                              purpose=add_samples_form.cleaned_data["purpose"],
                                              tags=add_samples_form.cleaned_data["tags"],
                                              project=sample_project)
        samples.append(sample)
        if substrate:
            sample.processes.add(substrate)
        user_details.my_samples.add(sample)
        if sample_project:
            for watcher in sample_project.auto_adders.all():
                watcher.my_samples.add(sample)
        new_names.append(unicode(sample))
    return new_names, samples


@login_required
def add(request):
    u"""View for adding new samples.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user = request.user
    if request.method == "POST":
        add_samples_form = AddSamplesForm(user, request.POST)
        if add_samples_form.is_valid():
            # FixMe: Find more reliable way to find stared sample names
            max_cycles = 10
            while max_cycles > 0:
                max_cycles -= 1
                try:
                    savepoint_without_samples = transaction.savepoint()
                    new_names, samples = add_samples_to_database(add_samples_form, user)
                except IntegrityError:
                    if max_cycles > 0:
                        transaction.savepoint_rollback(savepoint_without_samples)
                    else:
                        raise
                else:
                    break
            ids = [sample.pk for sample in samples]
            feed_utils.Reporter(user).report_new_samples(samples)
            if add_samples_form.cleaned_data["project"]:
                for watcher in add_samples_form.cleaned_data["project"].auto_adders.all():
                    for sample in samples:
                        watcher.my_samples.add(sample)
            if len(new_names) > 1:
                success_report = \
                    _(u"Your samples have the provisional names from %(first_name)s to "
                      u"%(last_name)s.  They were added to “My Samples”.") % \
                      {"first_name": new_names[0], "last_name": new_names[-1]}
            else:
                success_report = _(u"Your sample has the provisional name %s.  It was added to “My Samples”.") % new_names[0]
            if add_samples_form.cleaned_data["bulk_rename"]:
                return utils.successful_response(request, success_report, "samples.views.bulk_rename.bulk_rename",
                                                 query_string="numbers=" + ",".join(new_name[1:] for new_name in new_names),
                                                 forced=True, remote_client_response=ids)
            else:
                return utils.successful_response(request, success_report, remote_client_response=ids)
    else:
        add_samples_form = AddSamplesForm(user)
    return render_to_response("samples/add_samples.html",
                              {"title": _(u"Add samples"),
                               "add_samples": add_samples_form,
                               "external_operators_available": user.external_contacts.count() > 0},
                              context_instance=RequestContext(request))


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
    sample = utils.lookup_sample(sample_name, request)
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
            found_samples = found_samples.all()[:max_results] if too_many_results else found_samples.all()
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
    sample = utils.lookup_sample(sample_name, request)
    return csv_export.export(request, sample.get_data(), _(u"process"))
