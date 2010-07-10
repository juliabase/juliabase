#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for editing Chantal topics in various ways.  You may add topics,
get a list of them, and change user memberships in topics.  The list of
topics is actually only a stepping stone to the membership edit view.
"""

from __future__ import absolute_import

from django.shortcuts import render_to_response, get_object_or_404
from django.http import Http404
import django.utils.http
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.utils.translation import ugettext as _, ugettext_lazy
import django.forms as forms
from django.forms.util import ValidationError
from chantal_common.utils import append_error
from chantal_common.models import Topic
from samples import models, permissions
from samples.views import utils, feed_utils, form_utils


class NewTopicForm(forms.Form):
    u"""Form for adding a new topic.  I need only its new name and restriction
    status.
    """
    _ = ugettext_lazy
    new_topic_name = forms.CharField(label=_(u"Name of new topic"), max_length=80)
    # Translation hint: Topic which is not open to senior members
    restricted = forms.BooleanField(label=_(u"restricted"), required=False)
    def __init__(self, *args, **kwargs):
        super(NewTopicForm, self).__init__(*args, **kwargs)
        self.fields["new_topic_name"].widget.attrs["size"] = 40
    def clean_new_topic_name(self):
        topic_name = self.cleaned_data["new_topic_name"]
        topic_name = u" ".join(topic_name.split())
        if Topic.objects.filter(name=topic_name).exists():
            raise ValidationError(_(u"This topic name is already used."))
        return topic_name


@login_required
def add(request):
    u"""View for adding a new topic.  This action is only allowed to the heads
    of institute topics.  The name of topics may contain arbitrary characters.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_edit_topic(request.user)
    if request.method == "POST":
        new_topic_form = NewTopicForm(request.POST)
        if new_topic_form.is_valid():
            new_topic = Topic(name=new_topic_form.cleaned_data["new_topic_name"],
                                  restricted=new_topic_form.cleaned_data["restricted"])
            new_topic.save()
            request.user.topics.add(new_topic)
            request.user.samples_user_details.auto_addition_topics.add(new_topic)
            return utils.successful_response(
                request, _(u"Topic %s was successfully created.") % new_topic.name, "samples.views.topic.edit",
                kwargs={"name": django.utils.http.urlquote(new_topic.name, safe="")})
    else:
        new_topic_form = NewTopicForm()
    return render_to_response("samples/add_topic.html", {"title": _(u"Add new topic"), "new_topic": new_topic_form},
                              context_instance=RequestContext(request))


@login_required
def list_(request):
    u"""View for a complete list of all topics that the user can edit.  The
    user may select one, which leads him to the membership view for this topic.
    If the user can't edit any topic, a 404 is raised.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user = request.user
    all_topics = Topic.objects.all()
    user_topics = user.topics.all()
    topics = set(topic for topic in all_topics if permissions.has_permission_to_edit_topic(user, topic))
    if not topics:
        raise Http404(u"Can't find any topic that you can edit.")
    return render_to_response("samples/list_topics.html", {"title": _(u"List of all topics"), "topics": topics},
                              context_instance=RequestContext(request))


class EditTopicForm(forms.Form):
    u"""Form for the member list of a topic.  Note that it is allowed to have
    no members at all in a topic.  However, if the topic is restricted, the
    currently logged-in user must remain a member of the topic.
    """
    members = form_utils.MultipleUsersField(label=_(u"Members"), required=False)
    restricted = forms.BooleanField(label=_(u"restricted"), required=False)

    def __init__(self, user, topic, *args, **kwargs):
        super(EditTopicForm, self).__init__(*args, **kwargs)
        self.fields["members"].set_users(topic.members.all())
        self.fields["restricted"].initial = topic.restricted
        self.user = user
        self.topic = topic

    def clean(self):
        cleaned_data = self.cleaned_data
        if "members" in cleaned_data and "restricted" in cleaned_data:
            if cleaned_data["restricted"] and \
                    not any(permissions.has_permission_to_edit_topic(user, self.topic) for user in cleaned_data["members"]):
                append_error(self, _(u"In restricted topics, at least one member must have permission to edit the topic."),
                             "members")
        return cleaned_data


@login_required
def edit(request, name):
    u"""View for changing the members of a particular topic, and to set the
    restriction status.  This is only allowed to heads of institute groups and
    topic managers.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: the name of the topic

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    topic = get_object_or_404(Topic, name=name)
    permissions.assert_can_edit_topic(request.user, topic)
    if request.method == "POST":
        edit_topic_form = EditTopicForm(request.user, topic, request.POST)
        added_members = []
        removed_members = []
        if edit_topic_form.is_valid():
            old_members = list(topic.members.all())
            new_members = edit_topic_form.cleaned_data["members"]
            topic.members = new_members
            topic.restricted = edit_topic_form.cleaned_data["restricted"]
            for user in new_members:
                if user not in old_members:
                    added_members.append(user)
                    topic.auto_adders.add(user.samples_user_details)
            for user in old_members:
                if user not in new_members:
                    removed_members.append(user)
                    topic.auto_adders.remove(user.samples_user_details)
            if added_members:
                feed_utils.Reporter(request.user).report_changed_topic_membership(added_members, topic, "added")
            if removed_members:
                feed_utils.Reporter(request.user).report_changed_topic_membership(removed_members, topic, "removed")
            return utils.successful_response(request,
                                             _(u"Members of topic “%s” were successfully updated.") % topic.name)
    else:
        edit_topic_form = \
            EditTopicForm(request.user, topic, initial={"members": topic.members.values_list("pk", flat=True)})
    return render_to_response("samples/edit_topic.html",
                              {"title": _(u"Change topic memberships of “%s”") % name,
                               "edit_topic": edit_topic_form},
                              context_instance=RequestContext(request))
