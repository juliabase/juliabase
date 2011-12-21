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


from __future__ import absolute_import, unicode_literals

from django.template import RequestContext
from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
import django.forms as forms
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.decorators import login_required
from . import utils, models
from .utils import help_link


class SandboxForm(forms.Form):
    """Form for entering Markdown markup just for testing it.
    """
    _ = ugettext_lazy
    sandbox = forms.CharField(label=_("Sandbox"), widget=forms.Textarea, required=False)

    def clean_sandbox(self):
        """Forbid image and headings syntax in Markdown markup.
        """
        sandbox = self.cleaned_data["sandbox"]
        utils.check_markdown(sandbox)
        return sandbox


@help_link(_("MarkdownMarkup"))
def markdown_sandbox(request):
    """View so that the user can test Markdown syntax.  I deliberately decided
    not to *explain* Markdown on this page.  Rather, I recommend the help page
    in the Wiki.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    extracted_content = None
    if request.method == "POST":
        sandbox_form = SandboxForm(request.POST)
        if sandbox_form.is_valid():
            extracted_content = sandbox_form.cleaned_data["sandbox"]
    else:
        sandbox_form = SandboxForm()
    return render_to_response("chantal_common/markdown_sandbox.html",
                              {"title": _("Markdown sandbox"), "sandbox": sandbox_form,
                               "extracted_content": extracted_content},
                              context_instance=RequestContext(request))


@login_required
def switch_language(request):
    """This view parses the query string and extracts a language code from it,
    then switches the current user's prefered language to that language, and
    then goes back to the last URL.  This is used for realising the language
    switching by the flags on the top left.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    language = request.GET.get("lang")
    if language in dict(models.languages):
        user_details = request.user.chantal_user_details
        user_details.language = language
        user_details.save()
    return utils.successful_response(request)


def show_error_page(request, hash_value):
    """Shows an error page.  See `models.ErrorPage` for further information.

    :Parameters:
      - `request`: the current HTTP Request object
      - `hash_value`: the hash value (primary key) of the error page

    :type request: ``HttpRequest``
    :type hash_value: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    html = get_object_or_404(models.ErrorPage, hash_value=hash_value).html
    return HttpResponse(html)
