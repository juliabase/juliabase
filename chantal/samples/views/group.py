#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for editing Chantal groups in various ways.  You may add groups, get
a list of them, and change user memberships in groups.  The list of groups is
actually only a stepping stone to the membership edit view.
"""

from __future__ import absolute_import

from django.shortcuts import render_to_response, get_object_or_404
import django.utils.http
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.utils.translation import ugettext as _, ugettext_lazy
import django.forms as forms
from django.forms.util import ValidationError
import django.contrib.auth.models
from samples import models, permissions
from samples.views import utils, feed_utils, form_utils


def set_restriction_status(group, restricted):
    u"""Set the restriction status for a group.  This routine assures that a
    group details record exists.

    :Parameters:
      - `group`: the group to be changed
      - `restricted`: the new restriction status of the group

    :type group: ``django.contrib.auth.models.Group``
    :type restricted: bool
    """
    try:
        group.details.restricted = restricted
        group.details.save()
    except models.GroupDetails.DoesNotExist:
        group_details = models.GroupDetails.objects.create(group=group, restricted=restricted)


class NewGroupForm(forms.Form):
    u"""Form for adding a new group.  I need only its new name and restriction
    status.
    """
    _ = ugettext_lazy
    new_group_name = forms.CharField(label=_(u"Name of new group"), max_length=80)
    # Translation hint: Group which is not open to senior members
    restricted = forms.BooleanField(label=_(u"restricted"), required=False)
    def __init__(self, *args, **kwargs):
        super(NewGroupForm, self).__init__(*args, **kwargs)
        self.fields["new_group_name"].widget.attrs["size"] = 40
    def clean_new_group_name(self):
        group_name = self.cleaned_data["new_group_name"]
        group_name = u" ".join(group_name.split())
        if django.contrib.auth.models.Group.objects.filter(name=group_name).count():
            raise ValidationError(_(u"This group name is already used."))
        return group_name


@login_required
def add(request):
    u"""View for adding a new group.  This action is only allowed to the heads
    of institute groups.  The name of groups may contain arbitrary characters.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_edit_group(request.user)
    if request.method == "POST":
        new_group_form = NewGroupForm(request.POST)
        if new_group_form.is_valid():
            new_group = django.contrib.auth.models.Group(name=new_group_form.cleaned_data["new_group_name"])
            new_group.save()
            request.user.groups.add(new_group)
            set_restriction_status(new_group, new_group_form.cleaned_data["restricted"])
            return utils.successful_response(
                request, _(u"Group %s was successfully created.") % new_group.name, "samples.views.group.edit",
                kwargs={"name": django.utils.http.urlquote(new_group.name, safe="")})
    else:
        new_group_form = NewGroupForm()
    return render_to_response("add_group.html", {"title": _(u"Add new group"), "new_group": new_group_form},
                              context_instance=RequestContext(request))


@login_required
def list_(request):
    u"""View for a complete list of all groups.  The user may select one, which
    leads him to the membership view for this group.  Note this this view is
    also restricted to users who can change memberships in groups, although it
    is not really necessary.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_edit_group(request.user)
    all_groups = django.contrib.auth.models.Group.objects.all()
    user_groups = request.user.groups.all()
    groups = set(group for group in all_groups if not permissions.is_restricted(group) or group in user_groups)
    return render_to_response("list_groups.html",
                              {"title": _(u"List of all groups"), "groups": groups},
                              context_instance=RequestContext(request))


class EditGroupForm(forms.Form):
    u"""Form for the member list of a group.  Note that it is allowed to have
    no members at all in a group.  However, if the group is restricted, the
    currently logged-in user must remain a member of the group.
    """
    members = form_utils.MultipleUsersField(label=_(u"Members"), required=False)
    restricted = forms.BooleanField(label=_(u"restricted"), required=False)

    def __init__(self, user, group, *args, **kwargs):
        super(EditGroupForm, self).__init__(*args, **kwargs)
        self.fields["members"].set_users(group.user_set.all())
        self.fields["restricted"].initial = permissions.is_restricted(group)
        self.user = user

    def clean(self):
        cleaned_data = self.cleaned_data
        if "members" in cleaned_data and "restricted" in cleaned_data:
            if cleaned_data["restricted"] and \
                    not any(permissions.has_permission_to_edit_group(user) for user in cleaned_data["members"]):
                form_utils.append_error(
                    self, _(u"In restricted groups, at least one member must have permission to change groups."), "members")
        return cleaned_data


@login_required
def edit(request, name):
    u"""View for changing the members of a particular group, and to set the
    restriction status.  This is only allowed to heads of institute groups.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: the name of the group

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    group = get_object_or_404(django.contrib.auth.models.Group, name=name)
    permissions.assert_can_edit_group(request.user, group)
    if request.method == "POST":
        edit_group_form = EditGroupForm(request.user, group, request.POST)
        added_members = []
        removed_members = []
        if edit_group_form.is_valid():
            old_members = list(group.user_set.all())
            new_members = edit_group_form.cleaned_data["members"]
            group.user_set = new_members
            set_restriction_status(group, edit_group_form.cleaned_data["restricted"])
            for user in new_members:
                if user not in old_members:
                    added_members.append(user)
                    group.auto_adders.add(utils.get_profile(user))
            for user in old_members:
                if user not in new_members:
                    removed_members.append(user)
                    group.auto_adders.remove(utils.get_profile(user))
            if added_members:
                feed_utils.Reporter(request.user).report_changed_group_membership(added_members, group, "added")
            if removed_members:
                feed_utils.Reporter(request.user).report_changed_group_membership(removed_members, group, "removed")
            return utils.successful_response(request, _(u"Members of group “%s” were successfully updated.") % group.name)
    else:
        edit_group_form = \
            EditGroupForm(request.user, group, initial={"members": group.user_set.values_list("pk", flat=True)})
    return render_to_response("edit_group.html",
                              {"title": _(u"Change group memberships of “%s”") % name,
                               "edit_group": edit_group_form},
                              context_instance=RequestContext(request))
