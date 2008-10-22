#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for editing and creating comments (a result process).
"""

import datetime
from django.template import RequestContext
from django.http import Http404
import django.forms as forms
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from django.db.models import Q
from chantal.samples import models, permissions
from chantal.samples.views import utils

class EditCommentForm(forms.Form):
    u"""Form for editing the contents of a comment.
    """
    _ = ugettext_lazy
    contents = forms.CharField(label=_(u"Contents"), widget=forms.Textarea)

@login_required
def edit(request, process_id):
    u"""View for editing existing comments.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the ID of the comment process

    :type request: ``HttpRequest``
    :type process_id: str

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    comment = get_object_or_404(models.Comment, pk=utils.convert_id_to_int(process_id))
    permissions.assert_can_edit_result_process(request.user, comment)
    if request.method == "POST":
        comment_form = EditCommentForm(request.POST)
        if comment_form.is_valid():
            comment.comments = comment_form.cleaned_data["contents"]
            comment.save()
            return utils.successful_response(request)
    else:
        comment_form = EditCommentForm(initial={"contents": comment.comments})
    return render_to_response("edit_comment.html", {"title": _(u"Edit comment"), "is_new": False, "comment": comment_form},
                              context_instance=RequestContext(request))

class NewCommentForm(forms.Form):
    u"""Form for adding a new comment.  It is more complicated than the form
    for editing existing comments because the samples and sample series a
    comment is connected with can't be changed anymore.
    """
    _ = ugettext_lazy
    contents = forms.CharField(label=_(u"Contents"), widget=forms.Textarea)
    samples = forms.ModelMultipleChoiceField(label=_(u"Samples"), queryset=None, required=False)
    sample_series = forms.ModelMultipleChoiceField(label=_(u"Sample series"), queryset=None, required=False)
    def __init__(self, user_details, query_string_dict, data=None, **keyw):
        u"""Form constructor.  I have to initialise a couple of things here in
        a non-trivial way.

        The most complicated thing is to find all sample series electable for
        the comment.  Note that the current query will probably find to many
        electable sample series, but unallowed series will be rejected by
        `is_referentially_valid` anyway.
        """
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
    u"""Test whether the comment form is consistent with the database.  In
    particular, it tests whether the user is allowed to add the comment to all
    selected samples and sample series.

    :Return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if not utils.get_allowed_result_processes(user, comment_form.cleaned_data["samples"],
                                              comment_form.cleaned_data["sample_series"]):
        referentially_valid = False
        utils.append_error(comment_form,
                           _(u"You don't have the permission to add the result to all selected samples/series."))
    if not comment_form.cleaned_data["samples"] and not comment_form.cleaned_data["sample_series"]:
        referentially_valid = False
        utils.append_error(comment_form, _(u"You must select at least one samples/series."))
    return referentially_valid
            
@login_required
def new(request):
    u"""View for adding a new comment.  This routine also contains the full
    code for creating the forms, checking validity with ``is_valid``, and
    saving it to the database (bcause it's just so trivial for comments).

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user_details = utils.get_profile(request.user)
    query_string_dict = utils.parse_query_string(request)
    if request.method == "POST":
        comment_form = NewCommentForm(user_details, query_string_dict, request.POST)
        if comment_form.is_valid() and is_referentially_valid(comment_form, request.user):
            comment = models.Comment(operator=request.user, timestamp=datetime.datetime.now(),
                                     comments=comment_form.cleaned_data["contents"])
            comment.save()
            comment.samples = comment_form.cleaned_data["samples"]
            comment.sample_series = comment_form.cleaned_data["sample_series"]
            return utils.successful_response(request)
    else:
        comment_form = NewCommentForm(user_details, query_string_dict)
    return render_to_response("edit_comment.html", {"title": _(u"New comment"), "is_new": True, "comment": comment_form},
                              context_instance=RequestContext(request))
