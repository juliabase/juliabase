#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for editing Chantal projects in various ways.  You may add projects,
get a list of them, and change user memberships in projects.  The list of
projects is actually only a stepping stone to the membership edit view.
"""

from __future__ import absolute_import

from django.shortcuts import render_to_response, get_object_or_404
import django.utils.http
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.utils.translation import ugettext as _, ugettext_lazy
import django.forms as forms
from django.forms.util import ValidationError
from chantal_common.utils import append_error
from chantal_common.models import Project
from samples import models, permissions
from samples.views import utils, feed_utils, form_utils


class NewProjectForm(forms.Form):
    u"""Form for adding a new project.  I need only its new name and
    restriction status.
    """
    _ = ugettext_lazy
    new_project_name = forms.CharField(label=_(u"Name of new project"), max_length=80)
    # Translation hint: Project which is not open to senior members
    restricted = forms.BooleanField(label=_(u"restricted"), required=False)
    def __init__(self, *args, **kwargs):
        super(NewProjectForm, self).__init__(*args, **kwargs)
        self.fields["new_project_name"].widget.attrs["size"] = 40
    def clean_new_project_name(self):
        project_name = self.cleaned_data["new_project_name"]
        project_name = u" ".join(project_name.split())
        if Project.objects.filter(name=project_name).count():
            raise ValidationError(_(u"This project name is already used."))
        return project_name


@login_required
def add(request):
    u"""View for adding a new project.  This action is only allowed to the
    heads of institute projects.  The name of projects may contain arbitrary
    characters.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_edit_project(request.user)
    if request.method == "POST":
        new_project_form = NewProjectForm(request.POST)
        if new_project_form.is_valid():
            new_project = Project(name=new_project_form.cleaned_data["new_project_name"],
                                  restricted=new_project_form.cleaned_data["restricted"])
            new_project.save()
            request.user.projects.add(new_project)
            return utils.successful_response(
                request, _(u"Project %s was successfully created.") % new_project.name, "samples.views.project.edit",
                kwargs={"name": django.utils.http.urlquote(new_project.name, safe="")})
    else:
        new_project_form = NewProjectForm()
    return render_to_response("samples/add_project.html", {"title": _(u"Add new project"), "new_project": new_project_form},
                              context_instance=RequestContext(request))


@login_required
def list_(request):
    u"""View for a complete list of all projects.  The user may select one,
    which leads him to the membership view for this project.  Note this this
    view is also restricted to users who can change memberships in projects,
    although it is not really necessary.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_edit_project(request.user)
    all_projects = Project.objects.all()
    user_projects = request.user.projects.all()
    projects = set(project for project in all_projects if not project.restricted or project in user_projects)
    return render_to_response("samples/list_projects.html",
                              {"title": _(u"List of all projects"), "projects": projects},
                              context_instance=RequestContext(request))


class EditProjectForm(forms.Form):
    u"""Form for the member list of a project.  Note that it is allowed to have
    no members at all in a project.  However, if the project is restricted, the
    currently logged-in user must remain a member of the project.
    """
    members = form_utils.MultipleUsersField(label=_(u"Members"), required=False)
    restricted = forms.BooleanField(label=_(u"restricted"), required=False)

    def __init__(self, user, project, *args, **kwargs):
        super(EditProjectForm, self).__init__(*args, **kwargs)
        self.fields["members"].set_users(project.members.all())
        self.fields["restricted"].initial = project.restricted
        self.user = user

    def clean(self):
        cleaned_data = self.cleaned_data
        if "members" in cleaned_data and "restricted" in cleaned_data:
            if cleaned_data["restricted"] and \
                    not any(permissions.has_permission_to_edit_project(user) for user in cleaned_data["members"]):
                append_error(self,
                             _(u"In restricted projects, at least one member must have permission to change projects."),
                             "members")
        return cleaned_data


@login_required
def edit(request, name):
    u"""View for changing the members of a particular project, and to set the
    restriction status.  This is only allowed to heads of institute groups.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: the name of the project

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    project = get_object_or_404(Project, name=name)
    permissions.assert_can_edit_project(request.user, project)
    if request.method == "POST":
        edit_project_form = EditProjectForm(request.user, project, request.POST)
        added_members = []
        removed_members = []
        if edit_project_form.is_valid():
            old_members = list(project.members.all())
            new_members = edit_project_form.cleaned_data["members"]
            project.members = new_members
            project.restricted = edit_project_form.cleaned_data["restricted"]
            for user in new_members:
                if user not in old_members:
                    added_members.append(user)
                    project.auto_adders.add(utils.get_profile(user))
            for user in old_members:
                if user not in new_members:
                    removed_members.append(user)
                    project.auto_adders.remove(utils.get_profile(user))
            if added_members:
                feed_utils.Reporter(request.user).report_changed_project_membership(added_members, project, "added")
            if removed_members:
                feed_utils.Reporter(request.user).report_changed_project_membership(removed_members, project, "removed")
            return utils.successful_response(request,
                                             _(u"Members of project “%s” were successfully updated.") % project.name)
    else:
        edit_project_form = \
            EditProjectForm(request.user, project, initial={"members": project.members.values_list("pk", flat=True)})
    return render_to_response("samples/edit_project.html",
                              {"title": _(u"Change project memberships of “%s”") % name,
                               "edit_project": edit_project_form},
                              context_instance=RequestContext(request))
