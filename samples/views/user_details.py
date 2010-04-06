#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for showing and editing user data, i.e. real names, contact
information, and preferences.
"""

from __future__ import absolute_import

import re
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal_common.utils import get_really_full_name
from samples import models, permissions
from samples.views import utils, form_utils


@login_required
def show_user(request, login_name):
    u"""View for showing basic information about a user, like the email
    address.  Maybe this could be fleshed out with phone number, picture,
    position, and field of interest.

    :Parameters:
      - `request`: the current HTTP Request object
      - `login_name`: the login name of the user to be shown

    :type request: ``HttpRequest``
    :type login_name: str

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    userdetails = utils.get_profile(user)
    username = get_really_full_name(user)
    return render_to_response("samples/show_user.html", {"title": username, "user": user, "userdetails": userdetails},
                              context_instance=RequestContext(request))


class UserDetailsForm(forms.ModelForm):
    u"""Model form for user preferences.  I exhibit only two field here, namely
    the auto-addition projects and the switch whether a user wants to get only
    important news or all.
    """
    _ = ugettext_lazy
    def __init__(self, user, *args, **kwargs):
        super(UserDetailsForm, self).__init__(*args, **kwargs)
        self.fields["auto_addition_projects"].queryset = user.projects
    class Meta:
        model = models.UserDetails
        fields = ("auto_addition_projects", "only_important_news")


@login_required
def edit_preferences(request, login_name):
    u"""View for editing preferences of a user.  Note that by giving the
    ``login_name`` explicitly, it is possible to edit the preferences of
    another user.  However, this is only allowed to staff.  The main reason for
    this explicitness is to be more “RESTful”.

    You can't switch the prefered language here because there are the flags
    anyway.

    Moreover, for good reason, you can't change your real name here.  This is
    taken automatically from the domain database through LDAP.  I want to give
    as few options as possible in order to avoid misbehaviour.

    :Parameters:
      - `request`: the current HTTP Request object
      - `login_name`: the login name of the user who's preferences should be
        edited.

    :type request: ``HttpRequest``
    :type login_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    if not request.user.is_staff and request.user != user:
        raise permissions.PermissionError(request.user, _(u"You can't access the preferences of another user."))
    initials_mandatory = utils.parse_query_string(request).get("initials_mandatory") == "True"
    user_details = utils.get_profile(user)
    if request.method == "POST":
        user_details_form = UserDetailsForm(user, request.POST, instance=user_details)
        initials_form = form_utils.InitialsForm(user, initials_mandatory, request.POST)
        if user_details_form.is_valid() and initials_form.is_valid():
            user_details_form.save()
            initials_form.save()
            return utils.successful_response(request, _(u"The preferences were successfully updated."))
    else:
        user_details_form = UserDetailsForm(user, instance=user_details)
        initials_form = form_utils.InitialsForm(user, initials_mandatory)
    return render_to_response("samples/edit_preferences.html",
                              {"title": _(u"Change preferences for %s") % get_really_full_name(request.user),
                               "user_details": user_details_form, "initials": initials_form,
                               "has_projects": bool(user.projects.count())},
                              context_instance=RequestContext(request))


@login_required
def projects_and_permissions(request, login_name):
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    if not request.user.is_staff and request.user != user:
        raise permissions.PermissionError(
            request.user, _(u"You can't access the list of projects and permissions of another user."))
    return render_to_response("samples/projects_and_permissions.html",
                              {"title": _(u"Projects and permissions for %s") % get_really_full_name(request.user),
                               "projects": user.projects.all(), "permissions": permissions.get_user_permissions(user),
                               "full_user_name": get_really_full_name(request.user)},
                              context_instance=RequestContext(request))
