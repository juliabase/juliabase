#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Model for the main menu view and some miscellaneous views that don't have a
better place to be (yet).
"""

from __future__ import division
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples import models, permissions
from django.http import HttpResponsePermanentRedirect
import django.forms as forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from chantal.samples.views import utils
from chantal.samples.views.utils import help_link

class MySeries(object):
    u"""Helper class to pass sample series data to the main menu template.  It
    is used in `main_menu`.  This is *not* a data strcuture for sample series.
    It just stores all data needed to display a certain sample series to a
    certain user, besing on his groups an “My Samples”.

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
        u"""Adds a sample to this sample series view.

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

@help_link(_(u"MainMenu"))
@login_required
def main_menu(request):
    u"""The main menu view.  So far, it displays only the sample series in a
    dynamic way.  The rest is served static, which must be changed: The
    processes that are offered to you “for addition” must be according to your
    permissions for processes.  The same is true for “add samples” – this also
    is not allowed for everyone.
    
    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user_details = utils.get_profile(request.user)
    my_series = {}
    seriesless_samples = []
    for sample in user_details.my_samples.all():
        containing_series = sample.series.all()
        if not containing_series:
            seriesless_samples.append(sample)
        else:
            for series in containing_series:
                if series.name not in my_series:
                    my_series[series.name] = MySeries(series)
                my_series[series.name].append(sample)
    my_series = sorted(my_series.itervalues(), key=lambda series: series.timestamp, reverse=True)
    physical_processes = []
    for cls in permissions.get_allowed_physical_processes(request.user):
        # FixMe: This try block should vanish
        try:
            url, label = cls.get_add_link()
        except NotImplementedError:
            continue
        physical_processes.append({"url": url, "label": cls._meta.verbose_name})
    return render_to_response(
        "main_menu.html",
        {"title": _(u"Main menu"),
         "my_series": my_series,
         "seriesless_samples": seriesless_samples,
         "user_hash": permissions.get_user_hash(request.user),
         "can_edit_group_memberships": permissions.has_permission_to_edit_group_memberships(request.user),
         "can_add_external_operator": permissions.has_permission_to_add_external_operator(request.user),
         "has_external_contacts": request.user.external_contacts.count() > 0,
         "physical_processes": physical_processes},
        context_instance=RequestContext(request))

class SearchDepositionsForm(forms.Form):
    u"""Tiny form class that just allows to enter a pattern for the deposition
    search.  Currently, the search is case-insensitive, and arbitrary parts of
    the deposition number are matched.
    """
    _ = ugettext_lazy
    number_pattern = forms.CharField(label=_(u"Deposition number pattern"), max_length=30)

max_results = 50
u"""Maximal number of search results to be displayed."""
@login_required
def deposition_search(request):
    u"""View for search for depositions.  Currently, this search is very
    rudimentary: It is only possible to search for substrings in deposition
    numbers.  Sometime this should be expanded for a more fine-grained search,
    possibly with logical operators between the search criteria.

    Note this this view is used for both getting the search request from the
    user *and* displaying the search results.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    found_depositions = []
    too_many_results = False
    if request.method == "POST":
        search_depositions_form = SearchDepositionsForm(request.POST)
        if search_depositions_form.is_valid():
            found_depositions = \
                models.Deposition.objects.filter(number__icontains=search_depositions_form.cleaned_data["number_pattern"])
            too_many_results = found_depositions.count() > max_results
            found_depositions = found_depositions.all()[:max_results] if too_many_results else found_depositions.all()
            found_depositions = [deposition.find_actual_instance() for deposition in found_depositions]
    else:
        search_depositions_form = SearchDepositionsForm()
    return render_to_response("search_depositions.html", {"title": _(u"Search for deposition"),
                                                          "search_depositions": search_depositions_form,
                                                          "found_depositions": found_depositions,
                                                          "too_many_results": too_many_results,
                                                          "max_results": max_results},
                              context_instance=RequestContext(request))

@login_required
def show_deposition(request, deposition_number):
    u"""View for showing depositions by deposition number, no matter which type
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
    deposition = get_object_or_404(models.Deposition, number=deposition_number).find_actual_instance()
    return HttpResponsePermanentRedirect(deposition.get_absolute_url())

@login_required
def switch_language(request):
    u"""This view parses the query string and extracts a language code from it,
    then switches the current user's prefered language to that language, and
    then goes back to the last URL.  This is used for realising the language
    switching by the flags on the top left.
    
    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    query_dict = utils.parse_query_string(request)
    language = query_dict.get("lang")
    if language in dict(models.languages):
        user_details = utils.get_profile(request.user)
        user_details.language = language
        user_details.save()
    return utils.successful_response(request)
