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


"""Views for showing, editing, and creating external operators.
"""

from __future__ import absolute_import, unicode_literals

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
import django.contrib.auth.models
from samples import models, permissions
from samples.views import utils, form_utils


class AddExternalOperatorForm(forms.ModelForm):
    """Model form for creating a new external operator.  The
    ``contact_persons`` is implicitly the currently logged-in user.
    """
    _ = ugettext_lazy

    def __init__(self, user, *args, **kwargs):
        super(AddExternalOperatorForm, self).__init__(*args, **kwargs)
        self.user = user
        for fieldname in ["name", "email", "alternative_email"]:
            self.fields[fieldname].widget.attrs["size"] = "40"
        self.fields["institution"].widget.attrs["size"] = "60"

    def save(self):
        external_operator = super(AddExternalOperatorForm, self).save()
        external_operator.contact_persons.add(self.user)
        return external_operator

    class Meta:
        model = models.ExternalOperator
        exclude = ("contact_persons",)


@login_required
def new(request):
    """View for adding a new external operator.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_add_external_operator(request.user)
    if request.method == "POST":
        external_operator_form = AddExternalOperatorForm(request.user, request.POST)
        initials_form = form_utils.InitialsForm(person=None, initials_mandatory=True, data=request.POST)
        if external_operator_form.is_valid() and initials_form.is_valid():
            external_operator = external_operator_form.save()
            initials_form.save(external_operator)
            return utils.successful_response(
                request,
                _("The external operator “{operator}” was successfully added.".format(operator=external_operator.name)))
    else:
        external_operator_form = AddExternalOperatorForm(request.user)
        initials_form = form_utils.InitialsForm(person=None, initials_mandatory=True)
    return render_to_response("samples/edit_external_operator.html", {"title": _("Add external operator"),
                                                                      "external_operator": external_operator_form,
                                                                      "initials": initials_form},
                              context_instance=RequestContext(request))


class EditExternalOperatorForm(forms.ModelForm):
    """Model form for editing an existing external operator.  Here, you can
    also change the contact person.
    """
    _ = ugettext_lazy
    contact_persons = form_utils.MultipleUsersField(label=_("Contact persons"))

    def __init__(self, user, *args, **kwargs):
        super(EditExternalOperatorForm, self).__init__(*args, **kwargs)
        self.external_operator = kwargs.get("instance")
        for fieldname in ["name", "email", "alternative_email"]:
            self.fields[fieldname].widget.attrs["size"] = "40"
        self.fields["institution"].widget.attrs["size"] = "60"
        self.fields["contact_persons"].set_users(user, self.external_operator.contact_persons.all())

    class Meta:
        model = models.ExternalOperator


@login_required
def edit(request, external_operator_id):
    """View for editing existing external operators.  You can also give the
    operator initials here.

    :Parameters:
      - `request`: the current HTTP Request object
      - `external_operator_id`: the database ID for the external operator

    :type request: ``HttpRequest``
    :type `external_operator_id`: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
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
    initials_form = form_utils.InitialsForm(external_operator, initials_mandatory=True)
    return render_to_response("samples/edit_external_operator.html",
                              {"title": _("Edit external operator “{operator}”").format(operator=external_operator.name),
                               "external_operator": external_operator_form,
                               "initials": initials_form},
                              context_instance=RequestContext(request))


@login_required
def show(request, external_operator_id):
    """View for displaying existing external operators.  Only users who are
    allowed to see all samples, and the current contact person are allowed to
    see it.

    :Parameters:
      - `request`: the current HTTP Request object
      - `external_operator_id`: the database ID for the external operator

    :type request: ``HttpRequest``
    :type `external_operator_id`: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
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
    return render_to_response("samples/show_external_operator.html",
                              {"title": title,
                               "external_operator": external_operator, "initials": initials,
                               "contact_persons" : contact_persons,
                               "can_edit": request.user in contact_persons},
                              context_instance=RequestContext(request))


@login_required
def list_(request):
    """View for listing all external contacts of the currently logged-in user
    for selecting one to edit it.  If you have no external contacts, a 404 is
    generated.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    if request.user.is_superuser:
        external_operators = list(models.ExternalOperator.objects.all())
    else:
        external_operators = list(request.user.external_contacts.all())
    if not external_operators:
        raise Http404("You have no external contacts.")
    return render_to_response("samples/list_external_operators.html",
                              {"title": _("All you external contacts"), "external_operators": external_operators},
                              context_instance=RequestContext(request))
