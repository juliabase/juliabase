#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pyrefdb
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from .. import utils


class ReferenceForm(forms.Form):
    _ = ugettext_lazy
    reference_type = forms.ChoiceField(label=_("Type"), choices=utils.reference_types.items())
    part_title = forms.CharField(label=_("Title"), required=False)
    part_authors = forms.CharField(label=_("Authors"), required=False)

    def __init__(self, reference, *args, **kwargs):
        super(ReferenceForm, self).__init__(*args, **kwargs)


@login_required
def edit(request, citation_key):
    if citation_key:
        reference = utils.get_refdb_connection(request.user).get_references(":CK:=" + citation_key)
        if not reference:
            raise Http404("Citation key \"%s\" not found." % citation_key)
    else:
        reference = None
    if request.method == "POST":
        reference_form = ReferenceForm(reference, request.POST)
    else:
        reference_form = ReferenceForm(reference)
    title = _(u"Edit reference") if citation_key else _(u"Add reference")
    return render_to_response("edit_reference.html", {"title": title, "reference": reference_form},
                              context_instance=RequestContext(request))


@login_required
def view(request, citation_key):
    reference = utils.get_refdb_connection(request.user).get_references(":CK:=" + citation_key)
    if not reference:
        raise Http404("Citation key \"%s\" not found." % citation_key)
    return render_to_response("show_reference.html", {"title": _(u"View reference"), "body": reference[0]},
                              context_instance=RequestContext(request))
