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


"""
"""

from __future__ import absolute_import, division, unicode_literals

import numpy
from numpy import exp, sqrt, pi, log, interp
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from django.shortcuts import render_to_response
from django.template import RequestContext
import django.forms as forms


def smooth(x, y, window_len=11):
    if x[0] > x[1]:
        x, y = x[::-1], y[::-1]
    x_new = numpy.linspace(x[0], x[-1], len(x))
    y_new = interp(x_new, x, y)
    s = numpy.r_[2*y_new[0] - y_new[window_len:1:-1], y_new, 2*y_new[-1] - y_new[-1:-window_len:-1]]
    w = numpy.hanning(window_len)
    y_smooth = numpy.convolve(w / w.sum(), s, mode=b"same")
    return x_new, y_smooth[window_len-1:-window_len+1]


def get_mean_value(x, y, position, interval):
    y_values = y[(position - interval < x) & (x < position + interval)]
    return y_values.mean()


class PDSFileForm(forms.Form):
    _ = ugettext_lazy
    evaluated_pds_file = forms.FileField(label=_("Evaluated PDS file"))


def evaluation(request):
    if request.method == "POST":
        evaluation_form = PDSFileForm(request.POST, request.FILES)
        try:
            data = "".join(request.FILES["evaluated_pds_file"].chunks())
            x, y = [], []
            started = False
            for line in data.splitlines():
                if not started:
                    if line == "BEGIN":
                        started = True
                else:
                    if line == "END":
                        break
                    x_value, y_value, __ = line.split()
                    x.append(float(x_value))
                    y.append(float(y_value))
            x, y = numpy.array(x), numpy.array(y)
            results = {}
            results["gap_width"] = get_mean_value(y, x, 1e4, 1e3)
            x_smooth, y_smooth = smooth(x, numpy.log(y), 21)
            results["tailwidth"] = 1000 / max(x for x in numpy.diff(y_smooth, 1) / (x_smooth[1] - x_smooth[0]) if x == x)
            results["defects_absorption"] = exp(interp(1.2, x_smooth, y_smooth))
        except:
            results = None
    else:
        evaluation_form = PDSFileForm()
        results = None
    return render_to_response("chantal_institute/pds_evaluation.html",
                              {"title": _("PDS evaluation"), "evaluation": evaluation_form, "results": results},
                              context_instance=RequestContext(request))
