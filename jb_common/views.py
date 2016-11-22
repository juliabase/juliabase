#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
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


from __future__ import absolute_import, unicode_literals

from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
import django.forms as forms
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib.auth.decorators import login_required
from jb_common import models
import jb_common.utils.base as utils
from jb_common.utils.base import help_link, get_really_full_name


@login_required
def show_user(request, login_name):
    """View for showing basic information about a user, like the email address.
    This could be fleshed out with phone number, picture, position, and field
    of interest by overriding this view in the institute app.

    :param request: the current HTTP Request object
    :param login_name: the login name of the user to be shown

    :type request: HttpRequest
    :type login_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    try:
        user = django.contrib.auth.models.User.objects.filter(username=login_name). \
               exclude(jb_user_details__department=None)[0]
    except IndexError:
        raise Http404('No User matches the given query.')
    department = user.jb_user_details.department
    username = get_really_full_name(user)
    return render(request, "jb_common/show_user.html", {"title": username, "shown_user": user, "department": department})


class SandboxForm(forms.Form):
    """Form for entering Markdown markup just for testing it.
    """
    sandbox = forms.CharField(label=_("Sandbox"), widget=forms.Textarea, required=False)

    def clean_sandbox(self):
        """Forbid image and headings syntax in Markdown markup.
        """
        sandbox = self.cleaned_data["sandbox"]
        utils.check_markdown(sandbox)
        return sandbox


@help_link("markdown.html")
def markdown_sandbox(request):
    """View so that the user can test Markdown syntax.  I deliberately decided
    not to *explain* Markdown on this page.  Rather, I recommend the help page
    in the Wiki.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    extracted_content = None
    if request.method == "POST":
        sandbox_form = SandboxForm(request.POST)
        if sandbox_form.is_valid():
            extracted_content = sandbox_form.cleaned_data["sandbox"]
    else:
        sandbox_form = SandboxForm()
    return render(request, "jb_common/markdown_sandbox.html", {"title": _("Markdown sandbox"), "sandbox": sandbox_form,
                                                               "extracted_content": extracted_content})


@login_required
def switch_language(request):
    """This view parses the query string and extracts a language code from it,
    then switches the current user's prefered language to that language, and
    then goes back to the last URL.  This is used for realising the language
    switching by the flags on the top left.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    language = request.GET.get("lang")
    if language in dict(models.languages):
        user_details = request.user.jb_user_details
        user_details.language = language
        user_details.save()
    return utils.successful_response(request)


def show_error_page(request, hash_value):
    """Shows an error page.  See :py:class:`jb_common.models.ErrorPage` for further
    information.

    :param request: the current HTTP Request object
    :param hash_value: the hash value (primary key) of the error page

    :type request: HttpRequest
    :type hash_value: unicode

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    html = get_object_or_404(models.ErrorPage, hash_value=hash_value).html
    return HttpResponse(html)


_ = ugettext
