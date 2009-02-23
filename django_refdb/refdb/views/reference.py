#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import with_statement

from django.template import RequestContext
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
import pyrefdb


@login_required
def view(request, citation_key):
    references = pyrefdb.Connection("drefdbuser%d" % request.user.id).get_references(":ID:>0")
    print references
    return render_to_response("view_reference.html", {"title": _(u"View reference")},
                              context_instance=RequestContext(request))
