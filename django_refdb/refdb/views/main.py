#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

from django.template import RequestContext
from django.shortcuts import render_to_response
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy


def main_menu(request):
    return render_to_response("main_menu.html", {"title": _(u"Main menu")}, context_instance=RequestContext(request))
