#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


"""Helper classes and function for the views that are used for the institute.
It supplements :py:mod:`samples.views.form_utils` with institute specific
classes and functions.
"""

from __future__ import absolute_import, unicode_literals
from django.utils.six.moves import urllib

import re
from django.shortcuts import render
from django.utils.translation import ugettext as _
import django.core.urlresolvers
from django.forms.util import ValidationError
from django.contrib import messages
from jb_common.utils.base import capitalize_first_letter
from samples import permissions
import samples.utils.views as utils


def edit_depositions(request, deposition_number, form_set, institute_model, edit_url, rename_conservatively=False):
    """This function is the central view for editing, creating, and duplicating for
    any deposition.  The edit functions in the deposition views are wrapper
    functions who provides this function with the specific informations.  If
    `deposition_number` is ``None``, a new depositon is created (possibly by
    duplicating another one).

    :param request: the HTTP request object
    :param deposition_number: the number (=name) or the deposition
    :param form_set: the related formset object for the deposition
    :param institute_model: the related Database model
    :param edit_url: the location of the edit template
    :param rename_conservatively: If ``True``, rename only provisional and
        cleaning process names.  This is used by the Large Sputter deposition.
        See the ``new_names`` parameter in
        `samples.views.split_after_deposition.forms_from_database` for how this
        is achieved

    :type request: QueryDict
    :type deposition_number: unicode or NoneType
    :type form_set: FormSet
    :type institute_model: `samples.models.Deposition`
    :type edit_url: unicode
    :type rename_conservatively: bool

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    permissions.assert_can_add_edit_physical_process(request.user, form_set.deposition, institute_model)
    if request.method == "POST":
        form_set.from_post_data(request.POST)
        deposition = form_set.save_to_database()
        if deposition:
            if form_set.remove_from_my_samples_form and \
                    form_set.remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(deposition.samples.all(), form_set.user)
            next_view = next_view_kwargs = None
            query_string = ""
            newly_finished = deposition.finished and (not form_set.deposition or getattr(form_set, "unfinished", False))
            if newly_finished:
                rename = False
                new_names = {}
                if rename_conservatively:
                    for sample in deposition.samples.all():
                        name_format = utils.sample_name_format(sample.name)
                        if name_format == "provisional" or name_format == "old" and sample.name[2] in ["N", "V"]:
                            rename = True
                        elif name_format == "old":
                            new_names[sample.id] = sample.name
                else:
                    rename = True
                if rename:
                    next_view = "samples.views.split_after_deposition.split_and_rename_after_deposition"
                    next_view_kwargs = {"deposition_number": deposition.number}
                    query_string = urllib.parse.urlencode([("new-name-{0}".format(id_), new_name)
                                                           for id_, new_name in new_names.items()])
            elif not deposition.finished:
                next_view, __, next_view_kwargs = django.core.urlresolvers.resolve(request.path)
                next_view_kwargs["deposition_number"] = deposition.number
            if deposition_number:
                message = _("Deposition {number} was successfully changed in the database."). \
                    format(number=deposition.number)
                json_response = True
            else:
                message = _("Deposition {number} was successfully added to the database.").format(number=deposition.number)
                json_response = deposition.pk
            return utils.successful_response(request, message, next_view, next_view_kwargs or {}, query_string,
                                             forced=next_view is not None, json_response=json_response)
        else:
            messages.error(request, _("The deposition was not saved due to incorrect or missing data."))
    else:
        form_set.from_database(request.GET)
    institute_model_name = capitalize_first_letter(institute_model._meta.verbose_name)
    title = _("Edit {name} “{number}”").format(name=institute_model_name, number=deposition_number) if deposition_number \
        else _("Add {name}").format(name=institute_model._meta.verbose_name)
    title = capitalize_first_letter(title)
    context_dict = {"title": title}
    context_dict.update(form_set.get_context_dict())
    return render(request, edit_url, context_dict)


def three_digits(number):
    """
    :param number: the number of the deposition (only the number after the
        deposition system letter)

    :type number: int

    :return:
      The number filled with leading zeros so that it has at least three
      digits.

    :rtype: unicode
    """
    return "{0:03}".format(number)


deposition_number_pattern = re.compile("\d\d[A-Z]-\d{3,4}$")
def clean_deposition_number_field(value, letter):
    """Checks wheter a deposition number given by the user in a form is a
    valid one.  Note that it does not check whether a deposition with this
    number already exists in the database.  It just checks the syntax of the
    number.

    :param value: the deposition number entered by the user
    :param letter: the single uppercase letter denoting the deposition system;
        it may also be a list containing multiple possibily letters

    :type value: unicode
    :type letter: unicode or list of unicode

    :return:
      the original `value` (unchanged)

    :rtype: unicode

    :raises ValidationError: if the deposition number was not a valid deposition
        number
    """
    if not deposition_number_pattern.match(value):
        # Translators: “YY” is year, “L” is letter, and “NNN” is number
        raise ValidationError(_("Invalid deposition number.  It must be of the form YYL-NNN."))
    if isinstance(letter, list):
        if value[2] not in letter:
            raise ValidationError(_("The deposition letter must be an uppercase “{letter}”.").format(letter=", ".join(letter)))
    else:
        if value[2] != letter:
            raise ValidationError(_("The deposition letter must be an uppercase “{letter}”.").format(letter=letter))
    return value
