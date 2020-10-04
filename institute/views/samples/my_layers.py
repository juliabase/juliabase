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


"""View for editing the “My Layers” structure.  See
:py:attr:`samples.models.UserDetails.my_steps` for the syntax of the “My Steps”
field.  In the INM institute app, we use My Steps only for deposition layers,
therefore, we call it My Layers.  However, you are free to add views for other
“My …”, and filter the process classes as you need.  The ``my_steps`` field
will always store the union of all these processes.
"""

import re
from django.utils.translation import ugettext_lazy as _, ugettext
from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.forms.utils import ValidationError
import django.contrib.auth.models
from django.contrib import messages
from samples import models, permissions
import samples.utils.views as utils


class MyLayerForm(forms.Form):
    """Form for editing the “My Layers” structure.
    """
    nickname = forms.CharField(label=_("Nickname"))
    deposition_and_layer = forms.CharField(label=_("Layer identifier"),
                                           help_text=_("in the form \"deposition number\"-\"layer number\""))
    delete = forms.BooleanField(label=_("Delete"), required=False)

    def clean_deposition_and_layer(self):
        """Convert the notation ``<deposition number>-<layer number>`` to
        ``(deposition ID, layer number)``.  Additionaly, do some validity
        tests.
        """
        if "-" not in self.cleaned_data["deposition_and_layer"]:
            raise ValidationError(_("Deposition and layer number must be separated by \"-\"."), code="invalid")
        deposition_number, layer_number = self.cleaned_data["deposition_and_layer"].rsplit("-", 1)
        try:
            deposition = models.Deposition.objects.get(number=deposition_number).actual_instance
        except models.Deposition.DoesNotExist:
            raise ValidationError(_("Deposition number doesn't exist."), code="invalid")
        try:
            layer_number = int(layer_number)
        except ValueError:
            raise ValidationError(_("Layer number isn't a number."), code="invalid")
        # FixMe: Handle the case when there is no "layers" attribute
        if not deposition.layers.filter(number=layer_number).exists():
            raise ValidationError(_("This layer does not exist in this deposition."), code="invalid")
        return deposition.id, layer_number


layer_item_pattern = re.compile(r"\s*(?P<nickname>.+?)\s*:\s*(?P<raw_layer_identifier>.+?)\s*(?:,\s*|\Z)")
def forms_from_database(user):
    """Generate the “My Layers” forms for the current user.  Convert the
    notation ``<deposition ID>-<layer number>`` of the database to
    ``<deposition number>-<layer number>``.

    :param user: the current user

    :type user: django.contrib.auth.models.User

    :return:
      the “My Layers” forms

    :rtype: list of `MyLayerForm`
    """
    my_layer_forms = []
    for nickname, process_id, layer_number in user.samples_user_details.my_steps:
        # We know that there are only depositions in ``my_steps``
        deposition_number = models.Process.objects.get(pk=process_id).actual_instance.number
        deposition_and_layer = "{0}-{1}".format(deposition_number, layer_number)
        my_layer_forms.append(MyLayerForm(initial={"nickname": nickname, "deposition_and_layer": deposition_and_layer},
                                          prefix=str(len(my_layer_forms))))
    return my_layer_forms


def forms_from_post_data(post_data):
    """Interpret the POST data and create bound forms for with the “My Layers”
    from it.  This also includes the functionality of the ``change_structure``
    function found in other modules.

    :param post_data: the result from ``request.POST``

    :type post_data: QueryDict

    :return:
      list of “My Layers” forms, whether the structure was changed (i.e. a
      layer was deleted or added)

    :rtype: list of `MyLayerForm`, bool
    """
    my_layer_forms = []
    structure_changed = False
    index = 0
    while True:
        if "{0}-nickname".format(index) not in post_data:
            break
        if "{0}-delete".format(index) in post_data:
            structure_changed = True
        else:
            my_layer_forms.append(MyLayerForm(post_data, prefix=str(index)))
        index += 1
    if my_layer_forms and not post_data["{0}-nickname".format(index - 1)]:
        del my_layer_forms[-1]
    else:
        structure_changed = True
    return my_layer_forms, structure_changed


def is_referentially_valid(my_layer_forms):
    """Test whether no nickname occurs twice.

    :return:
      whether all nicknames are unique

    :rtype: bool
    """
    referentially_valid = True
    nicknames = set()
    for my_layer_form in my_layer_forms:
        if my_layer_form.is_valid():
            nickname = my_layer_form.cleaned_data["nickname"]
            if nickname in nicknames:
                my_layer_form.add_error(None, ValidationError(_("Nickname is already given."), code="duplicate"))
                referentially_valid = False
            else:
                nicknames.add(nickname)
    return referentially_valid


def save_to_database(my_layer_forms, user):
    """Save the new “My Layers” into the database.
    """
    user_details = user.samples_user_details
    old_layers = user_details.my_steps
    user_details.my_steps = [(form.cleaned_data["nickname"],) + form.cleaned_data["deposition_and_layer"]
                             for form in my_layer_forms]

    if not old_layers == user_details.my_steps:
        user_details.save()
        return  _("Successfully changed “My Layers”")
    else:
        return  _("Nothing changed.")

@login_required
def edit(request, login_name):
    """View for editing the “My Layers”.

    :param request: the current HTTP Request object
    :param login_name: the login name of the user whose “My Layers” should be
        changed

    :type request: HttpRequest
    :type login_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    if not request.user.is_superuser and request.user != user:
        raise permissions.PermissionError(request.user, _("You can't access the “My Layers” section of another user."))
    if request.method == "POST":
        my_layer_forms, structure_changed = forms_from_post_data(request.POST)
        all_valid = all([my_layer_form.is_valid() for my_layer_form in my_layer_forms])
        referentially_valid = is_referentially_valid(my_layer_forms)
        if all_valid and referentially_valid and not structure_changed:
            result = save_to_database(my_layer_forms, user)
            return utils.successful_response(request, result)
        elif all_valid and referentially_valid and structure_changed:
            messages.error(request, _("Changes are not saved yet."))
    else:
        my_layer_forms = forms_from_database(user)
    my_layer_forms.append(MyLayerForm(prefix=str(len(my_layer_forms))))
    return render(request, "samples/edit_my_layers.html", {"title": _("My Layers"), "my_layers": my_layer_forms})


_ = ugettext
