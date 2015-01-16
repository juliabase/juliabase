#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Views for editing permissions for addable models and to appoint topic
managers.
"""

from __future__ import absolute_import, unicode_literals

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Permission
from django.db.models import Q
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
import django.core
from django.conf import settings
from jb_common.utils.base import help_link, get_really_full_name, get_all_models, HttpResponseSeeOther, \
    camel_case_to_underscores, sorted_users
from jb_common.utils.views import UserField
from samples import models, permissions
import samples.utils.views as utils


class PermissionsModels(object):
    """Class for holding the permissions status of a addable model class.

    :ivar name: the verbose plural name of the model class

    :ivar codename: the name of the model class

    :ivar edit_permissions_permission: the permission instance for editing
      permissions of this model

    :ivar add_permission: the permission instance for adding such models

    :ivar view_all_permission: the permission instance for viewing all
      instances of this model class

    :ivar permission_editors: All users who have the permission of change
      permissions for this model class.  Note that this excludes superusers,
      unless they have the distinctive permission.

    :ivar adders: All users who have the permission to add instances of such
      model. Note that this excludes superusers, unless they have the distinctive
      permission.

    :ivar full_viewers: All users who have the permission to view all instances
      of this model class.  Note that this excludes superusers, unless they
      have the distinctive permission.

    :ivar full_editors: All users who have the permission to edit all instances
      of this model class.  Note that this excludes superusers, unless they
      have the distinctive permission.

    :ivar all_users: All users who have the permission to add instances of this
      model, plus those who can change permissions (because they can give them the
      right to add instances anyway).  This is used to the overview table to
      show all users of a model.  Note that this excludes superusers, unless
      they have the distinctive permissions.

    :cvar topic_manager_permission: the permission instance for changing
      memberships in own topics

    :type name: unicode
    :type codename: str
    :type edit_permissions_permission: django.contrib.auth.models.Permission
    :type add_permission: django.contrib.auth.models.Permission
    :type view_all_permission: django.contrib.auth.models.Permission
    :type permission_editors: QuerySet
    :type adders: QuerySet
    :type full_viewers: QuerySet
    :type full_editors: QuerySet
    :type all_users: QuerySet
    :type topic_manager_permission: django.contrib.auth.models.Permission
    """

    topic_manager_permission = Permission.objects.get(codename="can_edit_their_topics")
    add_external_operators_permission = Permission.objects.get(codename="add_external_operator")

    def __init__(self, addable_model_class):
        """
        :param addable_model_class: the addable model class to which this
            instance belongs

        :type addable_model_class: ``class`` (derived from
          ``django.db.models.Model``)
        """
        self.name = addable_model_class._meta.verbose_name_plural
        self.codename = addable_model_class.__name__
        substitutions = {"model_name": camel_case_to_underscores(addable_model_class.__name__)}
        try:
            self.edit_permissions_permission = \
                Permission.objects.get(codename="edit_permissions_for_{model_name}".format(**substitutions))
        except Permission.DoesNotExist:
            self.edit_permissions_permission = None
        try:
            self.add_permission = Permission.objects.get(codename="add_{model_name}".format(**substitutions))
        except Permission.DoesNotExist:
            self.add_permission = None
        try:
            self.view_all_permission = Permission.objects.get(codename="view_every_{model_name}".format(**substitutions))
        except Permission.DoesNotExist:
            self.view_all_permission = None
        try:
            self.edit_all_permission = Permission.objects.get(codename="edit_every_{model_name}".format(**substitutions))
        except Permission.DoesNotExist:
            self.edit_all_permission = None
        base_query = User.objects.filter(is_active=True, is_superuser=False)
        permission_editors = base_query.filter(Q(groups__permissions=self.edit_permissions_permission) |
                                               Q(user_permissions=self.edit_permissions_permission)).distinct() \
                                               if self.edit_permissions_permission else []
        adders = permissions.get_all_adders(addable_model_class)
        full_viewers = base_query.filter(Q(groups__permissions=self.view_all_permission) |
                                         Q(user_permissions=self.view_all_permission)).distinct() \
                                   if self.view_all_permission else []
        full_editors = base_query.filter(Q(groups__permissions=self.edit_all_permission) |
                                         Q(user_permissions=self.edit_all_permission)).distinct() \
                                   if self.edit_all_permission else []
        self.permission_editors = sorted_users(permission_editors)
        self.adders = sorted_users(adders)
        self.full_viewers = sorted_users(full_viewers)
        self.full_editors = sorted_users(full_editors)
        self.all_users = sorted_users(set(adders) | set(permission_editors))


class UserListForm(forms.Form):
    """Form class for selecting the user to change the permissions for him/her.
    """
    _ = ugettext_lazy
    selected_user = UserField(label=_("Change the permissions of"))

    def __init__(self, user, *args, **kwargs):
        super(UserListForm, self).__init__(*args, **kwargs)
        self.fields["selected_user"].set_users(user)


def get_addable_models(user):
    """Return a list with all registered addable model classes the user is
    allowed to see (the classes per se; this is not about the visibility of the
    model instances).  Their type is of `PermissionsModels`, which
    means that they contain information about the users who have permissions
    for that model.

    You can see all addable model classes of your department.  A superuser
    can see all classes.

    The result is used to build the list of apparatuses for which one can set
    permissions.

    :param user:  The user for which the classes are returned that he is allowed
        to see.

    :type user: django.contrib.auth.models.User

    :return:
      all addable models for the user

    :rtype: list of `django.db.models.Model`
    """
    all_addable_models = []
    for model in get_all_models().values():
        if model._meta.app_label not in ["samples", "jb_common"]:
            try:
                configurable_permissions = model.JBMeta.configurable_permissions
            except AttributeError:
                continue
            else:
                if configurable_permissions:
                    all_addable_models.append(model)

    if not user.is_superuser:
        user_department = user.jb_user_details.department
        if user_department:
            all_addable_models = [model for model in all_addable_models
                                      if model._meta.app_label == user_department.app_label]
        else:
            all_addable_models = []
    all_addable_models.sort(key=lambda model: model._meta.verbose_name_plural.lower())
    all_addable_models = [PermissionsModels(model) for model in all_addable_models]
    return all_addable_models


@help_link("demo.html#change-permissions-for-processes")
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

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    user = request.user
    addable_models = get_addable_models(user)
    can_edit_permissions = user.has_perm("samples.edit_permissions_for_all_physical_processes") or \
        any(user in model.permission_editors for model in addable_models)
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
    if user.has_perm("jb_common.can_edit_all_topics"):
        topic_managers = sorted_users(
            User.objects.filter(is_active=True, is_superuser=False)
            .filter(Q(groups__permissions=PermissionsModels.topic_manager_permission) |
                    Q(user_permissions=PermissionsModels.topic_manager_permission)).distinct())
    else:
        topic_managers = None
    return render(request, "samples/list_permissions.html",
                  {"title": _("Permissions"), "addable_models": addable_models,
                   "user_list": user_list_form, "topic_managers": topic_managers})


class PermissionsForm(forms.Form):
    """Form class for setting the permission triplets of a single model
    class and a single user.  See `edit` for further information.
    """
    _ = ugettext_lazy
    can_add = forms.BooleanField(label="Can add", required=False)
    can_view_all = forms.BooleanField(label="Can view all", required=False)
    can_edit_all = forms.BooleanField(label="Can edit all", required=False)
    can_edit_permissions = forms.BooleanField(label="Can edit permissions", required=False)

    def __init__(self, edited_user, model, *args, **kwargs):
        kwargs["initial"] = {"can_add": edited_user in process.adders,
                             "can_view_all": edited_user in model.full_viewers,
                             "can_edit_all": edited_user in model.full_editors,
                             "can_edit_permissions": edited_user in processmodel.permission_editors}
        super(PermissionsForm, self).__init__(*args, **kwargs)
        if not model.add_permission:
            self.fields["can_add"].widget.attrs.update({"disabled": "disabled", "style": "display: none"})
        if not model.view_all_permission:
            self.fields["can_view_all"].widget.attrs.update({"disabled": "disabled", "style": "display: none"})
        if not model.edit_all_permission:
            self.fields["can_edit_all"].widget.attrs.update({"disabled": "disabled", "style": "display: none"})
        if not model.edit_permissions_permission:
            self.fields["can_edit_permissions"].widget.attrs.update({"disabled": "disabled", "style": "display: none"})

    def clean(self):
        """Note that I don't check whether disabled fields were set
        nevertheless.  This means tampering but it is ignored in the view
        function anyway.  Moreover, superfluous values in the POST request are
        always ignored.
        """
        cleaned_data = super(PermissionsForm, self).clean()
        if cleaned_data["can_edit_permissions"]:
            cleaned_data["can_add"] = cleaned_data["can_view_all"] = cleaned_data["can_edit_all"] = True
        return cleaned_data


@login_required
def edit(request, username):
    """View for editing user permissions.  You can change two kinds of user
    permissions here: The “add”, “view all”, and “edit permissions”
    permissions, as well as whether the user is a so-called “topic manager”.
    See `list_` for further information.

    :param request: the current HTTP Request object
    :param username: the username of the user whose permissions should be
        changed

    :type request: HttpRequest
    :type username: unicode

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    edited_user = get_object_or_404(User, username=username)
    user = request.user
    has_global_edit_permission = user.has_perm("samples.edit_permissions_for_all_physical_processes")
    addable_models = get_addable_models(user)
    permissions_list = []
    for model in addable_models:
        if model.add_permission or model.view_all_permission or model.edit_all_permission or \
                model.edit_permissions_permission:
            if user in model.permission_editors or has_global_edit_permission:
                if request.method == "POST":
                    permissions_list.append((model, PermissionsForm(edited_user, model, request.POST,
                                                                      prefix=model.codename)))
                else:
                    permissions_list.append((model, PermissionsForm(edited_user, model, prefix=model.codename)))
    if request.method == "POST":
        if all(permission[1].is_valid() for permission in permissions_list):
            for model, permissions_form in permissions_list:
                cleaned_data = permissions_form.cleaned_data
                def model_permission(form_key, attribute_name, permission):
                    if permission:
                        if cleaned_data[form_key]:
                            if edited_user not in getattr(model, attribute_name):
                                edited_user.user_permissions.add(permission)
                        else:
                            if edited_user in getattr(model, attribute_name):
                                edited_user.user_permissions.remove(permission)
                model_permission("can_add", "adders", model.add_permission)
                model_permission("can_view_all", "full_viewers", model.view_all_permission)
                model_permission("can_edit_all", "full_editors", model.edit_all_permission)
                model_permission("can_edit_permissions", "permission_editors", model.edit_permissions_permission)
            return utils.successful_response(request, _("The permissions of {name} were successfully changed."). \
                                                 format(name=get_really_full_name(edited_user)), list_)
    return render(request, "samples/edit_permissions.html",
                  {"title": _("Change permissions of {name}").format(name=get_really_full_name(edited_user)),
                   "permissions_list": permissions_list})
