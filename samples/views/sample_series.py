# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""Collected views for dealing with sample series.

Names of sample series are of the form ``originator-YY-name``, where
``originator`` is the person who created the sample series, and ``YY`` is the
year (two digits). ``name`` is almost arbitrary.  Names of sample series can't
be changed once they have been created.
"""

import hashlib, datetime
from django import forms
from django.contrib.auth.decorators import login_required
from django.forms.utils import ValidationError
from django.http import HttpResponse
import django.utils.timezone
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.utils.text import capfirst
from django.views.decorators.http import condition
import django.contrib.auth.models
import jb_common.utils.base
from jb_common.utils.base import unquote_view_parameters
from jb_common.utils.views import UserField, TopicField
from samples import models, permissions
import samples.utils.views as utils


class SampleSeriesForm(forms.ModelForm):
    """Form for editing and creating sample series.
    """
    short_name = forms.CharField(label=capfirst(_("name")), max_length=50)
    currently_responsible_person = UserField(label=capfirst(_("currently responsible person")))
    topic = TopicField(label=capfirst(_("topic")))
    samples = utils.MultipleSamplesField(label=capfirst(_("samples")))

    class Meta:
        model = models.SampleSeries
        exclude = ("timestamp", "results", "name", "id")

    def __init__(self, user, data=None, **kwargs):
        """I have to initialise the form here, especially
        because the sample set to choose from must be found and the name of an
        existing series must not be changed.
        """
        super().__init__(data, **kwargs)
        sample_series = kwargs.get("instance")
        samples = user.my_samples.all()
        important_samples = sample_series.samples.all() if sample_series else set()
        self.fields["samples"].set_samples(user, samples, important_samples)
        self.fields["samples"].widget.attrs.update({"size": "15", "style": "vertical-align: top"})
        self.fields["short_name"].widget.attrs.update({"size": "50"})
        if sample_series:
            self.fields["short_name"].required = False
        if sample_series:
            self.fields["currently_responsible_person"].set_users(user, sample_series.currently_responsible_person)
        else:
            self.fields["currently_responsible_person"].choices = ((user.pk, str(user)),)
        self.fields["topic"].set_topics(user, sample_series.topic if sample_series else None)

    def clean_short_name(self):
        """Prevents users from just adding whitespaces.
        """
        short_name = self.cleaned_data["short_name"].strip()
        if not short_name and self.fields["short_name"].required:
            raise ValidationError(_("This field is required."), code="required")
        return short_name

    def clean_description(self):
        """Forbid image and headings syntax in Markdown markup.
        """
        description = self.cleaned_data["description"]
        jb_common.utils.base.check_markdown(description)
        return description

    def validate_unique(self):
        """Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in the create view itself.  I cannot use Django's
        built-in test anyway because it leads to an error message in wrong
        German (difficult to fix, even for the Django guys).
        """
        pass


def embed_timestamp(request, name):
    """Put a timestamp field in the request object that is used by both
    :py:func:`sample_series_timestamp` and :py:func:`sample_series_etag`.  It's
    really a pity that you can't give *one* function for returning both with
    Django's API for conditional view processing.

    :param request: the current HTTP Request object
    :param name: the name of the sample series

    :type request: HttpRequest
    :type name: str

    :return:
      the timestamp of the last modification of the sample's datasheet

    :rtype: datetime.datetime
    """
    if not hasattr(request, "_sample_series_timestamp"):
        try:
            sample_series = models.SampleSeries.objects.get(name=name)
        except models.SampleSeries.DoesNotExist:
            request._sample_series_timestamp = None
        else:
            request._sample_series_timestamp = max(
                sample_series.last_modified, request.user.samples_user_details.display_settings_timestamp,
                request.user.jb_user_details.layout_last_modified)


def sample_series_timestamp(request, name):
    """Calculate the timestamp of a sample series.  See
    `samples.views.sample.sample_timestamp` for further information.

    :param request: the current HTTP Request object
    :param name: the name of the sample series

    :type request: HttpRequest
    :type name: str

    :return:
      the timestamp of the last modification of the sample series' datasheet

    :rtype: datetime.datetime
    """
    embed_timestamp(request, name)
    return request._sample_series_timestamp


def sample_series_etag(request, name):
    """Calculate an ETag for the sample series page.  See
    `samples.views.sample.sample_timestamp` for further information.

    :param request: the current HTTP Request object
    :param name: the name of the sample series

    :type request: HttpRequest
    :type name: str

    :return:
      the ETag of the sample series' page

    :rtype: str
    """
    embed_timestamp(request, name)
    if request._sample_series_timestamp:
        hash_ = hashlib.sha1()
        hash_.update(str(request._sample_series_timestamp).encode())
        hash_.update(str(request.user.pk).encode())
        return hash_.hexdigest()


@login_required
@unquote_view_parameters
@condition(sample_series_etag, sample_series_timestamp)
def show(request, name):
    """View for showing a sample series.  You can see a sample series if
    you're in its topic, or you're the currently responsible person for it,
    or if you can view all samples anyway.

    :param request: the current HTTP Request object
    :param name: name of the sample series

    :type request: HttpRequest
    :type name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample_series = get_object_or_404(models.SampleSeries, name=name)
    permissions.assert_can_view_sample_series(request.user, sample_series)
    result_processes = [utils.digest_process(result, request.user) for result in sample_series.results.all()]
    can_edit = permissions.has_permission_to_edit_sample_series(request.user, sample_series)
    can_add_result = permissions.has_permission_to_add_result_process(request.user, sample_series)
    return render(request, "samples/show_sample_series.html",
                  {"title": _("Sample series “{name}”").format(name=sample_series.name),
                   "can_edit": can_edit, "can_add_result": can_add_result,
                   "sample_series": sample_series,
                   "result_processes": result_processes})


def is_referentially_valid(sample_series, sample_series_form, edit_description_form):
    """Checks that the “important” checkbox is marked if the topic or the
    currently responsible person were changed.

    :param sample_series: the currently edited sample series
    :param sample_series_form: the bound sample series form
    :param edit_description_form: a bound form with description of edit changes

    :type sample_series: `samples.models.SampleSeries`
    :type sample_series_form: `SampleSeriesForm`
    :type edit_description_form: `samples.utils.views.EditDescriptionForm`

    :return:
      whether the “important” tickbox was really marked in case of significant
      changes

    :rtype: bool
    """
    referentially_valid = True
    if sample_series_form.is_valid() and edit_description_form.is_valid() and \
            (sample_series_form.cleaned_data["topic"] != sample_series.topic or
             sample_series_form.cleaned_data["currently_responsible_person"] !=
             sample_series.currently_responsible_person) and \
             not edit_description_form.cleaned_data["important"]:
        referentially_valid = False
        edit_description_form.add_error("important", ValidationError(
            _("Changing the topic or the responsible person must be marked as important."), code="required"))
    return referentially_valid


@login_required
@unquote_view_parameters
def edit(request, name):
    """View for editing an existing sample series.  Only the currently
    responsible person can edit a sample series.

    :param request: the current HTTP Request object
    :param name: name of the sample series

    :type request: HttpRequest
    :type name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample_series = get_object_or_404(models.SampleSeries, name=name)
    permissions.assert_can_edit_sample_series(request.user, sample_series)
    if request.method == "POST":
        sample_series_form = SampleSeriesForm(request.user, request.POST, instance=sample_series)
        edit_description_form = utils.EditDescriptionForm(request.POST)
        all_valid = sample_series_form.is_valid()
        all_valid = edit_description_form.is_valid() and all_valid
        referentially_valid = is_referentially_valid(sample_series, sample_series_form, edit_description_form)
        if all_valid and referentially_valid:
            edit_description = edit_description_form.cleaned_data
            feed_reporter = utils.Reporter(request.user)
            if sample_series.currently_responsible_person != sample_series_form.cleaned_data["currently_responsible_person"]:
                feed_reporter.report_new_responsible_person_sample_series(sample_series, edit_description)
            if sample_series.topic != sample_series_form.cleaned_data["topic"]:
                feed_reporter.report_changed_sample_series_topic(sample_series, sample_series.topic, edit_description)
            feed_reporter.report_edited_sample_series(sample_series, edit_description)
            sample_series = sample_series_form.save()
            feed_reporter.report_edited_sample_series(sample_series, edit_description)
            return utils.successful_response(
                request,
                _("Sample series {name} was successfully updated in the database.").format(name=sample_series.name))
    else:
        sample_series_form = \
            SampleSeriesForm(request.user, instance=sample_series,
                             initial={"short_name": sample_series.name.split("-", 2)[-1],
                                      "currently_responsible_person": sample_series.currently_responsible_person.pk,
                                      "topic": sample_series.topic.pk,
                                      "samples": [sample.pk for sample in sample_series.samples.all()]})
        edit_description_form = utils.EditDescriptionForm()
    return render(request, "samples/edit_sample_series.html",
                  {"title": _("Edit sample series “{name}”").format(name=sample_series.name),
                   "sample_series": sample_series_form,
                   "is_new": False, "edit_description": edit_description_form})


@login_required
def new(request):
    """View for creating a new sample series.  Note that you can add arbitrary
    samples to a sample series, even those you can't see.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    if request.method == "POST":
        sample_series_form = SampleSeriesForm(request.user, request.POST)
        if sample_series_form.is_valid():
            timestamp = django.utils.timezone.now()
            full_name = "{0}-{1}-{2}".format(
                request.user.username, timestamp.strftime("%y"), sample_series_form.cleaned_data["short_name"])
            if models.SampleSeries.objects.filter(name=full_name).exists():
                sample_series_form.add_error("short_name", ValidationError(_("This sample series name is already given."),
                                                                           code="duplicate"))
            elif len(full_name) > models.SampleSeries._meta.get_field("name").max_length:
                overfull_letters = len(full_name) - models.SampleSeries._meta.get_field("name").max_length
                sample_series_form.add_error("short_name", ValidationError(
                    ungettext("The name is %(number)s letter too long.", "The name is %(number)s letters too long.",
                              overfull_letters), params={"number": overfull_letters}, code="invalid"))
            else:
                sample_series = sample_series_form.save(commit=False)
                sample_series.name = full_name
                sample_series.timestamp = timestamp
                sample_series.save()
                sample_series_form.save_m2m()
                utils.Reporter(request.user).report_new_sample_series(sample_series)
                return utils.successful_response(
                    request, _("Sample series {name} was successfully added to the database.").format(name=full_name))
    else:
        sample_series_form = SampleSeriesForm(request.user)
    return render(request, "samples/edit_sample_series.html",
                  {"title": _("Create new sample series"),
                   "sample_series": sample_series_form,
                   "is_new": True,
                   "name_prefix": "{0}-{1}".format(request.user.username, datetime.datetime.today().strftime("%y"))})


@login_required
@unquote_view_parameters
def export(request, name):
    """View for exporting sample series data in CSV or JSON format.  Thus, the
    return value is not an HTML response.  Note that you must also be allowed
    to see all *samples* in this sample series for the export.

    :param request: the current HTTP Request object
    :param name: the name of the sample series

    :type request: HttpRequest
    :type name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample_series = get_object_or_404(models.SampleSeries, name=name)
    permissions.assert_can_view_sample_series(request.user, sample_series)
    for sample in sample_series.samples.all():
        permissions.assert_can_fully_view_sample(request.user, sample)

    data = sample_series.get_data_for_table_export()
    result = utils.table_export(request, data, _("sample"))
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


_ = ugettext
