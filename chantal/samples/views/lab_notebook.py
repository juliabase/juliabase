#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""View for the lab notebooks for physical processes.  This is a generic view.
The concrete data extraction work is done in the ``get_lab_notebook_context``
methods of physical process models, and the layout work is done in the
``lab_notebook_<class_name_of_process>.html`` templates.

Furthermore, if you'd like to add a lab notebook function, you must add its URL
explicitly to ``urls.py``.  Look at the large-area deposition entry as an
example.
"""

import datetime, re
from django.http import Http404
from django.shortcuts import render_to_response
import django.core.urlresolvers
from django.template import Context, loader, RequestContext
import django.forms as forms
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.decorators import login_required
from django.utils.http import urlquote_plus
from chantal.samples import models, permissions
from chantal.samples.views import utils, csv_export
from chantal.samples.csv_common import CSVNode


class YearMonthForm(forms.Form):
    u"""Form for the year/month fields in which the user can see which month is
    currently selected, and also change it.
    """
    _ = ugettext_lazy
    year = forms.IntegerField(label=_(u"year"), min_value=1990)
    month = forms.IntegerField(label=_(u"month"), min_value=1, max_value=12)

    def __init__(self, *args, **kwargs):
        super(YearMonthForm, self).__init__(*args, **kwargs)
        self.fields["year"].widget.attrs["size"] = 3
        self.fields["month"].widget.attrs["size"] = 3


year_and_month_pattern = re.compile(r"(?P<year>\d{4})/(?P<month>\d{1,2})$")
def parse_year_and_month(year_and_month):
    u"""Parse the URL suffix in the lab notebook URL which is supposed to
    contain year and month.

    :Parameters:
      - `year_and_month`: the year-and-month part of the URL given in the
        request, i.e. of the form ``"YYYY/MM"`` (the month may be single-digit)

    :type year_and_month: unicode

    :Return:
      year found in the URL, month found in the URL; if ``year_and_month`` was
      empty, return the *current* year and month

    :rtype: int, int

    :Exceptions:
      - `Http404`: if the year-and-month string has an invalid format, or month
        and year refer to an invalid date, or the year precedes 1990.
    """
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


def get_previous_next_urls(process_name, year, month):
    u"""Determine the full relative URLs (i.e., only the domain is missing) of
    the previous and next month in the lab notebook, taking the current lab
    notebook view as the starting point.
    
    :Parameters:
      - `process_name`: the class name of the model of the physical process,
        e.g. ``"LargeAreaDeposition"``
      - `year`: year of the current view
      - `month`: month of the current view

    :type process_name: str
    :type year: int
    :type month: int

    :Return:
      the full relative URL to the previous month, the full relative URL to the
      next month

    :rtype: unicode, unicode
    """
    previous_year = next_year = year
    previous_month = next_month = month
    previous_url = next_url = None
    previous_month -= 1
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1
    if previous_year >= 1990:
        previous_url = django.core.urlresolvers.reverse(
            "lab_notebook_"+process_name, kwargs={"year_and_month": "%d/%d" % (previous_year, previous_month)})
    next_month += 1
    if next_month == 13:
        next_month = 1
        next_year += 1
    next_url = django.core.urlresolvers.reverse(
        "lab_notebook_"+process_name, kwargs={"year_and_month": "%d/%d" % (next_year, next_month)})
    return previous_url, next_url

    
@login_required
def show(request, process_name, year_and_month):
    u"""View for showing one month of the lab notebook for a particular
    physical process.  In ``urls.py``, you must give the entry for this view
    the name ``"lab_notebook_<process_name>"``.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_name`: the class name of the model of the physical process,
        e.g. ``"LargeAreaDeposition"``
      - `year_and_month`: the year and month to be displayed in the format
        ``YYYY/MM`` (the month may be single-digit)

    :type request: ``HttpRequest``
    :type process_name: str
    :type year_and_month: str

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    process_class = models.physical_process_models[process_name]
    permissions.assert_can_view_lab_notebook(request.user, process_class)
    year, month = parse_year_and_month(year_and_month)
    if request.method == "POST":
        year_month_form = YearMonthForm(request.POST)
        if year_month_form.is_valid():
            return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse(
                    "lab_notebook_"+process_name,
                    kwargs={"year_and_month": "%(year)d/%(month)d" % year_month_form.cleaned_data}))
    else:
        year_month_form = YearMonthForm(initial={"year": year, "month": month})
    template = loader.get_template("lab_notebook_" + utils.camel_case_to_underscores(process_name) + ".html")
    template_context = process_class.get_lab_notebook_context(year, month)
    html_body = template.render(Context(template_context))
    previous_url, next_url = get_previous_next_urls(process_name, year, month)
    try:
        export_url = django.core.urlresolvers.reverse(
            "export_lab_notebook_"+process_name,
            kwargs={"year_and_month": year_and_month}) + "?next=" + urlquote_plus(request.path)
    except django.core.urlresolvers.NoReverseMatch:
        export_url = None
    return render_to_response(
        "lab_notebook.html", {"title": _(u"Lab notebook for %s") % process_class._meta.verbose_name_plural,
                              "year": year, "month": month, "year_month": year_month_form,
                              "html_body": html_body, "previous_url": previous_url, "next_url": next_url,
                              "export_url": export_url},
        context_instance=RequestContext(request))


@login_required
def export(request, process_name, year_and_month):
    u"""View for exporting a month of a lab notebook to CSV data.  Thus, the
    return value is not an HTML response but a text/csv response.  In
    ``urls.py``, you must give the entry for this view the name
    ``"export_lab_notebook_<process_name>"``.
    
    :Parameters:
      - `request`: the current HTTP Request object
      - `process_name`: the class name of the model of the physical process,
        e.g. ``"LargeAreaDeposition"``
      - `year_and_month`: the year and month to be displayed in the format
        ``YYYY/MM`` (the month may be single-digit)

    :type request: ``HttpRequest``
    :type process_name: str
    :type year_and_month: str

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    process_class = models.physical_process_models[process_name]
    permissions.assert_can_view_lab_notebook(request.user, process_class)
    year, month = parse_year_and_month(year_and_month)
    data = process_class.get_lab_notebook_data(year, month)
    return csv_export.export(request, data, _(u"process"), renaming_offset=2)
