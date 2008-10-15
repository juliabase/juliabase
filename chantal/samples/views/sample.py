#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""All views and helper routines directly connected with samples themselves
(no processes!).  This includes adding, editing, and viewing samples.
"""

import time, datetime, pickle
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.http import Http404, HttpResponse
import django.forms as forms
from chantal.samples.models import Sample
from chantal.samples import models
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django.utils.http import urlquote_plus
from chantal.samples.views import utils
from chantal.samples.views.utils import check_permission
from django.utils.translation import ugettext as _, ugettext_lazy

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
    # FixMe: What about inactive users?
    currently_responsible_person = utils.OperatorChoiceField(label=_(u"Currently responsible person"),
                                                             queryset=django.contrib.auth.models.User.objects.all())
    class Meta:
        model = models.Sample
        exclude = ("name", "split_origin", "processes")

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
    sample, redirect = utils.lookup_sample(sample_name, request)
    if redirect:
        return redirect
    old_group, old_responsible_person = sample.group, sample.currently_responsible_person
    if sample.currently_responsible_person != request.user:
        return utils.HttpResponseSeeOther("permission_error")
    user_details = utils.get_profile(request.user)
    if request.method == "POST":
        sample_form = SampleForm(request.POST, instance=sample)
        if sample_form.is_valid():
            sample = sample_form.save()
            if sample.group and sample.group != old_group:
                for user in sample.group.user_set.all():
                    utils.get_profile(user).my_samples.add(sample)
            if sample.currently_responsible_person != old_responsible_person:
                utils.get_profile(sample.currently_responsible_person).my_samples.add(sample)
            return utils.successful_response(request,
                                             _(u"Sample %s was successfully changed in the database.") % sample.name,
                                             sample.get_absolute_url())
    else:
        sample_form = SampleForm(instance=sample)
    return render_to_response("edit_sample.html", {"title": _(u"Edit sample “%s”") % sample.name,
                                                   "sample_name": sample.name, "sample": sample_form},
                              context_instance=RequestContext(request))

def get_allowed_processes(user, sample):
    u"""Return a list with processes the user is allowed to add to the sample.

    :Parameters:
      - `user`: the current user
      - `sample`: the sample to be edit or displayed

    :type user: ``django.contrib.auth.models.User``
    :type sample: `models.Sample`

    :Return:
      a list with the allowed processes.  Every process is returned as a dict
      with two keys: ``"name"`` and ``"link"``.  ``"name"`` is the
      human-friendly descriptive name of the process, ``"link"`` is the URL to
      the process (processing `sample`!).

    :rtype: list of dict mapping str to unicode/str
    """
    processes = []
    processes.extend(utils.get_allowed_result_processes(user, samples=[sample]))
    if sample.currently_responsible_person == user:
        processes.append({"name": _(u"split"), "link": sample.get_absolute_url() + "/split/"})
        # FixMe: Add sample death
    # FixMe: Add other processes, deposition, measurements, if the user is allowed to do it
    return processes

@login_required
def show(request, sample_name, sample_id=None):
    u"""A view for showing existing samples.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the name of the sample
      - `sample_id`: the id of the sample; only used by the remote client

    :type request: ``HttpRequest``
    :type sample_name: unicode
    :type sample_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    start = time.time()
    if sample_id is None:
        sample, redirect = utils.lookup_sample(sample_name, request)
        if redirect:
            return redirect
    else:
        sample = get_object_or_404(models.Sample, pk=sample_id)
    user_details = utils.get_profile(request.user)
    if request.method == "POST":
        is_my_sample_form = IsMySampleForm(request.POST)
        if is_my_sample_form.is_valid():
            if is_my_sample_form.cleaned_data["is_my_sample"]:
                user_details.my_samples.add(sample)
                if utils.is_remote_client(request):
                    return utils.respond_to_remote_client(True)
                else:
                    request.session["success_report"] = _(u"Sample %s was added to Your Samples.") % sample.name
            else:
                user_details.my_samples.remove(sample)
                if utils.is_remote_client(request):
                    return utils.respond_to_remote_client(True)
                else:
                    request.session["success_report"] = _(u"Sample %s was removed from Your Samples.") % sample.name
    else:
        is_my_sample_form = IsMySampleForm(
            initial={"is_my_sample": user_details.my_samples.filter(id__exact=sample.id).count()})
    processes = utils.ProcessContext(request.user, sample).collect_processes()
    request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    return render_to_response("show_sample.html", {"processes": processes, "sample": sample,
                                                   "can_edit": request.user == sample.currently_responsible_person,
                                                   # FixMe: calling get_allowed_processes is too expensive
                                                   "can_add_process": bool(get_allowed_processes(request.user, sample)),
                                                   "is_my_sample_form": is_my_sample_form},
                              context_instance=RequestContext(request))

class AddSamplesForm(forms.Form):
    u"""Form for adding new samples.

    FixMe: Although this form can never represent *one* sample but allows the
    user to add abritrary samples with the same properties (except for the name
    of course), this should be converted to a *model* form in order to satisfy
    the dont-repeat-yourself principle.
    """
    _ = ugettext_lazy
    number_of_samples = forms.IntegerField(label=_(u"Number of samples"), min_value=1, max_value=100)
    substrate = forms.ChoiceField(label=_(u"Substrate"), choices=models.substrate_materials)
    timestamp = forms.DateTimeField(label=_(u"timestamp"), initial=datetime.datetime.now())
    current_location = forms.CharField(label=_(u"Current location"), max_length=50)
    currently_responsible_person = utils.OperatorChoiceField(label=_(u"Currently responsible person"),
                                                             queryset=django.contrib.auth.models.User.objects)
    purpose = forms.CharField(label=_(u"Purpose"), max_length=80, required=False)
    tags = forms.CharField(label=_(u"Tags"), max_length=255, required=False,
                           help_text=_(u"separated with commas, no whitespace"))
    group = utils.ModelChoiceField(label=_(u"Group"), queryset=django.contrib.auth.models.Group.objects, required=False)
    def __init__(self, user_details, data=None, **keyw):
        super(AddSamplesForm, self).__init__(data, **keyw)
        self.fields["currently_responsible_person"].initial = user_details.user.pk

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
    substrate = models.Substrate(operator=user, timestamp=add_samples_form.cleaned_data["timestamp"],
                                 material=add_samples_form.cleaned_data["substrate"])
    substrate.save()
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
    user_details = utils.get_profile(add_samples_form.cleaned_data["currently_responsible_person"])
    new_names = [u"*%d" % i for i in range(starting_number, starting_number + number_of_samples)]
    ids = []
    for new_name in new_names:
        sample = models.Sample(name=new_name,
                               current_location=add_samples_form.cleaned_data["current_location"],
                               currently_responsible_person=add_samples_form.cleaned_data["currently_responsible_person"],
                               purpose=add_samples_form.cleaned_data["purpose"],
                               tags=add_samples_form.cleaned_data["tags"],
                               group=add_samples_form.cleaned_data["group"])
        sample.save()
        ids.append(sample.pk)
        sample.processes.add(substrate)
        user_details.my_samples.add(sample)
    return new_names, ids

@login_required
@check_permission("add_sample")
def add(request):
    u"""View for adding new samples.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user_details = utils.get_profile(request.user)
    if request.method == "POST":
        add_samples_form = AddSamplesForm(user_details, request.POST)
        if add_samples_form.is_valid():
            new_names, ids = add_samples_to_database(add_samples_form, request.user)
            if len(new_names) > 1:
                success_report = \
                    _(u"Your samples have the provisional names from %(first_name)s to "
                      u"%(last_name)s.  They were added to “My Samples”.") % \
                      {"first_name": new_names[0], "last_name": new_names[-1]}
            else:
                success_report = _(u"Your sample has the provisional name %s.  It was added to “My Samples”.") % new_names[0]
            return utils.successful_response(request, success_report, remote_client_response=ids)
    else:
        add_samples_form = AddSamplesForm(user_details)
    return render_to_response("add_samples.html",
                              {"title": _(u"Add samples"),
                               "add_samples": add_samples_form},
                              context_instance=RequestContext(request))

@login_required
def add_process(request, sample_name):
    u"""View for appending a new process to the process list of a sample.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: the sample of the sample

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample, redirect = utils.lookup_sample(sample_name, request)
    if redirect:
        return redirect
    user_details = utils.get_profile(request.user)
    processes = get_allowed_processes(request.user, sample)
    if not processes:
        return utils.HttpResponseSeeOther("permission_error")
    return render_to_response("add_process.html",
                              {"title": _(u"Add process to sample “%s”" % sample.name),
                               "processes": processes,
                               "query_string": "sample=%s&next=%s" % (urlquote_plus(sample_name),
                                                                      sample.get_absolute_url())},
                              context_instance=RequestContext(request))

class SearchSamplesForm(forms.Form):
    u"""Form for searching for samples.  So far, you can only enter a name
    substring for looking for samples.
    """
    _ = ugettext_lazy
    name_pattern = forms.CharField(label=_(u"Name pattern"), max_length=30)

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
    found_samples = []
    too_many_results = False
    if request.method == "POST":
        search_samples_form = SearchSamplesForm(request.POST)
        if search_samples_form.is_valid():
            found_samples = \
                models.Sample.objects.filter(name__icontains=search_samples_form.cleaned_data["name_pattern"])
            too_many_results = found_samples.count() > max_results
            found_samples = found_samples.all()[:max_results] if too_many_results else found_samples.all()
    else:
        search_samples_form = SearchSamplesForm()
    return render_to_response("search_samples.html", {"title": _(u"Search for sample"),
                                                      "search_samples": search_samples_form,
                                                      "found_samples": found_samples,
                                                      "too_many_results": too_many_results,
                                                      "max_results": max_results},
                              context_instance=RequestContext(request))
