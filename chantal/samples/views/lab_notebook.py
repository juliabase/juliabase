#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime, re
from django.http import Http404
from django.shortcuts import render_to_response
import django.core.urlresolvers
from django.template import Context, loader, RequestContext
import django.forms as forms
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.decorators import login_required
from chantal.samples import models, permissions
from chantal.samples.views import utils

class YearMonthForm(forms.Form):
    _ = ugettext_lazy
    year = forms.IntegerField(label=_(u"Year"), min_value=1990)
    month = forms.IntegerField(label=_(u"Month"), min_value=1, max_value=12)
    def __init__(self, *args, **kwargs):
        super(YearMonthForm, self).__init__(*args, **kwargs)
        self.fields["year"].widget.attrs["size"] = 3
        self.fields["month"].widget.attrs["size"] = 3

year_and_month_pattern = re.compile(r"(?P<year>\d{4})/(?P<month>\d{1,2})$")
def parse_year_and_month(year_and_month):
    if not year_and_month:
        today = datetime.date.today()
        return today.year, today.month
    match = year_and_month_pattern.match(year_and_month)
    if not match:
        raise Http404("Invalid year and/or month")
    year, month = int(match.group("year")), int(match.group("month"))
    if not 1990 <= year or not 1 <= month <= 12:
        raise Http404("Invalid year and/or month")
    return year, month
    
@login_required
def show(request, process_name, year_and_month):
    process_class = models.physical_process_models[process_name]
    permissions.assert_can_view_lab_notebook(request.user, process_class)
    year, month = parse_year_and_month(year_and_month)
    if request.method == "POST":
        year_month_form = YearMonthForm(request.POST)
        if year_month_form.is_valid():
            return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse(
                    show, kwargs={"process_name": process_name,
                                  "year_and_month": "%(year)d/%(month)d" % year_month_form.cleaned_data}))
    else:
        year_month_form = YearMonthForm()
    template = loader.get_template("lab_notebook_" + utils.camel_case_to_underscores(process_name) + ".html")
    template_context = process_class.get_lab_notebook_data(year, month)
    table_body = template.render(Context(template_context))
    return render_to_response("lab_notebook.html", {"title": _(u"Lab notebook for %s") % process_class._meta.verbose_name,
                                                    "year": year, "month": month,
                                                    "table_body": table_body},
                              context_instance=RequestContext(request))

