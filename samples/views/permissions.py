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


"""Views for editing permissions for physical processes and to appoint topic
managers.
"""

from __future__ import absolute_import, unicode_literals

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Permission
from django.db.models import Q
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal_common.utils import get_really_full_name, get_all_models, HttpResponseSeeOther
from samples import models, permissions
from samples.views import utils, form_utils
import django.core


class PhysicalProcess(object):
    """Class for holding the permissions status of a physical process class.

    :ivar name: the verbose plural name of the process class

    :ivar codename: the name of the process class

    :ivar edit_permissions_permission: the permission instance for editing
      permissions of this process

    :ivar add_permission: the permission instance for adding such processes

    :ivar view_all_permission: the permission instance for viewing all
      processes of this processes class

    :ivar permission_editors: All users who have the permission of change
      permissions for this process class.  Note that this excludes superusers,
      unless they have the distinctive permission.

    :ivar adders: All users who have the permission to add such processes.
      Note that this excludes superusers, unless they have the distinctive
      permission.

    :ivar full_viewers: All users who have the permission to view all processes
      of this process class.  Note that this excludes superusers, unless they
      have the distinctive permission.

    :ivar full_editors: All users who have the permission to edit all processes
      of this process class.  Note that this excludes superusers, unless they
      have the distinctive permission.

    :ivar all_users: All users who have the permission to add such processes,
      plus those who can change permissions (because they can give them the
      right to add processes anyway).  This is used to the overview table to
      show all users of a process.  Note that this excludes superusers, unless
      they have the distinctive permissions.

    :cvar topic_manager_permission: the permission instance for changing
      memberships in own topics

    :type name: unicode
    :type codename: str
    :type edit_permissions_permission: ``django.contrib.auth.models.Permission``
    :type add_permission: ``django.contrib.auth.models.Permission``
    :type view_all_permission: ``django.contrib.auth.models.Permission``
    :type permission_editors: ``QuerySet``
    :type adders: ``QuerySet``
    :type full_viewers: ``QuerySet``
    :type full_editors: ``QuerySet``
    :type all_users: ``QuerySet``
    :type topic_manager_permission: ``django.contrib.auth.models.Permission``
    """

    topic_manager_permission = Permission.objects.get(codename="can_edit_their_topics")
    add_external_operators_permission = Permission.objects.get(codename="add_external_operator")

    def __init__(self, physical_process_class):
        """
        :Parameters:
          - `physical_process_class`: the physical process class to which this
            instance belongs

        :type physical_process_class: ``class`` (derived from
          ``samples.models.PhysicalProcess``)
        """
        self.name = physical_process_class._meta.verbose_name_plural
        self.codename = physical_process_class.__name__
        substitutions = {"process_name": utils.camel_case_to_underscores(physical_process_class.__name__)}
        try:
            self.edit_permissions_permission = \
                Permission.objects.get(codename="edit_permissions_for_{process_name}".format(**substitutions))
        except Permission.DoesNotExist:
            self.edit_permissions_permission = None
        try:
            self.add_permission = Permission.objects.get(codename="add_{process_name}".format(**substitutions))
        except Permission.DoesNotExist:
            self.add_permission = None
        try:
            self.view_all_permission = Permission.objects.get(codename="view_every_{process_name}".format(**substitutions))
        except Permission.DoesNotExist:
            self.view_all_permission = None
        try:
            self.edit_all_permission = Permission.objects.get(codename="edit_every_{process_name}".format(**substitutions))
        except Permission.DoesNotExist:
            self.edit_all_permission = None
        base_query = User.objects.filter(is_active=True, chantal_user_details__is_administrative=False)
        permission_editors = base_query.filter(Q(groups__permissions=self.edit_permissions_permission) |
                                               Q(user_permissions=self.edit_permissions_permission)).distinct() \
                                               if self.edit_permissions_permission else []
        adders = permissions.get_all_adders(physical_process_class)
        full_viewers = base_query.filter(Q(groups__permissions=self.view_all_permission) |
                                         Q(user_permissions=self.view_all_permission)).distinct() \
                                   if self.view_all_permission else []
        full_editors = base_query.filter(Q(groups__permissions=self.edit_all_permission) |
                                         Q(user_permissions=self.edit_all_permission)).distinct() \
                                   if self.edit_all_permission else []
        self.permission_editors = utils.sorted_users(permission_editors)
        self.adders = utils.sorted_users(adders)
        self.full_viewers = utils.sorted_users(full_viewers)
        self.full_editors = utils.sorted_users(full_editors)
        self.all_users = utils.sorted_users(set(adders) | set(permission_editors))


class UserListForm(forms.Form):
    """Form class for selecting the user to change the permissions for him/her.
    """
    selected_user = form_utils.UserField(label=_("Change the permissions of"))

    def __init__(self, user, *args, **kwargs):
        super(UserListForm, self).__init__(*args, **kwargs)
        self.fields["selected_user"].set_users(user)


def get_physical_processes(user):
    """Return a list with all registered physical processes.  Their type is of
    `PhysicalProcess`, which means that they contain information about the
    users who have permissions for that process.

    :Return:
      all physical processes

    :rtype: list of `PhysicalProcess`
    """
    if user.is_superuser:
        all_physical_processes = [PhysicalProcess(process) for process in utils.get_physical_processes()]
    else:
        all_physical_processes = [PhysicalProcess(process) for process
                                  in utils.get_physical_processes(user.chantal_user_details.department.name)]
    return all_physical_processes

@login_required
def list_(request):
    """View for listing user permissions.  It shows who can add new processes
    of all registered physical process classes.  It also shows who can change
    permissions for them (usually the person responsible for the respective
    apparatus).

    It deliberately does not show who is able to see all runs of a particular
    apparatus.  First, this information is of little value for other users.
    And secondly, it may cause “why him and not me?” emails.

    For the very same reason, only those you can create new topics (typically,
    the team leaders of the institution), can see who's a “topic manager”
    (i.e., someone who can change memberships in their topics).

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user = request.user
    physical_processes = get_physical_processes(user)
    can_edit_permissions = user.has_perm("samples.edit_permissions_for_all_physical_processes") or \
        any(user in process.permission_editors for process in physical_processes)
    if can_edit_permissions:
        if request.method == "POST":
            user_list_form = UserListForm(user, request.POST)
            if user_list_form.is_valid():
                return HttpResponseSeeOther(django.core.urlresolvers.reverse("samples.views.permissions.edit",
                                kwargs={"username": user_list_form.cleaned_data["selected_user"].username}))
        else:
            user_list_form = UserListForm(user)
    else:
        user_list_form = None
    if user.has_perm("chantal_common.can_edit_all_topics"):
        topic_managers = utils.sorted_users(
            User.objects.filter(is_active=True, chantal_user_details__is_administrative=False)
            .filter(Q(groups__permissions=PhysicalProcess.topic_manager_permission) |
                    Q(user_permissions=PhysicalProcess.topic_manager_permission)).distinct())
    else:
        topic_managers = None
    return render_to_response(
        "samples/list_permissions.html",
        {"title": _("Permissions to processes"), "physical_processes": physical_processes,
         "user_list": user_list_form, "topic_managers": topic_managers},
        context_instance=RequestContext(request))


class PermissionsForm(forms.Form):
    """Form class for setting the permission triplets of a single process
    class and a single user.  See `edit` for further information.
    """
    _ = ugettext_lazy
    can_add = forms.BooleanField(label="Can add", required=False)
    can_view_all = forms.BooleanField(label="Can view all", required=False)
    can_edit_all = forms.BooleanField(label="Can edit all", required=False)
    can_edit_permissions = forms.BooleanField(label="Can edit permissions", required=False)

    def __init__(self, edited_user, process, *args, **kwargs):
        kwargs["initial"] = {"can_add": edited_user in process.adders,
                             "can_view_all": edited_user in process.full_viewers,
                             "can_edit_all": edited_user in process.full_editors,
                             "can_edit_permissions": edited_user in process.permission_editors}
        super(PermissionsForm, self).__init__(*args, **kwargs)
        if not process.add_permission:
            self.fields["can_add"].widget.attrs.update({"disabled": "disabled", "style": "display: none"})
        if not process.view_all_permission:
            self.fields["can_view_all"].widget.attrs.update({"disabled": "disabled", "style": "display: none"})
        if not process.edit_all_permission:
            self.fields["can_edit_all"].widget.attrs.update({"disabled": "disabled", "style": "display: none"})
        if not process.edit_permissions_permission:
            self.fields["can_edit_permissions"].widget.attrs.update({"disabled": "disabled", "style": "display: none"})

    def clean(self):
        """Note that I don't check whether disabled fields were set
        nevertheless.  This means tampering but it is ignored in the view
        function anyway.  Moreover, superfluous values in the POST request are
        always ignored.
        """
        if self.cleaned_data["can_edit_permissions"]:
            self.cleaned_data["can_add"] = self.cleaned_data["can_view_all"] = self.cleaned_data["can_edit_all"] = True
        return self.cleaned_data


@login_required
def edit(request, username):
    """View for editing user permissions.  You can change two kinds of user
    permissions here: The “add”, “view all”, and “edit permissions”
    permissions, as well as whether the user is a so-called “topic manager”.
    See `list_` for further information.

    :Parameters:
      - `request`: the current HTTP Request object
      - `username`: the username of the user whose permissions should be
        changed

    :type request: ``HttpRequest``
    :type username: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    edited_user = get_object_or_404(User, username=username)
    user = request.user
    has_global_edit_permission = user.has_perm("samples.edit_permissions_for_all_physical_processes")
    physical_processes = get_physical_processes(user)
    permissions_list = []
    for process in physical_processes:
        if process.add_permission or process.view_all_permission or process.edit_all_permission or \
                process.edit_permissions_permission:
            if user in process.permission_editors or has_global_edit_permission:
                if request.method == "POST":
                    permissions_list.append((process, PermissionsForm(edited_user, process, request.POST,
                                                                      prefix=process.codename)))
                else:
                    permissions_list.append((process, PermissionsForm(edited_user, process, prefix=process.codename)))
    if request.method == "POST":
        if all(permission[1].is_valid() for permission in permissions_list):
            for process, permissions_form in permissions_list:
                cleaned_data = permissions_form.cleaned_data
                def process_permission(form_key, attribute_name, permission):
                    if permission:
                        if cleaned_data[form_key]:
                            if edited_user not in getattr(process, attribute_name):
                                edited_user.user_permissions.add(permission)
                        else:
                            if edited_user in getattr(process, attribute_name):
                                edited_user.user_permissions.remove(permission)
                process_permission("can_add", "adders", process.add_permission)
                process_permission("can_view_all", "full_viewers", process.view_all_permission)
                process_permission("can_edit_all", "full_editors", process.edit_all_permission)
                process_permission("can_edit_permissions", "permission_editors", process.edit_permissions_permission)
            return utils.successful_response(request, _("The permissions of {name} were successfully changed."). \
                                                 format(name=get_really_full_name(edited_user)), list_)
    return render_to_response(
        "samples/edit_permissions.html",
        {"title": _("Change permissions of {name}").format(name=get_really_full_name(edited_user)),
         "permissions_list": permissions_list},
        context_instance=RequestContext(request))
