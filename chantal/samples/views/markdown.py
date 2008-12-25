#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""View so that the user can test Markdown syntax.
"""

from django.template import RequestContext
from django.shortcuts import render_to_response
import django.forms as forms
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal.samples.views import utils, form_utils
from chantal.samples.views.utils import help_link


class SandboxForm(forms.Form):
    u"""Form for entering Markdown markup just for testing it.
    """
    _ = ugettext_lazy
    sandbox = forms.CharField(label=_(u"Sandbox"), widget=forms.Textarea, required=False)
    def clean_sandbox(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        sandbox = self.cleaned_data["sandbox"]
        form_utils.check_markdown(sandbox)
        return sandbox


@help_link(_(u"MarkdownMarkup"))
def sandbox(request):
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
