#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

from django.template import RequestContext
from django.shortcuts import render_to_response
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from .. import utils


class SimpleSearchForm(forms.Form):
    u"""Form class for the simple search filters.  Currently, it only accepts a
    RefDB query string.
    """

    _ = ugettext_lazy
    query_string = forms.CharField(label=_("Query string"), required=False)


@login_required
def main_menu(request):
    u"""Generates the main page with simple search and main reference list.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    search_form = SimpleSearchForm()
    references = utils.get_refdb_connection(request.user).get_references(":ID:>0", listname=utils.refdb_username(request.user.pk))
    print len(references)
    return render_to_response("main_menu.html", {"title": _(u"Main menu"), "search": search_form, "references": references},
                              context_instance=RequestContext(request))
