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


"""Model for the main menu view and some miscellaneous views that don't have a
better place to be (yet).
"""

from __future__ import absolute_import, unicode_literals, division

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from samples import models, permissions
from django.http import HttpResponsePermanentRedirect, Http404
import django.core.urlresolvers
import django.forms as forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from samples.views import utils
from chantal_common.utils import help_link, is_json_requested, respond_in_json
from chantal_common.models import Topic


class MySeries(object):
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

    :type sample_series: `models.SampleSeries`
    :type name: unicode
    :type timestamp: ``datetime.datetime``
    :type samples: list of `models.Sample`
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

        :Parameters:
          - `sample`: the sample

        :type sample: `models.Sample`
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


# Translators: This is a page name in the Chantal wiki
@help_link(_("MainMenu"))
@login_required
def main_menu(request):
    """The main menu view.  It displays the sample series in a dynamic way,
    and the actions that depend on the specific permissions a user has.  The
    rest is served static.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    my_topics, topicless_samples = utils.build_structured_sample_list(request.user.my_samples.all(), request.user)
    allowed_physical_processes = permissions.get_allowed_physical_processes(request.user)
    lab_notebooks = []
    for process in allowed_physical_processes:
        try:
            url = django.core.urlresolvers.reverse("lab_notebook_" + process["type"], kwargs={"year_and_month": ""})
        except django.core.urlresolvers.NoReverseMatch:
            pass
        else:
            lab_notebooks.append({"label": process["label_plural"], "url": url})
    return render_to_response(
        "samples/main_menu.html",
        {"title": _("Main menu"),
         "my_topics": my_topics,
         "topicless_samples": topicless_samples,
         "add_sample_url": django.core.urlresolvers.reverse(settings.ADD_SAMPLE_VIEW),
         "user_hash": permissions.get_user_hash(request.user),
         "can_add_topic": permissions.has_permission_to_edit_topic(request.user),
         "can_edit_topics": any(permissions.has_permission_to_edit_topic(request.user, topic)
                                for topic in Topic.objects.all()),
         "can_add_external_operator": permissions.has_permission_to_add_external_operator(request.user),
         "has_external_contacts": request.user.external_contacts.exists() or request.user.is_superuser,
         "physical_processes": allowed_physical_processes,
         "lab_notebooks": lab_notebooks},
        context_instance=RequestContext(request))


class SearchDepositionsForm(forms.Form):
    """Tiny form class that just allows to enter a pattern for the deposition
    search.  Currently, the search is case-insensitive, and arbitrary parts of
    the deposition number are matched.
    """
    _ = ugettext_lazy
    number_pattern = forms.CharField(label=_("Deposition number pattern"), max_length=30, required=False)


max_results = 50
"""Maximal number of search results to be displayed."""
@login_required
def deposition_search(request):
    """View for search for depositions.  Currently, this search is very
    rudimentary: It is only possible to search for substrings in deposition
    numbers.  Sometime this should be expanded for a more fine-grained search,
    possibly with logical operators between the search criteria.

    Note this this view is used for both getting the search request from the
    user *and* displaying the search results.  It supports only the GET method.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
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
    return render_to_response("samples/search_depositions.html", {"title": _("Search for deposition"),
                                                                  "search_depositions": search_depositions_form,
                                                                  "found_depositions": found_depositions,
                                                                  "too_many_results": too_many_results,
                                                                  "max_results": max_results},
                              context_instance=RequestContext(request))


@login_required
def show_deposition(request, deposition_number):
    """View for showing depositions by deposition number, no matter which type
    of deposition they are.  It is some sort of dispatch view, which
    immediately redirecty to the actual deposition view.  Possibly it is
    superfluous, or at least only sensible to users who enter URL addresses
    directly.

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: the number of the deposition to be displayed

    :type request: ``HttpRequest``
    :type deposition_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    deposition = get_object_or_404(models.Deposition, number=deposition_number).actual_instance
    return HttpResponsePermanentRedirect(deposition.get_absolute_url())


@login_required
def show_process(request, process_id):
    """Show an existing physical process.  This is some sort of fallback view
    in case a process doesn't provide its own show view.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the ID or the process

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    process = get_object_or_404(models.Process, id=utils.convert_id_to_int(process_id)).actual_instance
    if not isinstance(process, models.PhysicalProcess):
        raise Http404("No physical process with that ID was found.")
    permissions.assert_can_view_physical_process(request.user, process)
    if is_json_requested(request):
        return respond_in_json(process.get_data().to_dict())
    template_context = {"title": unicode(process), "samples": process.samples.all(), "process": process}
    template_context.update(utils.digest_process(process, request.user))
    return render_to_response("samples/show_process.html", template_context, context_instance=RequestContext(request))
