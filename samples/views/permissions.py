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


u"""Views for editing permissions for physical processes and to appoint topic
managers.
"""

from __future__ import absolute_import

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Permission
from django.db.models import Q
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal_common.utils import get_really_full_name
from samples import models
from samples.views import utils


class PhysicalProcess(object):

    topic_manager_permission = Permission.objects.get(codename="can_edit_their_topics")

    def __init__(self, physical_process_class):
        self.name = physical_process_class._meta.verbose_name_plural
        self.codename = physical_process_class.__name__
        substitutions = {"process_name": utils.camel_case_to_underscores(physical_process_class.__name__)}
        self.edit_permissions_permission = \
            Permission.objects.get(codename="edit_permissions_for_{process_name}".format(**substitutions))
        self.add_permission = Permission.objects.get(codename="add_{process_name}".format(**substitutions))
        self.view_all_permission = Permission.objects.get(codename="view_every_{process_name}".format(**substitutions))
        base_query = User.objects.filter(is_active=True, chantal_user_details__is_administrative=False)
        permission_editors = base_query.filter(Q(groups__permissions=self.edit_permissions_permission) |
                                               Q(user_permissions=self.edit_permissions_permission)).distinct()
        adders = base_query.filter(Q(groups__permissions=self.add_permission) |
                                   Q(user_permissions=self.add_permission)).distinct()
        full_viewers = base_query.filter(Q(groups__permissions=self.view_all_permission) |
                                         Q(user_permissions=self.view_all_permission)).distinct()
        self.permission_editors = sorted_users(permission_editors)
        self.adders = sorted_users(adders)
        self.full_viewers = sorted_users(full_viewers)


def sorted_users(users):
    return sorted(users, key=lambda user: user.last_name.lower() if user.last_name else user.username)


def get_physical_processes(user):
    return [PhysicalProcess(process) for process in models.physical_process_models.values()]


@login_required
def list_(request):
    user = request.user
    physical_processes = get_physical_processes(user)
    can_edit_permissions = user.has_perm("samples.edit_permissions_for_all_physical_processes") or \
        any(user in process.permission_editors for process in physical_processes)
    if can_edit_permissions:
        user_list = sorted_users(User.objects.filter(is_active=True, chantal_user_details__is_administrative=False))
    else:
        user_list = []
    if user.has_perm("chantal_common.can_edit_all_topics"):
        topic_managers = sorted_users(User.objects.filter(is_active=True, chantal_user_details__is_administrative=False)
                                      .filter(Q(groups__permissions=PhysicalProcess.topic_manager_permission) |
                                              Q(user_permissions=PhysicalProcess.topic_manager_permission)).distinct())
    else:
        topic_managers = None
    return render_to_response(
        "samples/list_permissions.html",
        {"title": _(u"Permissions for processes"), "physical_processes": physical_processes,
         "user_list": user_list, "topic_managers": topic_managers},
        context_instance=RequestContext(request))


class PermissionsForm(forms.Form):
    _ = ugettext_lazy
    can_add = forms.BooleanField(label=u"Can add", required=False)
    can_view_all = forms.BooleanField(label=u"Can view all", required=False)
    can_edit_permissions = forms.BooleanField(label=u"Can edit permissions", required=False)


class IsTopicManagerForm(forms.Form):
    _ = ugettext_lazy
    is_topic_manager = forms.BooleanField(label=_(u"Is topic manager"), required=False)


@login_required
def edit(request, username):
    edited_user = get_object_or_404(User, username=username)
    user = request.user
    has_global_edit_permission = user.has_perm("samples.edit_permissions_for_all_physical_processes")
    can_appoint_topic_managers = user.has_perm("chantal_common.can_edit_all_topics")
    permissions_list = []
    for process in get_physical_processes(user):
        if user in process.permission_editors or has_global_edit_permission:
            if request.method == "POST":
                permissions_list.append((process, PermissionsForm(request.POST, prefix=process.codename)))
            else:
                permissions_list.append((process, PermissionsForm(
                            initial={"can_add": edited_user in process.adders,
                                     "can_view_all": edited_user in process.full_viewers,
                                     "can_edit_permissions": edited_user in process.permission_editors},
                            prefix=process.codename)))
    if request.method == "POST":
        is_topic_manager_form = IsTopicManagerForm(request.POST)
        if all(permission[1].is_valid() for permission in permissions_list) and is_topic_manager_form.is_valid():
            for process, permissions_form in permissions_list:
                cleaned_data = permissions_form.cleaned_data
                def process_permission(form_key, attribute_name, permission):
                    if cleaned_data[form_key]:
                        if edited_user not in getattr(process, attribute_name):
                            edited_user.user_permissions.add(permission)
                    else:
                        if edited_user in getattr(process, attribute_name):
                            edited_user.user_permissions.remove(permission)
                process_permission("can_add", "adders", process.add_permission)
                process_permission("can_view_all", "full_viewers", process.view_all_permission)
                process_permission("can_edit_permissions", "permission_editors", process.edit_permissions_permission)
            if is_topic_manager_form.cleaned_data["is_topic_manager"]:
                edited_user.user_permissions.add(PhysicalProcess.topic_manager_permission)
            else:
                edited_user.user_permissions.remove(PhysicalProcess.topic_manager_permission)
            return utils.successful_response(request, _(u"The permissions of {name} were successfully changed."). \
                                                 format(name=get_really_full_name(edited_user)), list_)
    else:
        is_topic_manager_form = IsTopicManagerForm(
            initial={"is_topic_manager": edited_user.has_perm("chantal_common.can_edit_their_topics")})
    return render_to_response(
        "samples/edit_permissions.html",
        {"title": _(u"Change permissions for {name}").format(name=get_really_full_name(edited_user)),
         "permissions_list": permissions_list,
         "is_topic_manager": is_topic_manager_form if can_appoint_topic_managers else None},
        context_instance=RequestContext(request))
