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


"""Views for showing and editing user data, i.e. real names, contact
information, and preferences.
"""

from __future__ import absolute_import, unicode_literals

import re, json, copy
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django.conf import settings
from django import forms
from django.forms.util import ValidationError
import django.core.urlresolvers
from django.utils.translation import ugettext as _, ugettext_lazy
from django.utils.text import capfirst
from chantal_common.utils import get_really_full_name
from samples import models, permissions
from samples.views import utils, form_utils
from samples.permissions import get_all_addable_physical_process_models
from django.contrib.contenttypes.models import ContentType
from chantal_common import utils as chantal_common_utils, auth
from chantal_common.models import Topic, Department



@login_required
def show_user(request, login_name):
    """View for showing basic information about a user, like the email
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
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name, is_superuser=False)
    connection = auth.LDAPConnection()
    attributes = connection.get_ad_data(user.username)
    userdetails = ()
    if attributes:
        office = attributes["physicalDeliveryOfficeName"][0]
        phone = attributes["telephoneNumber"][0]
        userdetails = (office, phone)
    department = user.chantal_user_details.department
    username = get_really_full_name(user)
    return render_to_response("samples/show_user.html", {"title": username, "shown_user": user, "userdetails": userdetails,
                                                         "department": department},
                              context_instance=RequestContext(request))


class UserDetailsForm(forms.ModelForm):
    """Model form for user preferences.
    """
    _ = ugettext_lazy
    subscribed_feeds = forms.MultipleChoiceField(label=capfirst(_("subscribed newsfeeds")), required=False)
    default_folded_process_classes = forms.MultipleChoiceField(label=capfirst(_("folded processes")), required=False)
    show_user_from_department = forms.MultipleChoiceField(label=capfirst(_("show user from department")), required=False)

    def __init__(self, user, *args, **kwargs):
        super(UserDetailsForm, self).__init__(*args, **kwargs)
        self.fields["auto_addition_topics"].queryset = user.topics
        choices = []
        processes = [process_class for process_class in chantal_common_utils.get_all_models().itervalues()
                    if issubclass(process_class, models.Process) and not process_class._meta.abstract
                    and process_class not in [models.Process, models.Deposition]]
        department_ids = json.loads(user.samples_user_details.show_user_from_department)
        for department in Department.objects.filter(id__in=department_ids).order_by("name").iterator():
            process_from_department = set(process for process in processes
                                          if ContentType.objects.get_for_model(process) in department.processes.all())
            choices.append((department.name, form_utils.choices_of_content_types(process_from_department)))
        if not choices:
            choices = (("", 9 * "-"),)
        self.fields["default_folded_process_classes"].choices = choices
        self.fields["default_folded_process_classes"].initial = [content_type.id for content_type
                                                     in user.samples_user_details.default_folded_process_classes.iterator()]
        self.fields["default_folded_process_classes"].widget.attrs["size"] = "15"
        self.fields["subscribed_feeds"].choices = form_utils.choices_of_content_types(
            list(get_all_addable_physical_process_models()) + [models.Sample, models.SampleSeries, Topic])
        self.fields["subscribed_feeds"].widget.attrs["size"] = "15"
        self.fields["show_user_from_department"].choices = [(department.pk, department.name)
                                                            for department in Department.objects.iterator()]
        self.fields["show_user_from_department"].initial = (json.loads(user.samples_user_details.show_user_from_department))

    class Meta:
        model = models.UserDetails
        fields = ("auto_addition_topics", "only_important_news", "subscribed_feeds",)


@login_required
def edit_preferences(request, login_name):
    """View for editing preferences of a user.  Note that by giving the
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
    def __change_folded_processes(default_folded_process_classes, user):
        """Creates the new exceptional processes dictionary and saves it into the user details.
        """
        old_default_classes = set(cls.id for cls in ContentType.objects.filter(dont_show_to_user=user.samples_user_details))
        new_default_classes = set(map(int, default_folded_process_classes))
        differences = old_default_classes ^ new_default_classes
        exceptional_processes_dict = json.loads(user.samples_user_details.folded_processes)
        for process_id_list in exceptional_processes_dict.itervalues():
            for process_id in copy.copy(process_id_list):
                try:
                    if models.Process.objects.get(pk=process_id).content_type.id in differences:
                        process_id_list.remove(process_id)
                except models.Process.DoesNotExist:
                    # FixMe: the missing process should be removed from the exceptional_processes_dict
                    pass
        user.samples_user_details.folded_processes = json.dumps(exceptional_processes_dict)
        user.samples_user_details.save()

    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    if not request.user.is_staff and request.user != user:
        raise permissions.PermissionError(request.user, _("You can't access the preferences of another user."))
    initials_mandatory = request.GET.get("initials_mandatory") == "True"
    user_details = user.samples_user_details
    if request.method == "POST":
        user_details_form = UserDetailsForm(user, request.POST, instance=user_details)
        initials_form = form_utils.InitialsForm(user, initials_mandatory, request.POST)
        if user_details_form.is_valid() and initials_form.is_valid():
            __change_folded_processes(user_details_form.cleaned_data["default_folded_process_classes"], user)
            user_details = user_details_form.save(commit=False)
            user_details.show_user_from_department = json.dumps(user_details_form.cleaned_data["show_user_from_department"])
            user_details.default_folded_process_classes = [ContentType.objects.get_for_id(int(id_))
                 for id_ in user_details_form.cleaned_data["default_folded_process_classes"]]
            user_details.save()
            initials_form.save()
            return utils.successful_response(request, _("The preferences were successfully updated."))
    else:
        user_details_form = UserDetailsForm(user, instance=user_details)
        initials_form = form_utils.InitialsForm(user, initials_mandatory)
    return render_to_response(
        "samples/edit_preferences.html",
        {"title": _("Change preferences for {user_name}").format(user_name=get_really_full_name(request.user)),
         "user_details": user_details_form, "initials": initials_form,
         "has_topics": user.topics.exists()},
        context_instance=RequestContext(request))


@login_required
def topics_and_permissions(request, login_name):
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    if not request.user.is_staff and request.user != user:
        raise permissions.PermissionError(
            request.user, _("You can't access the list of topics and permissions of another user."))
    return render_to_response(
        "samples/topics_and_permissions.html",
        {"title": _("Topics and permissions for {user_name}").format(user_name=get_really_full_name(request.user)),
         "topics": user.topics.all(), "managed_topics": user.managed_topics.all(),
         "permissions": permissions.get_user_permissions(user),
         "full_user_name": get_really_full_name(request.user),
         "permissions_url": django.core.urlresolvers.reverse("samples.views.permissions.list_")},
        context_instance=RequestContext(request))
