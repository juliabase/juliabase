# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2022 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""View for the lab notebooks for physical processes.  This is a generic view.
The concrete data extraction work is done in the ``get_lab_notebook_context``
methods of physical process models, and the layout work is done in the
:file:`lab_notebook_{camel_case_class_name_of_process}.html` templates.

Furthermore, if you'd like to add a lab notebook function, you must add its URL
explicitly to ``urls.py``.  See :py:mod:`samples.utils.urls` for further
information.
"""

import re
from datetime import datetime, timedelta
from dateutil import parser
from urllib.parse import quote_plus
from django.http import Http404, HttpResponse
from django.shortcuts import render
import django.urls
from django.template import loader, RequestContext
import django.forms as forms
from django.utils.translation import gettext_lazy as _, gettext
from django.contrib.auth.decorators import login_required
from django.core.serializers import serialize
from jb_common.utils.base import help_link, HttpResponseSeeOther, get_all_models, camel_case_to_underscores, \
    capitalize_first_letter, get_model_field_names
from samples import permissions
import samples.utils.views as utils
import calendar


class YearMonthForm(forms.Form):
    """Form for the year/month fields in which the user can see which month is
    currently selected, and also change it.
    """
    year = forms.IntegerField(label=_("year"), min_value=1990, max_value=9999)
    month = forms.IntegerField(label=_("month"), min_value=1, max_value=12)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["year"].widget.attrs["style"] = "width: 4em"
        self.fields["month"].widget.attrs["style"] = "width: 4em"


year_and_month_pattern = re.compile(r"(?P<year>\d{4})/(?P<month>\d{1,2})$")
def parse_year_and_month(year_and_month):
    """Parse the URL suffix in the lab notebook URL which is supposed to
    contain year and month.

    :param year_and_month: the year-and-month part of the URL given in the
        request, i.e. of the form ``"YYYY/MM"`` (the month may be single-digit)

    :type year_and_month: str

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

# ---------------------------------------------Ayob added this :)------------------

class DateForm(forms.Form):
    """Form for the date fields in which the user can see which month is
    currently selected, and also change it.
    """
    begin_date = forms.DateField(
        label=_('Begin Date'),
        widget=forms.SelectDateWidget(years=range(1990, 2040))
    )

    end_date = forms.DateField(
        label=_('End Date'),
        widget=forms.SelectDateWidget(years=range(1990, 2040))
    )

    def clean(self):
        cleaned_data = super().clean()
        begin_date = cleaned_data.get('begin_date')
        end_date = cleaned_data.get('end_date')

        # Check if begin_date is less than end_date
        if begin_date and end_date and begin_date >= end_date:
            cleaned_data['begin_date'], cleaned_data['end_date'] = end_date, begin_date

        return cleaned_data




# date_pattern = re.compile(r"(?P<from_year>\d{4})/(?P<from_month>\d{1,2})/(?P<from_day>\d{1,2})/(?P<to_year>\d{4})/(?P<to_month>\d{1,2})/(?P<to_day>\d{1,2})$")
# def parse_dates(dates):
#     """Parse the URL suffix in the lab notebook URL which is supposed to
#     contain year and month.

#     :param year_and_month: the year-and-month part of the URL given in the
#         request, i.e. of the form ``"YYYY/MM"`` (the month may be single-digit)

#     :type year_and_month: str

#     :return:
#       year found in the URL, month found in the URL

#     :rtype: int, int

#     :raises Http404: if the year-and-month string has an invalid format or was
#         empty, or month and year refer to an invalid date, or the year precedes
#         1990.
#     """
#     match = date_pattern.match(dates)
#     if not match:
#         raise Http404("Invalid dates")
#     from_year, from_month, from_day = int(match.group("from_year")), int(match.group("from_month")), int(match.group("from_day"))
#     to_year, to_month, to_day = int(match.group("to_year")), int(match.group("to_month")), int(match.group("to_day"))
    
#     # if not 1990 <= from_year or not 1 <= from_month <= 12:
#     #     raise Http404("Invalid year and/or month")
#     return from_year, from_month, from_day, to_year, to_month, to_day


# def get_previous_next_urls(process_name, namespace, year, month):
#     """Determine the full relative URLs (i.e., only the domain is missing) of
#     the previous and next month in the lab notebook, taking the current lab
#     notebook view as the starting point.

#     :param process_name: the class name of the model of the physical process in
#         camel case, e.g. ``"large_area_deposition"``
#     :param namespace: namespace the lab notebook URL resides in
#     :param year: year of the current view
#     :param month: month of the current view

#     :type process_name: str
#     :type namespace: str
#     :type year: int
#     :type month: int

#     :return:
#       the full relative URL to the previous month, the full relative URL to the
#       next month

#     :rtype: str, str
#     """
#     previous_year = next_year = year
#     previous_month = next_month = month
#     previous_url = next_url = None
#     previous_month -= 1
#     if previous_month == 0:
#         previous_month = 12
#         previous_year -= 1
#     if previous_year >= 1990:
#         previous_url = django.urls.reverse("{}:lab_notebook_{}".format(namespace, process_name),
#                                            kwargs={"year_and_month": "{0}/{1}".format(previous_year, previous_month)})
#     next_month += 1
#     if next_month == 13:
#         next_month = 1
#         next_year += 1
#     next_url = django.urls.reverse("{}:lab_notebook_{}".format(namespace, process_name),
#                                    kwargs={"year_and_month": "{0}/{1}".format(next_year, next_month)})
#     return previous_url, next_url

def get_previous_next_month_urls(process_name, namespace, begin_date, end_date):
    """Determine the full relative URLs (i.e., only the domain is missing) of
    the previous and next month in the lab notebook, taking the current lab
    notebook view as the starting point.

    We pick the previous month before the begin date, and the next month after
    the end date.

    :param process_name: the class name of the model of the physical process in
        camel case, e.g. ``"large_area_deposition"``
    :param namespace: namespace the lab notebook URL resides in
    :param begin_date: begin date of the current view
    :param month: month of the current view

    :type process_name: str
    :type namespace: str
    :type year: int
    :type month: int

    :return:
      the full relative URL to the previous month, the full relative URL to the
      next month

    :rtype: str, str
    """
    begin_date = datetime.strptime(begin_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")


    # Get the first day of the begin_date input month
    first_day_of_month_begin_date = begin_date.replace(day=1).strftime("%Y-%m-%d")

    # Get the last day of the begin_date input month
    last_day_of_month_begin_date = (begin_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    last_day_of_month_begin_date_str = last_day_of_month_begin_date.strftime("%Y-%m-%d")

    # Get the first day of the end_date input month
    first_day_of_month_end_date = end_date.replace(day=1).strftime("%Y-%m-%d")

    # Get the last day of the end_date input month
    last_day_of_month_end_date = (end_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    last_day_of_month_end_date_str = last_day_of_month_end_date.strftime("%Y-%m-%d")

    # Get the first day of the previous month based on the begin_date
    first_day_of_previous_month = (begin_date.replace(day=1) - timedelta(days=1)).replace(day=1)
    first_day_of_previous_month_str = first_day_of_previous_month.strftime("%Y-%m-%d")

    # Get the last day of the previous month based on the begin_date
    last_day_of_previous_month = (begin_date.replace(day=1) - timedelta(days=1))
    last_day_of_previous_month_str = last_day_of_previous_month.strftime("%Y-%m-%d")

    # Get the first day of the next month based on the end_date
    first_day_of_next_month = (end_date.replace(day=1) + timedelta(days=32)).replace(day=1)
    first_day_of_next_month_str = first_day_of_next_month.strftime("%Y-%m-%d")

    # Get the last day of the next month based on the end_date
    last_day_of_next_month = (end_date.replace(day=1) + timedelta(days=64)).replace(day=1) - timedelta(days=1)
    last_day_of_next_month_str = last_day_of_next_month.strftime("%Y-%m-%d")

    # Checking if the previous month and next month are between 1990 and 2039. 
    # I know, hard coding dates == not the best practice, but it works.
    if last_day_of_previous_month.year >= 1990:
        previous_url = django.urls.reverse("{}:lab_notebook_{}".format(namespace, process_name),
                                            kwargs={"begin_date": "{0}".format(first_day_of_previous_month_str),
                                                    "end_date": "{0}".format(last_day_of_previous_month_str)})
    # If the previous month is before 1990, then simply return the current month.
    else:
        previous_url = django.urls.reverse("{}:lab_notebook_{}".format(namespace, process_name),
                                            kwargs={"begin_date": "{0}".format(first_day_of_month_begin_date),
                                                    "end_date": "{0}".format(last_day_of_month_begin_date_str)})

    if last_day_of_next_month.year <= 2039:
        next_url = django.urls.reverse("{}:lab_notebook_{}".format(namespace, process_name),
                                    kwargs={"begin_date": "{0}".format(first_day_of_next_month_str),
                                            "end_date": "{0}".format(last_day_of_next_month_str)})
    # If the next month is after 2039, then simply return the current month.
    else:
        next_url = django.urls.reverse("{}:lab_notebook_{}".format(namespace, process_name),
                                            kwargs={"begin_date": "{0}".format(first_day_of_month_end_date),
                                                    "end_date": "{0}".format(last_day_of_month_end_date_str)})

        

    

    return previous_url, next_url


# @help_link("demo.html#lab-notebooks")
# @login_required
# def show(request, process_name, year_and_month):
#     """View for showing one month of the lab notebook for a particular
#     physical process.  In ``urls.py``, you must give the entry for this view
#     the name ``"lab_notebook_<camel_case_process_name>"``.

#     :param request: the current HTTP Request object
#     :param process_name: the class name of the model of the physical process,
#         e.g. ``"LargeAreaDeposition"``
#     :param year_and_month: the year and month to be displayed in the format
#         ``YYYY/MM`` (the month may be single-digit)

#     :type request: HttpRequest
#     :type process_name: str
#     :type year_and_month: str

#     :return:
#       the HTTP response object

#     :rtype: HttpResponse
#     """
#     process_class = get_all_models()[process_name]
#     process_name = camel_case_to_underscores(process_name)
#     namespace = process_class._meta.app_label
#     permissions.assert_can_view_lab_notebook(request.user, process_class)
#     if not year_and_month:
#         try:
#             timestamp = process_class.objects.latest().timestamp
#         except process_class.DoesNotExist:
#             timestamp = datetime.datetime.today()
#         return HttpResponseSeeOther("{0}/{1}".format(timestamp.year, timestamp.month))
#     year, month = parse_year_and_month(year_and_month)
#     if request.method == "POST":
#         year_month_form = YearMonthForm(request.POST)
#         if year_month_form.is_valid():
#             return HttpResponseSeeOther(django.urls.reverse(
#                 "{}:lab_notebook_{}".format(namespace, process_name),
#                 kwargs={"year_and_month": "{year}/{month}".format(**year_month_form.cleaned_data)}))
#     else:
#         year_month_form = YearMonthForm(initial={"year": year, "month": month})
#     template = loader.get_template("samples/lab_notebook_" + process_name + ".html")
#     template_context = RequestContext(request, process_class.get_lab_notebook_context(year, month))
#     template_context["request"] = request
#     html_body = template.render(template_context.flatten())
#     previous_url, next_url = get_previous_next_urls(process_name, namespace, year, month)
#     try:
#         export_url = django.urls.reverse(
#             "{}:export_lab_notebook_{}".format(namespace, process_name),
#             kwargs={"year_and_month": year_and_month}) + "?next=" + quote_plus(request.path)
#     except django.urls.NoReverseMatch:
#         export_url = None
#     return render(request, "samples/lab_notebook.html",
#                   {"title": capitalize_first_letter(_("lab notebook for {process_name}")
#                                                     .format(process_name=process_class._meta.verbose_name_plural)),
#                    "year": year, "month": month, "year_month": year_month_form,
#                    "html_body": html_body, "previous_url": previous_url, "next_url": next_url,
#                    "export_url": export_url})


def format_date(year, month, day):
    return f'{year}-{month:02d}-{day:02d}'

@login_required
def show(request, process_name, begin_date=False, end_date=False):
    """View for showing a lab notebook in a specified range for a particular
    physical process.  In ``urls.py``, you must give the entry for this view
    the name ``"lab_notebook_<camel_case_process_name>"``.

    :param request: the current HTTP Request object
    :param process_name: the class name of the model of the physical process,
        e.g. ``"LargeAreaDeposition"``
    :param begin_date: the beginning date to be displayed in the format
        ``YYYY/MM/DD`` 

    :type request: HttpRequest
    :type process_name: str
    :type begin_date: str
    :type end_date: str
    

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    # Here we get the current process, namespace and set the permissions
    process_class = get_all_models()[process_name]
    process_name = camel_case_to_underscores(process_name)
    namespace = process_class._meta.app_label
    permissions.assert_can_view_lab_notebook(request.user, process_class)
    
    # If not date is given, pick today's date
    if not begin_date and not end_date:
        try:
            timestamp = process_class.objects.latest().timestamp
        except process_class.DoesNotExist:
            timestamp = datetime.today()
        
        # Pick the last day of the chosen month, then create 
        # formatted begin and end variables that contain
        # the whole date in 8 characters: yyyy-mm-dd
        x, last_day = calendar.monthrange(timestamp.year, timestamp.month)
        begin = format_date(timestamp.year, timestamp.month, 1)
        end = format_date(timestamp.year, timestamp.month, last_day)
        
        return HttpResponseSeeOther("{0}/{1}".format(begin, end))
    
    # Check if the form was submitted by the user
    if request.method == "POST":
        # If yes, send a response with the chosen dates
        date_form = DateForm(request.POST)
        if date_form.is_valid():
            begin_date = date_form.cleaned_data['begin_date']
            end_date = date_form.cleaned_data['end_date']
            return HttpResponseSeeOther(django.urls.reverse(
                "{}:lab_notebook_{}".format(namespace, process_name),
                kwargs={"begin_date": "{begin_date}".format(**date_form.cleaned_data),
                        "end_date": "{end_date}".format(**date_form.cleaned_data)}))
    else:
        # If not, pick the current begin and end dates and create a form
        initial_data = {'begin_date': begin_date,
                        'end_date': end_date}
        date_form = DateForm(initial=initial_data)
    
    # Fetch the template to be used
    template = loader.get_template("samples/lab_notebook_" + process_name + ".html")
    # serialized_data = 0
    # raise ValueError("proc", dir(process_class))
    cols = get_model_field_names(process_class)
    
    if "screenprinter_paste" in process_name or "screenprinter_screen" in process_name or "project" in process_name:
        # If the notebook does not support range search, fetch everything
        # serialized_data = serialize('json', process_class.get_lab_notebook_context_all())
        template_context = RequestContext(request, process_class.get_lab_notebook_context_all())

    else:
        # Fetch all the rows from the table of the chosen process 
        # whose begin and end dates are between the specified range 
        template_context = RequestContext(request, process_class.get_lab_notebook_context_range(begin_date, end_date))
    
    # Render the template
    template_context["request"] = request
    html_body = template.render(template_context.flatten())
    # Get the previous months
    previous_url, next_url = get_previous_next_month_urls(process_name, namespace, begin_date, end_date)
    try:
        # FIXME: I commented the next line since the form is never valid because it might be filled
        # but it might not be bound :/
        # if date_form.is_valid():
        export_url = django.urls.reverse(
            "{}:export_lab_notebook_{}".format(namespace, process_name),
            kwargs={'begin_date': begin_date,
                    'end_date': end_date}) + "?next=" + quote_plus(request.path)
    except django.urls.NoReverseMatch:
        export_url = None
    # Render the final page using html_body from before
    return render(request, "samples/lab_notebook.html",
                  {"title": capitalize_first_letter(_("lab notebook for {process_name}")
                                                    .format(process_name=process_class._meta.verbose_name_plural)),
                        "date_form": date_form,
                   "html_body": html_body,"previous_url": previous_url, "next_url": next_url,
                   "export_url": export_url, "cols": cols})




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


@login_required
def export_range(request, process_name, begin_date, end_date):
    """View for exporting the data of a month of a lab notebook that uses a range date system.  Thus, the
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
    # year, month = parse_year_and_month(year_and_month)
    # begin_date = datetime.strptime(begin_date, '%Y-%m-%d')
    # end_date = datetime.strptime(end_date, '%Y-%m-%d')
    
    # FIXME: This is a quite terrible way to deal with another problem that is
    # ScreenprinterPaste/Screen using physical processes lab notebooks although they are not
    # physical processes. 
    # This causes an error to be thrown when using the date range function. 
    # A possible fix would be simply creating separate pages for displaying 
    # ScreenprinterPaste/Screen to be 
    # normal models instead of physical processes.
    try:
        data = process_class.get_lab_notebook_data_range(begin_date, end_date)
    except:
        data = process_class.get_lab_notebook_data(begin_date, end_date)

    # raise ValueError("data:", data)
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
_ = gettext
