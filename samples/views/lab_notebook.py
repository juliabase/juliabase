#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""View for the lab notebooks for physical processes.  This is a generic view.
The concrete data extraction work is done in the ``get_lab_notebook_context``
methods of physical process models, and the layout work is done in the
:file:`lab_notebook_{camel_case_class_name_of_process}.html` templates.

Furthermore, if you'd like to add a lab notebook function, you must add its URL
explicitly to ``urls.py``.  See :py:mod:`samples.url_utils` for further
information.
"""

from __future__ import absolute_import, unicode_literals

import datetime, re
from django.http import Http404, HttpResponse
from django.shortcuts import render
import django.core.urlresolvers
from django.template import loader, RequestContext
import django.forms as forms
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.decorators import login_required
from django.utils.http import urlquote_plus
from samples import permissions
from samples.views import utils
from jb_common.utils import HttpResponseSeeOther, get_all_models


class YearMonthForm(forms.Form):
    """Form for the year/month fields in which the user can see which month is
    currently selected, and also change it.
    """
    _ = ugettext_lazy
    year = forms.IntegerField(label=_("year"), min_value=1990)
    month = forms.IntegerField(label=_("month"), min_value=1, max_value=12)

    def __init__(self, *args, **kwargs):
        super(YearMonthForm, self).__init__(*args, **kwargs)
        self.fields["year"].widget.attrs["size"] = 3
        self.fields["month"].widget.attrs["size"] = 3


year_and_month_pattern = re.compile(r"(?P<year>\d{4})/(?P<month>\d{1,2})$")
def parse_year_and_month(year_and_month):
    """Parse the URL suffix in the lab notebook URL which is supposed to
    contain year and month.

    :param year_and_month: the year-and-month part of the URL given in the
        request, i.e. of the form ``"YYYY/MM"`` (the month may be single-digit)

    :type year_and_month: unicode

    :return:
      year found in the URL, month found in the URL

    :rtype: int, int

    :raises Http404: if the year-and-month string has an invalid format or was
        empty, or month and year refer to an invalid date, or the year precedes
        1990.
    """
    match = year_and_month_pattern.match(year_and_month)
    if not match:
        raise Http404("Invalid year and/or month")
    year, month = int(match.group("year")), int(match.group("month"))
    if not 1990 <= year or not 1 <= month <= 12:
        raise Http404("Invalid year and/or month")
    return year, month


def get_previous_next_urls(process_name, year, month):
    """Determine the full relative URLs (i.e., only the domain is missing) of
    the previous and next month in the lab notebook, taking the current lab
    notebook view as the starting point.

    :param process_name: the class name of the model of the physical process in
        camel case, e.g. ``"large_area_deposition"``
    :param year: year of the current view
    :param month: month of the current view

    :type process_name: str
    :type year: int
    :type month: int

    :return:
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
            "lab_notebook_" + process_name, kwargs={"year_and_month": "{0}/{1}".format(previous_year, previous_month)})
    next_month += 1
    if next_month == 13:
        next_month = 1
        next_year += 1
    next_url = django.core.urlresolvers.reverse(
        "lab_notebook_" + process_name, kwargs={"year_and_month": "{0}/{1}".format(next_year, next_month)})
    return previous_url, next_url


@login_required
def show(request, process_name, year_and_month):
    """View for showing one month of the lab notebook for a particular
    physical process.  In ``urls.py``, you must give the entry for this view
    the name ``"lab_notebook_<camel_case_process_name>"``.

    :param request: the current HTTP Request object
    :param process_name: the class name of the model of the physical process,
        e.g. ``"LargeAreaDeposition"``
    :param year_and_month: the year and month to be displayed in the format
        ``YYYY/MM`` (the month may be single-digit)

    :type request: HttpRequest
    :type process_name: str
    :type year_and_month: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    process_class = get_all_models()[process_name]
    process_name = utils.camel_case_to_underscores(process_name)
    permissions.assert_can_view_lab_notebook(request.user, process_class)
    if not year_and_month:
        try:
            timestamp = process_class.objects.latest().timestamp
        except process_class.DoesNotExist:
            timestamp = datetime.datetime.today()
        return HttpResponseSeeOther("{0}/{1}".format(timestamp.year, timestamp.month))
    year, month = parse_year_and_month(year_and_month)
    if request.method == "POST":
        year_month_form = YearMonthForm(request.POST)
        if year_month_form.is_valid():
            return HttpResponseSeeOther(django.core.urlresolvers.reverse(
                    "lab_notebook_" + process_name,
                    kwargs={"year_and_month": "{year}/{month}".format(**year_month_form.cleaned_data)}))
    else:
        year_month_form = YearMonthForm(initial={"year": year, "month": month})
    template = loader.get_template("samples/lab_notebook_" + process_name + ".html")
    template_context = RequestContext(request, process_class.get_lab_notebook_context(year, month))
    html_body = template.render(template_context)
    previous_url, next_url = get_previous_next_urls(process_name, year, month)
    try:
        export_url = django.core.urlresolvers.reverse(
            "export_lab_notebook_" + process_name,
            kwargs={"year_and_month": year_and_month}) + "?next=" + urlquote_plus(request.path)
    except django.core.urlresolvers.NoReverseMatch:
        export_url = None
    return render(request, "samples/lab_notebook.html",
                  {"title": utils.capitalize_first_letter(_("lab notebook for {process_name}")
                                                          .format(process_name=process_class._meta.verbose_name_plural)),
                   "year": year, "month": month, "year_month": year_month_form,
                   "html_body": html_body, "previous_url": previous_url, "next_url": next_url,
                   "export_url": export_url})


@login_required
def export(request, process_name, year_and_month):
    """View for exporting the data of a month of a lab notebook.  Thus, the
    return value is not an HTML response but a CSV or JSON response.  In
    ``urls.py``, you must give the entry for this view the name
    ``"export_lab_notebook_<process_name>"``.

    :param request: the current HTTP Request object
    :param process_name: the class name of the model of the physical process,
        e.g. ``"LargeAreaDeposition"``
    :param year_and_month: the year and month to be displayed in the format
        ``YYYY/MM`` (the month may be single-digit)

    :type request: HttpRequest
    :type process_name: str
    :type year_and_month: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    process_class = get_all_models()[process_name]
    permissions.assert_can_view_lab_notebook(request.user, process_class)
    year, month = parse_year_and_month(year_and_month)
    data = process_class.get_lab_notebook_data(year, month)
    result = utils.table_export(request, data, _("process"))
    if isinstance(result, tuple):
        column_groups_form, columns_form, table, switch_row_forms, old_data_form = result
    elif isinstance(result, HttpResponse):
        return result
    title = _("Table export for “{name}”").format(name=data.descriptive_name)
    return render(request, "samples/table_export.html", {"title": title, "column_groups": column_groups_form,
                                                         "columns": columns_form,
                                                         "rows": list(zip(table, switch_row_forms)) if table else None,
                                                         "old_data": old_data_form,
                                                         "backlink": request.GET.get("next", "")})
