#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for editing Chantal groups in various ways.  You may add groups, get
a list of them, and change user memberships in groups.  The list of groups is
actually only a stepping stone to the membership edit view.
"""

from django.shortcuts import render_to_response, get_object_or_404
import django.utils.http
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.utils.translation import ugettext as _, ugettext_lazy
import django.forms as forms
from django.forms.util import ValidationError
import django.contrib.auth.models
from chantal.samples import permissions
from chantal.samples.views import utils, feed_utils, form_utils

class NewGroupForm(forms.Form):
    u"""Form for adding a new group.  I need only its new name.
    """
    _ = ugettext_lazy
    new_group_name = forms.CharField(label=_(u"Name of new group"), max_length=80)
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
    permissions.assert_can_edit_group_memberships(request.user)
    if request.method == "POST":
        new_group_form = NewGroupForm(request.POST)
        if new_group_form.is_valid():
            new_group = django.contrib.auth.models.Group(name=new_group_form.cleaned_data["new_group_name"])
            new_group.save()
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
    also restricted to users who can change memberships in groups.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_edit_group_memberships(request.user)
    return render_to_response("list_groups.html",
                              {"title": _(u"List of all groups"), "groups": django.contrib.auth.models.Group.objects.all()},
                              context_instance=RequestContext(request))

class OperatorMultipleChoiceField(forms.ModelMultipleChoiceField):
    u"""A specialised ``ModelMultipleChoiceField`` for displaying users in a
    multiple choice field in forms.  It's only purpose is that you don't see
    the dull username then, but the beautiful full name of the user.
    """
    def label_from_instance(self, operator):
        return utils.get_really_full_name(operator)

class ChangeMembershipsForm(forms.Form):
    u"""Form for the member list of a group.  Note that it is allowed to have
    no members at all in a group.
    """
    members = form_utils.MultipleUsersField(label=_(u"Members"), required=False)
    def __init__(self, group, *args, **kwargs):
        super(ChangeMembershipsForm, self).__init__(*args, **kwargs)
        self.fields["members"].set_users(group.user_set.all())

@login_required
def edit(request, name):
    u"""View for changing the members of a particular group.  This is only
    allowed to heads of institute groups.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: the name of the group

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_edit_group_memberships(request.user)
    group = get_object_or_404(django.contrib.auth.models.Group, name=name)
    if request.method == "POST":
        change_memberships_form = ChangeMembershipsForm(group, request.POST)
        added_members = []
        removed_members = []
        if change_memberships_form.is_valid():
            old_members = list(group.user_set.all())
            new_members = change_memberships_form.cleaned_data["members"]
            group.user_set = new_members
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
        change_memberships_form = \
            ChangeMembershipsForm(group, initial={"members": group.user_set.values_list("pk", flat=True)})
    return render_to_response("edit_group_memberships.html",
                              {"title": _(u"Change group memberships of “%s”") % name,
                               "change_memberships": change_memberships_form},
                              context_instance=RequestContext(request))
