#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time, datetime
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404
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
    _ = ugettext_lazy
    is_my_sample = forms.BooleanField(label=_(u"is amongst My Samples"), required=False)

class SampleForm(forms.ModelForm):
    _ = ugettext_lazy
    currently_responsible_person = utils.OperatorChoiceField(label=_(u"Currently responsible person"),
                                                             queryset=django.contrib.auth.models.User.objects.all())
    class Meta:
        model = models.Sample
        exclude = ("name", "split_origin", "processes")

@login_required
def edit(request, sample_name):
    sample, redirect = utils.lookup_sample(sample_name, request)
    if redirect:
        return redirect
    old_group, old_responsible_person = sample.group, sample.currently_responsible_person
    if sample.currently_responsible_person != request.user:
        return utils.HttpResponseSeeOther("permission_error")
    user_details = request.user.get_profile()
    if request.method == "POST":
        sample_form = SampleForm(request.POST, instance=sample)
        if sample_form.is_valid():
            sample = sample_form.save()
            if sample.group and sample.group != old_group:
                for user in sample.group.user_set.all():
                    user.get_profile().my_samples.add(sample)
            if sample.currently_responsible_person != old_responsible_person:
                sample.currently_responsible_person.get_profile().my_samples.add(sample)
            request.session["success_report"] = _(u"Sample %s was successfully changed in the database.") % sample.name
            return utils.HttpResponseSeeOther(utils.parse_query_string(request).get("next", sample.get_absolute_url()))
    else:
        sample_form = SampleForm(instance=sample)
    return render_to_response("edit_sample.html", {"title": _(u"Edit sample “%s”") % sample.name,
                                                   "sample_name": sample.name, "sample": sample_form},
                              context_instance=RequestContext(request))

def get_allowed_processes(user, sample):
    processes = []
    processes.extend(utils.get_allowed_result_processes(user, samples=[sample]))
    if sample.currently_responsible_person == user:
        processes.append({"name": _(u"split"), "link": sample.get_absolute_url() + "/split/"})
        # FixMe: Add sample death
    # FixMe: Add other processes, deposition, measurements, if the user is allowed to do it
    return processes

@login_required
def show(request, sample_name):
    start = time.time()
    sample, redirect = utils.lookup_sample(sample_name, request)
    if redirect:
        return redirect
    user_details = request.user.get_profile()
    if request.method == "POST":
        is_my_sample_form = IsMySampleForm(request.POST)
        if is_my_sample_form.is_valid():
            if is_my_sample_form.cleaned_data["is_my_sample"]:
                user_details.my_samples.add(sample)
                request.session["success_report"] = _(u"Sample %s was added to Your Samples.") % sample.name
            else:
                user_details.my_samples.remove(sample)
                request.session["success_report"] = _(u"Sample %s was removed from Your Samples.") % sample.name
    else:
        start = time.time()
        is_my_sample_form = IsMySampleForm(initial={"is_my_sample": sample in user_details.my_samples.all()})
        request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    processes = utils.ProcessContext(request.user, sample).collect_processes()
    request.session["db_access_time_in_ms"] = "%.1f" % ((time.time() - start) * 1000)
    return render_to_response("show_sample.html", {"processes": processes, "sample": sample,
                                                   "can_edit": request.user == sample.currently_responsible_person,
                                                   # FixMe: calling get_allowed_processes is too expensive
                                                   "can_add_process": bool(get_allowed_processes(request.user, sample)),
                                                   "is_my_sample_form": is_my_sample_form},
                              context_instance=RequestContext(request))

class AddSamplesForm(forms.Form):
    _ = ugettext_lazy
    number_of_samples = forms.IntegerField(label=_(u"Number of samples"), min_value=1, max_value=100)
    substrate = forms.ChoiceField(label=_(u"Substrate"), choices=models.substrate_materials)
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
    substrate = models.Substrate(operator=user, timestamp=datetime.datetime.now(),
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
    user_details = add_samples_form.cleaned_data["currently_responsible_person"].get_profile()
    new_names = [u"*%d" % i for i in range(starting_number, starting_number + number_of_samples)]
    for new_name in new_names:
        sample = models.Sample(name=new_name,
                               current_location=add_samples_form.cleaned_data["current_location"],
                               currently_responsible_person=add_samples_form.cleaned_data["currently_responsible_person"],
                               purpose=add_samples_form.cleaned_data["purpose"],
                               tags=add_samples_form.cleaned_data["tags"],
                               group=add_samples_form.cleaned_data["group"])
        sample.save()
        sample.processes.add(substrate)
        user_details.my_samples.add(sample)
    return new_names

@login_required
@check_permission("add_sample")
def add(request):
    user_details = request.user.get_profile()
    if request.method == "POST":
        add_samples_form = AddSamplesForm(user_details, request.POST)
        if add_samples_form.is_valid():
            new_names = add_samples_to_database(add_samples_form, request.user)
            if len(new_names) > 1:
                request.session["success_report"] = \
                    _(u"Your samples have the provisional names from %(first_name)s to "
                      u"%(last_name)s.  They were added to “My Samples”.") % \
                      {"first_name": new_names[0], "last_name": new_names[-1]}
            else:
                request.session["success_report"] = _(u"Your sample has the provisional name %s.  "
                                                      u"It was added to “My Samples”.") % new_names[0]
            return utils.http_response_go_next(request)
    else:
        add_samples_form = AddSamplesForm(user_details)
    return render_to_response("add_samples.html",
                              {"title": _(u"Add samples"),
                               "add_samples": add_samples_form},
                              context_instance=RequestContext(request))

@login_required
def add_process(request, sample_name):
    sample, redirect = utils.lookup_sample(sample_name, request)
    if redirect:
        return redirect
    user_details = request.user.get_profile()
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
    _ = ugettext_lazy
    name_pattern = forms.CharField(label=_(u"Name pattern"), max_length=30)

max_results = 50
@login_required
def search(request):
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
