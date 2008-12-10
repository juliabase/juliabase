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

def get_previous_next_urls(year, month):
    previous_year = next_year = year
    previous_month = next_month = month
    previous_url = next_url = None
    previous_month -= 1
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1
    if previous_year >= 1990:
        previous_url = \
            django.core.urlresolvers.reverse(show, kwargs={"year_and_month": "%d/%d" % (previous_year, previous_month)})
    next_month += 1
    if next_month == 13:
        next_month = 1
        next_year += 1
    next_url = django.core.urlresolvers.reverse(show, kwargs={"year_and_month": "%d/%d" % (next_year, next_month)})
    return previous_url, next_url
    
@login_required
def show(request, process_name, year_and_month):
    process_class = models.physical_process_models[process_name]
    permissions.assert_can_view_lab_notebook(request.user, process_class)
    year, month = parse_year_and_month(year_and_month)
    if request.method == "POST":
        year_month_form = YearMonthForm(request.POST)
        if year_month_form.is_valid():
            return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse(
                    show, kwargs={"year_and_month": "%(year)d/%(month)d" % year_month_form.cleaned_data}))
    else:
        year_month_form = YearMonthForm(initial={"year": year, "month": month})
    template = loader.get_template("lab_notebook_" + utils.camel_case_to_underscores(process_name) + ".html")
    template_context = process_class.get_lab_notebook_data(year, month)
    html_body = template.render(Context(template_context))
    previous_url, next_url = get_previous_next_urls(year, month)
    return render_to_response(
        "lab_notebook.html", {"title": _(u"Lab notebook for %s") % process_class._meta.verbose_name_plural,
                              "year": year, "month": month, "year_month": year_month_form,
                              "html_body": html_body, "previous_url": previous_url, "next_url": next_url},
        context_instance=RequestContext(request))

