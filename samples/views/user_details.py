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


"""Views for showing and editing user data, i.e. real names, contact
information, and preferences.
"""

import copy
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django.views.decorators.http import require_http_methods
from django import forms
import django.urls
from django.utils.translation import ugettext_lazy as _, ugettext
from django.utils.text import capfirst
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from jb_common.utils.base import get_really_full_name
import jb_common.utils.base as jb_common_utils
from jb_common.models import Topic, Department
from samples import models, permissions
from samples.permissions import get_all_addable_physical_process_models
import samples.utils.views as utils


class UserDetailsForm(forms.ModelForm):
    """Model form for user preferences.
    """
    subscribed_feeds = forms.MultipleChoiceField(label=capfirst(_("subscribed newsfeeds")), required=False)
    default_folded_process_classes = forms.MultipleChoiceField(label=capfirst(_("folded processes")), required=False)
    show_users_from_departments = forms.MultipleChoiceField(label=capfirst(_("show users from department")), required=False)

    class Meta:
        model = models.UserDetails
        fields = ("auto_addition_topics", "only_important_news", "subscribed_feeds",)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["auto_addition_topics"].queryset = user.topics
        choices = []
        processes = [process_class for process_class in jb_common_utils.get_all_models().values()
                    if issubclass(process_class, models.Process) and not process_class._meta.abstract
                    and process_class not in [models.Process, models.Deposition]]
        for department in user.samples_user_details.show_users_from_departments.iterator():
            processes_from_department = {process for process in processes if process._meta.app_label == department.app_label}
            choices.append((department.name, utils.choices_of_content_types(processes_from_department)))
        self.fields["default_folded_process_classes"].choices = choices
        self.fields["default_folded_process_classes"].initial = [content_type.id for content_type
                                                     in user.samples_user_details.default_folded_process_classes.iterator()]
        self.fields["default_folded_process_classes"].widget.attrs["size"] = "15"
        self.fields["subscribed_feeds"].choices = utils.choices_of_content_types(
            list(get_all_addable_physical_process_models()) + [models.Sample, models.SampleSeries, Topic])
        self.fields["subscribed_feeds"].widget.attrs["size"] = "15"
        self.fields["show_users_from_departments"].choices = [(department.pk, department.name)
                                                            for department in Department.objects.iterator()]
        self.fields["show_users_from_departments"].initial = \
                    list(user.samples_user_details.show_users_from_departments.values_list("id", flat=True))


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

    :param request: the current HTTP Request object
    :param login_name: the login name of the user who's preferences should be
        edited.

    :type request: HttpRequest
    :type login_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    def __change_folded_processes(default_folded_process_classes, user):
        """Creates the new exceptional processes dictionary and saves it into the user details.
        """
        old_default_classes = {cls.id for cls in ContentType.objects.filter(dont_show_to_user=user.samples_user_details)}
        new_default_classes = {int(class_id) for class_id in default_folded_process_classes if class_id}
        differences = old_default_classes ^ new_default_classes
        exceptional_processes_dict = user.samples_user_details.folded_processes
        for process_id_list in exceptional_processes_dict.values():
            for process_id in copy.copy(process_id_list):
                try:
                    if models.Process.objects.get(pk=process_id).content_type.id in differences:
                        process_id_list.remove(process_id)
                except models.Process.DoesNotExist:
                    # FixMe: the missing process should be removed from the exceptional_processes_dict
                    pass
        user.samples_user_details.folded_processes = exceptional_processes_dict
        user.samples_user_details.save()

    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    if not request.user.is_superuser and request.user != user:
        raise permissions.PermissionError(request.user, _("You can't access the preferences of another user."))
    initials_mandatory = request.GET.get("initials_mandatory") == "True"
    user_details = user.samples_user_details
    if request.method == "POST":
        user_details_form = UserDetailsForm(user, request.POST, instance=user_details)
        initials_form = utils.InitialsForm(user, initials_mandatory, request.POST)
        if user_details_form.is_valid() and initials_form.is_valid():
            __change_folded_processes(user_details_form.cleaned_data["default_folded_process_classes"], user)
            user_details = user_details_form.save(commit=False)
            user_details.show_users_from_departments.set(Department.objects.filter(id__in=
                                                        user_details_form.cleaned_data["show_users_from_departments"]))
            user_details.default_folded_process_classes.set([ContentType.objects.get_for_id(int(id_))
                 for id_ in user_details_form.cleaned_data["default_folded_process_classes"]])
            user_details.save()
            user_details_form.save_m2m()
            initials_form.save()
            return utils.successful_response(request, _("The preferences were successfully updated."))
    else:
        user_details_form = UserDetailsForm(user, instance=user_details)
        initials_form = utils.InitialsForm(user, initials_mandatory)
    return render(request, "samples/edit_preferences.html",
                  {"title": _("Change preferences for {user_name}").format(user_name=get_really_full_name(request.user)),
                   "user_details": user_details_form, "initials": initials_form,
                   "has_topics": user.topics.exists()})


@login_required
@require_http_methods(["GET"])
def topics_and_permissions(request, login_name):
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    if not request.user.is_superuser and request.user != user:
        raise permissions.PermissionError(
            request.user, _("You can't access the list of topics and permissions of another user."))
    if jb_common_utils.is_json_requested(request):
        return jb_common_utils.respond_in_json((list(user.topics.values_list("pk", flat=True)),
                                                list(user.managed_topics.values_list("pk", flat=True)),
                                                user.get_all_permissions()))
    return render(request, "samples/topics_and_permissions.html",
                  {"title": _("Topics and permissions for {user_name}").format(user_name=get_really_full_name(request.user)),
                   "topics": user.topics.all(), "managed_topics": user.managed_topics.all(),
                   "permissions": permissions.get_user_permissions(user),
                   "full_user_name": get_really_full_name(request.user),
                   "permissions_url": django.urls.reverse("samples:list_permissions")})


_ = ugettext
