#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Chantal.  Chantal is published under the MIT license.  A
# copy of this licence is shipped with Chantal in the file LICENSE.


from __future__ import absolute_import

from django.template import RequestContext
from django.shortcuts import render_to_response
import django.forms as forms
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.decorators import login_required
from . import utils, models
from .utils import help_link


class SandboxForm(forms.Form):
    u"""Form for entering Markdown markup just for testing it.
    """
    _ = ugettext_lazy
    sandbox = forms.CharField(label=_(u"Sandbox"), widget=forms.Textarea, required=False)

    def clean_sandbox(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        sandbox = self.cleaned_data["sandbox"]
        utils.check_markdown(sandbox)
        return sandbox


@help_link(_(u"MarkdownMarkup"))
def markdown_sandbox(request):
    u"""View so that the user can test Markdown syntax.  I deliberately decided
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
    return render_to_response("markdown_sandbox.html", {"title": _(u"Markdown sandbox"), "sandbox": sandbox_form,
                                                        "extracted_content": extracted_content},
                              context_instance=RequestContext(request))


@login_required
def switch_language(request):
    u"""This view parses the query string and extracts a language code from it,
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
