#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
from django.template import RequestContext
from django.http import HttpResponseRedirect, Http404
import django.forms as forms
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from django.db.models import Q
from chantal.samples import models
from . import utils

class EditCommentForm(forms.Form):
    _ = ugettext_lazy
    contents = forms.CharField(label=_(u"Contents"), widget=forms.Textarea)

@login_required
def edit(request, process_id):
    comment = get_object_or_404(models.Comment, pk=utils.convert_id_to_int(process_id))
    if request.user != comment.operator or \
            not utils.can_edit_result_processes(request.user, comment.samples.all(), comment.sample_series.all()):
        return HttpResponseRedirect("permission_error")
    if request.method == "POST":
        comment_form = EditCommentForm(request.POST)
        if comment_form.is_valid():
            comment.contents = comment_form.cleaned_data["contents"]
            comment.save()
            return HttpResponseRedirect("../../"+utils.parse_query_string(request).get("next", ""))
    else:
        comment_form = EditCommentForm(initial={"contents": comment.contents})
    return render_to_response("edit_comment.html", {"title": _(u"Edit comment"), "is_new": False, "comment": comment_form},
                              context_instance=RequestContext(request))

class NewCommentForm(forms.Form):
    _ = ugettext_lazy
    contents = forms.CharField(label=_(u"Contents"), widget=forms.Textarea)
    samples = forms.ModelMultipleChoiceField(label=_(u"Samples"), queryset=None, required=False)
    sample_series = forms.ModelMultipleChoiceField(label=_(u"Sample series"), queryset=None, required=False)
    def __init__(self, user_details, query_string_dict, data=None, **keyw):
        super(NewCommentForm, self).__init__(data, **keyw)
        self.fields["samples"].queryset = \
            models.Sample.objects.filter(Q(watchers=user_details) | Q(name=query_string_dict.get("sample"))).distinct()
        if "sample" in query_string_dict:
            try:
                self.fields["samples"].initial = [models.Sample.objects.get(name=query_string_dict["sample"])._get_pk_val()]
            except models.Sample.DoesNotExist:
                raise Http404(u"sample %s given in query string not found" % query_string_dict["sample"])
        now = datetime.datetime.now() + datetime.timedelta(seconds=5)
        three_months_ago = now - datetime.timedelta(days=90)
        self.fields["sample_series"].queryset = \
            models.SampleSeries.objects.filter(Q(samples__watchers=user_details) |
                                               ( Q(currently_responsible_person=user_details.user) &
                                                 Q(timestamp__range=(three_months_ago, now)))
                                               | Q(name=query_string_dict.get("sample_series"))).distinct()
        self.fields["sample_series"].initial = [query_string_dict.get("sample_series")]

def is_referentially_valid(comment_form, user):
    referentially_valid = True
    if not utils.can_edit_result_processes(user, comment_form.cleaned_data["samples"],
                                           comment_form.cleaned_data["sample_series"]):
        referentially_valid = False
        utils.append_error(comment_form, "__all__",
                           _(u"You don't have the permission to add the result to all selected samples/series."))
    if not comment_form.cleaned_data["samples"] and not comment_form.cleaned_data["sample_series"]:
        referentially_valid = False
        utils.append_error(comment_form, "__all__", _(u"You must select at least one samples/series."))
    return referentially_valid
            
@login_required
def new(request):
    user_details = request.user.get_profile()
    query_string_dict = utils.parse_query_string(request)
    if request.method == "POST":
        comment_form = NewCommentForm(user_details, query_string_dict, request.POST)
        if comment_form.is_valid() and is_referentially_valid(comment_form, request.user):
            comment = models.Comment(operator=request.user, timestamp=datetime.datetime.now(),
                                     contents=comment_form.cleaned_data["contents"])
            comment.save()
            comment.samples = comment_form.cleaned_data["samples"]
            comment.sample_series = comment_form.cleaned_data["sample_series"]
            return HttpResponseRedirect("../../"+query_string_dict.get("next", ""))
    else:
        comment_form = NewCommentForm(user_details, query_string_dict)
    return render_to_response("edit_comment.html", {"title": _(u"New comment"), "is_new": True, "comment": comment_form},
                              context_instance=RequestContext(request))
