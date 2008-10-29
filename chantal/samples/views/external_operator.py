#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for showing, editing, and creating external operators.
"""

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
import django.contrib.auth.models
from chantal.samples import models, permissions
from chantal.samples.views import utils

class AddExternalOperatorForm(forms.ModelForm):
    u"""Model form for creating a new external operator.  The
    ``contact_person`` is implicitly the currently logged-in user.
    """
    _ = ugettext_lazy
    def __init__(self, user, *args, **keyw):
        super(AddExternalOperatorForm, self).__init__(*args, **keyw)
        self.user = user
        for fieldname in ["name", "email", "alternative_email"]:
            self.fields[fieldname].widget.attrs["size"] = "40"
        self.fields["institution"].widget.attrs["size"] = "60"
    def save(self):
        external_operator = super(AddExternalOperatorForm, self).save(commit=False)
        external_operator.contact_person = self.user
        external_operator.save()
        return external_operator
    class Meta:
        model = models.ExternalOperator
        exclude = ("contact_person",)

@login_required
def new(request):
    u"""View for adding a new external operator.
    
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
        if external_operator_form.is_valid():
            external_operator = external_operator_form.save()
            return utils.successful_response(request, _(u"The external operator “%s” was successfully added." %
                                                        external_operator.name))
    else:
        external_operator_form = AddExternalOperatorForm(request.user)
    return render_to_response("edit_external_operator.html", {"title": _(u"Add external operator"),
                                                              "external_operator": external_operator_form},
                              context_instance=RequestContext(request))
    

class EditExternalOperatorForm(forms.ModelForm):
    u"""Model form for editing an existing external operator.  Here, you can
    also change the contact person.
    """
    _ = ugettext_lazy
    contact_person = utils.OperatorChoiceField(label=_(u"Concact person"),
                                               queryset=django.contrib.auth.models.User.objects.all())
    def __init__(self, *args, **keyw):
        super(EditExternalOperatorForm, self).__init__(*args, **keyw)
        for fieldname in ["name", "email", "alternative_email"]:
            self.fields[fieldname].widget.attrs["size"] = "40"
        self.fields["institution"].widget.attrs["size"] = "60"
    class Meta:
        model = models.ExternalOperator

@login_required
def edit(request, external_operator_id):
    u"""View for editing existing external operators.  You can also give the
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
        external_operator_form = EditExternalOperatorForm(request.POST, instance=external_operator)
        initials_form = utils.InitialsForm(external_operator, initials_mandatory=False, data=request.POST)
        if external_operator_form.is_valid() and initials_form.is_valid():
            external_operator = external_operator_form.save()
            initials_form.save()
            return utils.successful_response(request, _(u"The external operator “%s” was successfully changed.") %
                                                        external_operator.name)
    else:
        external_operator_form = EditExternalOperatorForm(instance=external_operator)
        initials_form = utils.InitialsForm(external_operator, initials_mandatory=False)
    return render_to_response("edit_external_operator.html",
                              {"title": _(u"Edit external operator “%s”") % external_operator.name,
                               "external_operator": external_operator_form,
                               "initials": initials_form},
                              context_instance=RequestContext(request))

@login_required
def show(request, external_operator_id):
    u"""View for displaying existing external operators.  Only users who are
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
    permissions.assert_can_view_external_operator(request.user, external_operator)
    try:
        initials = external_operator.initials
    except models.Initials.DoesNotExist:
        initials = None
    return render_to_response("show_external_operator.html",
                              {"title": _(u"External operator “%(name)s”") % {"name": external_operator.name},
                               "external_operator": external_operator, "initials": initials,
                               "can_edit": request.user == external_operator.contact_person},
                              context_instance=RequestContext(request))

@login_required
def list_(request):
    u"""View for listing all external contacts of the currently logged-in user
    for selecting one to edit it.  If you have no external contacts, a 404 is
    generated.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    external_operators = list(request.user.external_contacts.all())
    if not external_operators:
        raise Http404(_("You have no external contacts."))
    return render_to_response("list_external_operators.html",
                              {"title": _(u"All you external contacts"), "external_operators": external_operators},
                              context_instance=RequestContext(request))
