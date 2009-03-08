#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

from xml.etree import ElementTree
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from .. import utils


@login_required
def view(request, citation_key):
    reference = utils.get_refdb_connection(request.user).get_references(":CK:=" + citation_key)
    if not reference:
        raise Http404("Citation key \"%s\" not found." % citation_key)
    return render_to_response("show_reference.html", {"title": _(u"View reference"), "body": reference[0]},
                              context_instance=RequestContext(request))
