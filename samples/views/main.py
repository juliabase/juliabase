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


"""Model for the main menu view and some miscellaneous views that don't have a
better place to be (yet).
"""

from django.shortcuts import render, get_object_or_404
from samples import models, permissions
from django.http import HttpResponsePermanentRedirect, Http404
from django.views.decorators.http import require_http_methods
import django.urls
import django.forms as forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext_lazy as _, ugettext
from jb_common.utils.base import help_link, is_json_requested, respond_in_json, get_all_models, unquote_view_parameters, \
    int_or_zero
from jb_common.models import Topic
import samples.utils.views as utils
from samples.models import ExternalOperator, Process


class MySeries:
    """Helper class to pass sample series data to the main menu template.  It
    is used in `main_menu`.  This is *not* a data strcuture for sample series.
    It just stores all data needed to display a certain sample series to a
    certain user, basing on his topics in “My Samples”.

    :ivar sample_series: the sample series for which data should be collected
      in this object
    :ivar name: the name of the sample series
    :ivar timestamp: the creation timestamp of the sample series
    :ivar samples: all samples belonging to this sample series, *and* being
      part of “My Samples” of the current user
    :ivar is_complete: a read-only property.  If ``False``, there are samples
      in the sample series not included into the list because they were missing
      on “My Samples”.  In other words, the user deliberately gets an
      incomplete list of samples and should be informed about it.

    :type sample_series: `samples.models.SampleSeries`
    :type name: str
    :type timestamp: datetime.datetime
    :type samples: list of `samples.models.Sample`
    :type is_complete: bool
    """

    def __init__(self, sample_series):
        self.sample_series = sample_series
        self.name = sample_series.name
        self.timestamp = sample_series.timestamp
        self.samples = []
        self.__is_complete = None

    def append(self, sample):
        """Adds a sample to this sample series view.

        :param sample: the sample

        :type sample: `samples.models.Sample`
        """
        assert self.__is_complete is None
        self.samples.append(sample)

    @property
    def is_complete(self):
        if self.__is_complete is None:
            sample_series_length = self.sample_series.samples.count()
            assert sample_series_length >= len(self.samples)
            self.__is_complete = sample_series_length == len(self.samples)
        return self.__is_complete


@help_link("demo.html#the-my-samples-list")
@login_required
def main_menu(request):
    """The main menu view.  It displays the “My Samples” list in a dynamic way, and
    the actions that depend on the specific permissions a user has.  The rest
    is served static.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    my_topics, topicless_samples = utils.build_structured_sample_list(request.user)
    allowed_physical_processes = permissions.get_allowed_physical_processes(request.user)
    lab_notebooks = permissions.get_lab_notebooks(request.user)
    return render(request, "samples/main_menu.html",
                  {"title": _("Main menu"),
                   "my_topics": my_topics,
                   "topicless_samples": topicless_samples,
                   "add_samples_url": django.urls.reverse(settings.ADD_SAMPLES_VIEW),
                   "user_hash": permissions.get_user_hash(request.user),
                   "can_add_topic": permissions.has_permission_to_edit_users_topics(request.user),
                   "can_edit_topics": permissions.can_edit_any_topics(request.user),
                   "can_add_external_operator": permissions.has_permission_to_add_external_operator(request.user),
                   "has_external_contacts": permissions.can_edit_any_external_contacts(request.user),
                   "can_rename_samples": request.user.has_perm("samples.rename_samples"),
                   "physical_processes": allowed_physical_processes,
                   "lab_notebooks": lab_notebooks})


class SearchDepositionsForm(forms.Form):
    """Tiny form class that just allows to enter a pattern for the deposition
    search.  Currently, the search is case-insensitive, and arbitrary parts of
    the deposition number are matched.
    """
    number_pattern = forms.CharField(label=_("Deposition number pattern"), max_length=30, required=False)


max_results = 50
"""Maximal number of search results to be displayed.
"""
@login_required
def deposition_search(request):
    """View for search for depositions.  Currently, this search is very
    rudimentary: It is only possible to search for substrings in deposition
    numbers.  Sometime this should be expanded for a more fine-grained search,
    possibly with logical operators between the search criteria.

    Note this this view is used for both getting the search request from the
    user *and* displaying the search results.  It supports only the GET method.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    found_depositions = []
    too_many_results = False
    search_depositions_form = SearchDepositionsForm(request.GET)
    if search_depositions_form.is_valid():
        number_pattern = search_depositions_form.cleaned_data["number_pattern"]
        if number_pattern:
            found_depositions = models.Deposition.objects.filter(number__icontains=number_pattern)
            too_many_results = found_depositions.count() > max_results
            found_depositions = found_depositions[:max_results] if too_many_results else found_depositions
            found_depositions = [deposition.actual_instance for deposition in found_depositions]
    return render(request, "samples/search_depositions.html", {"title": _("Search for deposition"),
                                                               "search_depositions": search_depositions_form,
                                                               "found_depositions": found_depositions,
                                                               "too_many_results": too_many_results,
                                                               "max_results": max_results})


@login_required
@unquote_view_parameters
def show_deposition(request, deposition_number):
    """View for showing depositions by deposition number, no matter which type
    of deposition they are.  It is some sort of dispatch view, which
    immediately redirecty to the actual deposition view.  Possibly it is
    superfluous, or at least only sensible to users who enter URL addresses
    directly.

    :param request: the current HTTP Request object
    :param deposition_number: the number of the deposition to be displayed

    :type request: HttpRequest
    :type deposition_number: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    deposition = get_object_or_404(models.Deposition, number=deposition_number).actual_instance
    return HttpResponsePermanentRedirect(deposition.get_absolute_url())


@login_required
@unquote_view_parameters
def show_process(request, process_id, process_name="Process"):
    """Show an existing physical process.  This is some sort of fallback view in
    case a process doesn't provide its own show view (which is mostly the
    case).

    The ``process_id`` needn't be the ``"id"`` field: If `process_name` is not
    ``None``, its ``JBMeta.identifying_field``, it given, is used instead for
    the lookup.

    :param request: the current HTTP Request object
    :param process_id: the ID or the process's identifying field value
    :param process_name: the class name of the process; if ``None``, ``Process``
        is assumed

    :type request: HttpRequest
    :type process_id: str
    :type process_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    process_class = get_all_models()[process_name]
    try:
        identifying_field = process_class.JBMeta.identifying_field
    except AttributeError:
        identifying_field = "id"
    try:
        process = get_object_or_404(process_class, **{identifying_field: process_id}).actual_instance
    except ValueError:
        raise Http404("Invalid value for {} passed: {}".format(identifying_field, repr(process_id)))
    if not isinstance(process, models.PhysicalProcess):
        raise Http404("No physical process with that ID was found.")
    permissions.assert_can_view_physical_process(request.user, process)
    if is_json_requested(request):
        return respond_in_json(process.get_data())
    template_context = {"title": str(process), "samples": process.samples.all(), "process": process}
    template_context.update(utils.digest_process(process, request.user))
    return render(request, "samples/show_process.html", template_context)


@login_required
@require_http_methods(["POST"])
@unquote_view_parameters
def delete_process(request, process_id):
    """Deletes an existing physical process.

    :param request: the current HTTP Request object
    :param process_id: the process's ID

    :type request: HttpRequest
    :type process_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    process = get_object_or_404(Process, pk=int_or_zero(process_id)).actual_instance
    affected_objects = permissions.assert_can_delete_physical_process(request.user, process)
    for instance in affected_objects:
        if isinstance(instance, models.Sample):
            utils.Reporter(request.user).report_deleted_sample(instance)
        elif isinstance(instance, models.Process):
            utils.Reporter(request.user).report_deleted_process(instance)
    success_message = _("Process {process} was successfully deleted in the database.").format(process=process)
    process.delete()
    return utils.successful_response(request, success_message)


@login_required
@require_http_methods(["GET"])
@unquote_view_parameters
def delete_process_confirmation(request, process_id):
    """View for confirming that you really want to delete the given process.
    Typically, it is visited by clicking on an icon.

    :param request: the current HTTP Request object
    :param process_id: the ID of the process

    :type request: HttpRequest
    :type process_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    process = get_object_or_404(Process, pk=int_or_zero(process_id)).actual_instance
    affected_objects = permissions.assert_can_delete_physical_process(request.user, process)
    digested_affected_objects = {}
    for instance in affected_objects:
        try:
            class_name = instance.__class__._meta.verbose_name_plural.title()
        except AttributeError:
            class_name = capfirst(_("miscellaneous"))
        digested_affected_objects.setdefault(class_name, set()).add(instance)
    return render(request, "samples/delete_process_confirmation.html",
                  {"title": _("Delete process “{process}”").format(process=process), "process": process,
                   "affected_objects": digested_affected_objects})


_ = ugettext
