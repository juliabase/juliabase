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


"""Views for showing, editing, and creating external operators.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django import forms
from django.utils.translation import ugettext_lazy as _, ugettext
from django.utils.text import capfirst
import django.contrib.auth.models
from jb_common.utils.views import MultipleUsersField
from samples import models, permissions
import samples.utils.views as utils


class AddExternalOperatorForm(forms.ModelForm):
    """Model form for creating a new external operator.  The
    ``contact_persons`` is implicitly the currently logged-in user.
    """
    class Meta:
        model = models.ExternalOperator
        exclude = ("contact_persons",)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        for fieldname in ["name", "email", "alternative_email"]:
            self.fields[fieldname].widget.attrs["size"] = "40"
        self.fields["institution"].widget.attrs["size"] = "60"

    def save(self):
        external_operator = super().save()
        external_operator.contact_persons.add(self.user)
        return external_operator


@login_required
def new(request):
    """View for adding a new external operator.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    permissions.assert_can_add_external_operator(request.user)
    if request.method == "POST":
        external_operator_form = AddExternalOperatorForm(request.user, request.POST)
        initials_form = utils.InitialsForm(person=None, initials_mandatory=True, data=request.POST)
        if external_operator_form.is_valid() and initials_form.is_valid():
            external_operator = external_operator_form.save()
            initials_form.save(external_operator)
            return utils.successful_response(
                request,
                _("The external operator “{operator}” was successfully added.".format(operator=external_operator.name)))
    else:
        external_operator_form = AddExternalOperatorForm(request.user)
        initials_form = utils.InitialsForm(person=None, initials_mandatory=True)
    return render(request, "samples/edit_external_operator.html", {"title": capfirst(_("add external operator")),
                                                                   "external_operator": external_operator_form,
                                                                   "initials": initials_form})


class EditExternalOperatorForm(forms.ModelForm):
    """Model form for editing an existing external operator.  Here, you can
    also change the contact person.
    """
    contact_persons = MultipleUsersField(label=_("Contact persons"))

    class Meta:
        model = models.ExternalOperator
        fields = "__all__"

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.external_operator = kwargs.get("instance")
        for fieldname in ["name", "email", "alternative_email"]:
            self.fields[fieldname].widget.attrs["size"] = "40"
        self.fields["institution"].widget.attrs["size"] = "60"
        self.fields["contact_persons"].set_users(user, self.external_operator.contact_persons.all())


@login_required
def edit(request, external_operator_id):
    """View for editing existing external operators.  You can also give the
    operator initials here.

    :param request: the current HTTP Request object
    :param external_operator_id: the database ID for the external operator

    :type request: HttpRequest
    :type external_operator_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    external_operator = get_object_or_404(models.ExternalOperator, pk=utils.convert_id_to_int(external_operator_id))
    permissions.assert_can_edit_external_operator(request.user, external_operator)
    if request.method == "POST":
        external_operator_form = EditExternalOperatorForm(request.user, request.POST, instance=external_operator)
        if external_operator_form.is_valid():
            external_operator = external_operator_form.save()
            return utils.successful_response(
                request,
                _("The external operator “{operator}” was successfully changed.").format(operator=external_operator.name))
    else:
        external_operator_form = EditExternalOperatorForm(request.user, instance=external_operator)
    initials_form = utils.InitialsForm(external_operator, initials_mandatory=True)
    return render(request, "samples/edit_external_operator.html",
                  {"title": _("Edit external operator “{operator}”").format(operator=external_operator.name),
                   "external_operator": external_operator_form,
                   "initials": initials_form})


@login_required
def show(request, external_operator_id):
    """View for displaying existing external operators.  Only users who are
    allowed to see all samples, and the current contact person are allowed to
    see it.

    :param request: the current HTTP Request object
    :param external_operator_id: the database ID for the external operator

    :type request: HttpRequest
    :type external_operator_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    external_operator = get_object_or_404(models.ExternalOperator, pk=utils.convert_id_to_int(external_operator_id))
    contact_persons = external_operator.contact_persons.all()
    if permissions.has_permission_to_view_external_operator(request.user, external_operator):
        try:
            initials = external_operator.initials
        except models.Initials.DoesNotExist:
            initials = None
        title = _("External operator “{name}”").format(name=external_operator.name)
    else:
        title = _("Confidential operator #{number}").format(number=external_operator.pk)
        external_operator = None
        initials = None
    return render(request, "samples/show_external_operator.html",
                  {"title": title,
                   "external_operator": external_operator, "initials": initials,
                   "contact_persons" : contact_persons,
                   "can_edit": request.user in contact_persons})


@login_required
def list_(request):
    """View for listing all external contacts of the currently logged-in user
    for selecting one to edit it.  If you have no external contacts, a 404 is
    generated.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    if request.user.is_superuser:
        external_operators = list(models.ExternalOperator.objects.all())
    else:
        external_operators = list(request.user.external_contacts.all())
    if not external_operators:
        raise Http404("You have no external contacts.")
    return render(request, "samples/list_external_operators.html",
                  {"title": _("All you external contacts"), "external_operators": external_operators})


_ = ugettext
