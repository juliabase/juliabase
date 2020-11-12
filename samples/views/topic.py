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


"""Views for editing JuliaBase topics in various ways.  You may add topics, get
a list of them, and change user memberships in topics.  The list of topics is
actually only a stepping stone to the membership edit view.
"""

from django.shortcuts import render, get_object_or_404
from django.http import Http404
import django.utils.http
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext_lazy as _, ugettext
import django.urls
import django.forms as forms
from django.forms.utils import ValidationError
from django.utils.text import capfirst
from jb_common.models import Topic
from jb_common.utils.base import int_or_zero, HttpResponseSeeOther
from jb_common.utils.views import UserField, MultipleUsersField
from samples import permissions
import samples.utils.views as utils


class NewTopicForm(forms.Form):
    """Form for adding a new topic.  I need only its new name and restriction
    status.
    """
    new_topic_name = forms.CharField(label=_("Name of new topic"), max_length=80)
    # Translators: Topic which is not open to senior members
    confidential = forms.BooleanField(label=_("confidential"), required=False)
    parent_topic = forms.ChoiceField(label=_("Upper topic"), required=False)
    topic_manager = UserField(label=capfirst(_("topic manager")))

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_topic_name"].widget.attrs["size"] = 40
        self.user = user
        if user.is_superuser:
            self.fields["parent_topic"].choices = [(topic.pk, topic) for topic in
                                                   Topic.objects.iterator()]
        else:
            self.fields["parent_topic"].choices = [(topic.pk, topic.get_name_for_user(user)) for topic in
                Topic.objects.filter(department=user.jb_user_details.department).iterator()
                if permissions.has_permission_to_edit_topic(user, topic)]
        self.fields["parent_topic"].choices.insert(0, ("", 9 * "-"))
        self.fields["topic_manager"].set_users(user, user)
        self.fields["topic_manager"].initial = user.pk

    def clean_new_topic_name(self):
        topic_name = self.cleaned_data["new_topic_name"]
        topic_name = " ".join(topic_name.split())
        return topic_name

    def clean_parent_topic(self):
        pk = self.cleaned_data.get("parent_topic")
        if pk:
            parent_topic = Topic.objects.get(pk=int(pk))
            if not permissions.has_permission_to_edit_topic(self.user, parent_topic):
                raise ValidationError(_("You are not allowed to edit the topic “%(parent_topic)s”."),
                                      params={"parent_topic": parent_topic.name})
            return parent_topic
        elif not permissions.has_permission_to_edit_topic(self.user):
            raise ValidationError(_("You are only allowed to create sub topics. You have to select an upper topic."),
                                  code="forbidden")

    def clean(self):
        cleaned_data = super().clean()
        parent_topic = cleaned_data.get("parent_topic")
        if "new_topic_name" in cleaned_data:
            topic_name = cleaned_data["new_topic_name"]
            if Topic.objects.filter(name=topic_name, department=self.user.jb_user_details.department,
                                    parent_topic=parent_topic).exists():
                self.add_error("new_topic_name", ValidationError(_("This topic name is already used."), code="duplicate"))
        if parent_topic and parent_topic.manager != cleaned_data.get("topic_manager"):
            self.add_error("topic_manager", ValidationError(
                _("The topic manager must be the topic manager from the upper topic."), code="invalid"))
        return cleaned_data


@login_required
def add(request):
    """View for adding a new topic.  This action is only allowed to the heads
    of institute groups.  The name of topics may contain arbitrary characters.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    permissions.assert_can_edit_users_topics(request.user)
    if not request.user.jb_user_details.department:
        if request.user.is_superuser:
            return HttpResponseSeeOther(django.urls.reverse("admin:jb_common_topic_add"))
        else:
            raise permissions.PermissionError(request.user,
                                              _("You cannot add topics here because you are not in any department."))
    if request.method == "POST":
        new_topic_form = NewTopicForm(request.user, request.POST)
        if new_topic_form.is_valid():
            parent_topic = new_topic_form.cleaned_data.get("parent_topic", None)
            new_topic = Topic(name=new_topic_form.cleaned_data["new_topic_name"],
                              confidential=new_topic_form.cleaned_data["confidential"],
                              department=request.user.jb_user_details.department,
                              manager=new_topic_form.cleaned_data["topic_manager"])
            if parent_topic:
                new_topic.parent_topic = parent_topic
                new_topic.confidential = parent_topic.confidential
                new_topic.save()
                new_topic.members.set(parent_topic.members.all())
                next_view = None
                next_view_kwargs = {}
            else:
                new_topic.save()
                next_view = "samples:edit_topic"
                next_view_kwargs = {"id": django.utils.http.urlquote(str(new_topic.id), safe="")}
            new_topic.manager.user_permissions.add(permissions.get_topic_manager_permission())
            request.user.topics.add(new_topic)
            request.user.samples_user_details.auto_addition_topics.add(new_topic)
            return utils.successful_response(
                request, _("Topic {name} was successfully created.").format(name=new_topic.name),
                next_view, kwargs=next_view_kwargs)
    else:
        new_topic_form = NewTopicForm(request.user)
    return render(request, "samples/add_topic.html", {"title": capfirst(_("add new topic")), "new_topic": new_topic_form})


@login_required
def list_(request):
    """View for a complete list of all topics that the user can edit.  The
    user may select one, which leads him to the membership view for this topic.
    If the user can't edit any topic, a 404 is raised.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    user = request.user
    topics = []
    for topic in Topic.objects.filter(parent_topic=None).iterator():
        if topic.confidential and user not in topic.members.all() and not user.is_superuser:
            continue
        editable = False
        if permissions.has_permission_to_edit_topic(user, topic):
            editable = True
        topics.append((topic, editable))
    if not topics:
        raise Http404("Can't find any topics.")
    return render(request, "samples/list_topics.html", {"title": _("List of all topics"), "topics": topics})


class EditTopicForm(forms.Form):
    """Form for the member list of a topic.  Note that it is allowed to have
    no members at all in a topic.  However, if the topic is confidential, the
    currently logged-in user must remain a member of the topic.
    """
    members = MultipleUsersField(label=_("Members"), required=False)
    confidential = forms.BooleanField(label=_("confidential"), required=False)
    topic_manager = UserField(label=capfirst(_("topic manager")))

    def __init__(self, user, topic, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["members"].set_users(user, topic.members.all())
        self.fields["members"].widget.attrs["size"] = 30
        self.fields["confidential"].initial = topic.confidential
        self.user = user
        self.topic = topic
        self.fields["topic_manager"].set_users(user, topic.manager)

    def clean(self):
        cleaned_data = super().clean()
        if "members" in cleaned_data and "confidential" in cleaned_data:
            if cleaned_data["confidential"] and \
                    not any(permissions.has_permission_to_edit_topic(user, self.topic) for user in cleaned_data["members"]):
                self.add_error("members", ValidationError(
                    _("In confidential topics, at least one member must have permission to edit the topic."), code="invalid"))
        return cleaned_data


@login_required
def edit(request, id):
    """View for changing the members of a particular topic, and to set the
    restriction status.  This is only allowed to heads of institute groups and
    topic managers.

    :param request: the current HTTP Request object
    :param id: the id of the topic

    :type request: HttpRequest
    :type name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    topic = get_object_or_404(Topic, id=int_or_zero(id), parent_topic=None)
    permissions.assert_can_edit_topic(request.user, topic)
    if request.method == "POST":
        edit_topic_form = EditTopicForm(request.user, topic, request.POST)
        added_members = []
        removed_members = []
        if edit_topic_form.is_valid():
            old_manager = topic.manager
            new_manager = edit_topic_form.cleaned_data["topic_manager"]
            topic.manager = new_manager
            old_members = list(topic.members.all())
            new_members = list(edit_topic_form.cleaned_data["members"]) + [new_manager]
            topic.members.set(new_members)
            topic.confidential = edit_topic_form.cleaned_data["confidential"]
            topic.save()
            if old_manager != new_manager:
                topic_manager_permission = permissions.get_topic_manager_permission()
                if not old_manager.managed_topics.all():
                    old_manager.user_permissions.remove(topic_manager_permission)
                if not permissions.has_permission_to_edit_users_topics(new_manager):
                    new_manager.user_permissions.add(topic_manager_permission)
            for user in new_members:
                if user not in old_members:
                    added_members.append(user)
                    #topic.auto_adders.add(user.samples_user_details)  -> auto add of user to "auto addition" not wanted anymore
            for user in old_members:
                if user not in new_members:
                    removed_members.append(user)
                    topic.auto_adders.remove(user.samples_user_details)
            if added_members:
                utils.Reporter(request.user).report_changed_topic_membership(added_members, topic, "added")
            if removed_members:
                utils.Reporter(request.user).report_changed_topic_membership(removed_members, topic, "removed")
            return utils.successful_response(
                request, _("Members of topic “{name}” were successfully updated.").format(name=topic.name))
    else:
        edit_topic_form = \
            EditTopicForm(request.user, topic, initial={"members": list(topic.members.values_list("pk", flat=True)),
                                                        "topic_manager": topic.manager.pk})
    return render(request, "samples/edit_topic.html", {"title": _("Change topic memberships of “{0}”").format(topic.name),
                                                       "edit_topic": edit_topic_form})


_ = ugettext
