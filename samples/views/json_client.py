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


u"""Views that are intended only for the Remote Client and AJAX code (called
“JSON clients”).  While also users can visit these links with their browser
directly, it is not really useful what they get there.  Note that the whole
communication to the remote client happens in JSON format.
"""

from __future__ import absolute_import

import sys
from django.db.utils import IntegrityError
from django.db.models import Q
from django.conf import settings
from django.http import Http404
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
import django.contrib.auth.models
import django.contrib.auth
from django.shortcuts import get_object_or_404
from chantal_common.models import Topic
from chantal_common.utils import respond_in_json, JSONClientException
from samples.views import utils
from samples import models, permissions


@login_required
@never_cache
@require_http_methods(["GET"])
def primary_keys(request):
    u"""Return the mappings of names of database objects to primary keys.
    While this can be used by everyone by entering the URL directly, this view
    is intended to be used only by a JSON client program to get primary keys.
    The reason for this is simple: In forms, you have to give primary keys in
    POST data sent to the web server.  However, a priori, the JSON client
    doesn't know them.  Therefore, it can query this view to get them.

    The syntax of the query string to be appended to the URL is very simple.
    If you say::

        ...?samples=01B410,01B402

    you get the primary keys of those two samples::

        {"samples": {"01B410": 5, "01B402": 42}}

    The same works for ``"topics"``, ``"users"``, and ``"external_operators"``.
    You can also mix all tree in the query string.  If you pass ``"*"`` instead
    of a values list, you get *all* primary keys.  For samples, however, this
    is limited to “My Samples”.

    The result is the JSON representation of the resulting nested dictionary.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    query_dict = utils.parse_query_string(request)
    result_dict = {}
    if "topics" in query_dict:
        all_topics = set(topic for topic in Topic.objects.all()
                         if not topic.confidential or topic in request.user.topics.all() or request.user.is_staff)
        if query_dict["topics"] == "*":
            topics = all_topics
        else:
            topicnames = query_dict["topics"].split(",")
            topics = set(topic for topic in all_topics if topic.name in topicnames)
        result_dict["topics"] = dict((topic.name, topic.id) for topic in topics)
    if "samples" in query_dict:
        if query_dict["samples"] == "*":
            result_dict["samples"] = dict(request.user.my_samples.values_list("name", "id"))
        else:
            sample_names = query_dict["samples"].split(",")
            result_dict["samples"] = {}
            for alias, sample_id in models.SampleAlias.objects.filter(name__in=sample_names).values_list("name", "sample"):
                result_dict["samples"].setdefault(alias, []).append(sample_id)
            result_dict["samples"].update(models.Sample.objects.filter(name__in=sample_names).values_list("name", "id"))
    if "users" in query_dict:
        if query_dict["users"] == "*":
            result_dict["users"] = dict(django.contrib.auth.models.User.objects.values_list("username", "id"))
        else:
            user_names = query_dict["users"].split(",")
            # FixMe: Return only *active* users
            result_dict["users"] = dict(django.contrib.auth.models.User.objects.filter(username__in=user_names).
                                        values_list("username", "id"))
    if "external_operators" in query_dict:
        if request.user.is_staff:
            all_external_operators = set(models.ExternalOperator.objects.all())
        else:
            all_external_operators = set(external_operator for external_operator in models.ExternalOperator.objects.all()
                                         if not external_operator.confidential or
                                         external_operator.contact_person == request.user)
        if query_dict["external_operators"] == "*":
            external_operators = all_external_operators
        else:
            external_operator_names = query_dict["external_operators"].split(",")
            external_operators = set(external_operator for external_operator in all_external_operators
                                     if external_operator.name in external_operator_names)
        result_dict["external_operators"] = dict((external_operator.name, external_operator.id)
                                                 for external_operator in external_operators)
    return respond_in_json(result_dict)


# FixMe: This should be merged into `primary_keys`, and instead of the dict in
# ``id_field``, the ``natural_key`` method as described in
# http://docs.djangoproject.com/en/dev/topics/serialization/#serialization-of-natural-keys
# should be used.

@login_required
@never_cache
@require_http_methods(["GET"])
def available_items(request, model_name):
    u"""Returns the unique ids of all items that are already in the database
    for this model.  The point is that it will almost never return primary
    keys.  Instead, it returns the “official” id of the respective model.  This
    may be the number of a deposition, or the sample for a measurement process,
    etc.

    :Parameters:
      - `request`: the current HTTP Request object
      - `model_name`: the name of the database model

    :type request: ``HttpRequest``
    :type model_name: unicode

    :Returns:
      The HTTP response object.  It is a JSON list object with all the ids of
      the objects in the database for the model.

    :rtype: ``HttpResponse``
    """
    if not request.user.is_staff:
        raise permissions.PermissionError(request.user, _(u"Only the administrator can access this resource."))
    for app_name in settings.INSTALLED_APPS:
        try:
            model = sys.modules[app_name + ".models"].__dict__[model_name]
        except KeyError:
            continue
        break
    else:
        raise Http404("Model name not found.")
    # FixMe: Add all interesing models here.
    id_field = {"PDSMeasurement": "number", "SixChamberDeposition": "number",
                "LargeAreaDeposition": "number"}.get(model_name, "id")
    return respond_in_json(list(model.objects.values_list(id_field, flat=True)))


# FixMe: The following two functions must go to Chantal-common.

@require_http_methods(["POST"])
def login_remote_client(request):
    u"""Login for the Chantal Remote Client.  It only supports the HTTP POST
    method and expects ``username`` and ``password``.  AJAX code shouldn't need
    this because it has the cookie already.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object.  It is a JSON boolean object, whether the login
      was successful or not.

    :rtype: ``HttpResponse``
    """
    try:
        username = request.POST["username"]
        password = request.POST["password"]
    except KeyError:
        raise JSONClientException(3, '"username" and/or "password" missing')
    user = django.contrib.auth.authenticate(username=username, password=password)
    if user is not None and user.is_active:
        django.contrib.auth.login(request, user)
        return respond_in_json(True)
    raise JSONClientException(4, "user could not be authenticated")


@require_http_methods(["GET"])
def logout_remote_client(request):
    u"""By requesting this view, the Chantal Remote Client can log out.  This
    view can never fail.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object.  It is a JSON boolean object and always
      ``True``.

    :rtype: ``HttpResponse``
    """
    django.contrib.auth.logout(request)
    return respond_in_json(True)


@require_http_methods(["GET"])
def next_deposition_number(request, letter):
    u"""Send the next free deposition number to a JSON client.

    :Parameters:
      - `request`: the current HTTP Request object
      - `letter`: the letter of the deposition system, see
        `utils.get_next_deposition_number`.

    :type request: ``HttpRequest``
    :type letter: str

    :Returns:
      the next free deposition number for the given apparatus.

    :rtype: ``HttpResponse``
    """
    return respond_in_json(utils.get_next_deposition_number(letter))


def get_next_quirky_name(sample_name, year_digits):
    u"""Returns the next sample name for legacy samples that don't fit into any
    known name scheme.

    :Parameters:
      - `sample_name`: the legacy sample name
      - `year_digits`: the last two digits of the year of creation of the
        sample

    :type sample_name: unicode
    :type year_digits: str

    :Return:
      the Chantal legacy sample name

    :rtype: unicode
    """
    prefixes = set()
    legacy_prefix = year_digits + "-LGCY-"
    for name in models.Sample.objects.filter(name__startswith=legacy_prefix).values_list("name", flat=True):
        prefix, __, original_name = name[len(legacy_prefix):].partition("-")
        if original_name == sample_name:
            prefixes.add(prefix)
    free_prefix = u""
    while free_prefix in prefixes:
        digits = [ord(digit) for digit in free_prefix]
        for i in range(len(digits) - 1, -1 , -1):
            digits[i] += 1
            if digits[i] > 122:
                digits[i] = 97
            else:
                break
        else:
            digits[0:0] = [97]
        free_prefix = u"".join(unichr(digit) for digit in digits)
    return u"{0}{1}-{2}".format(legacy_prefix, free_prefix, sample_name)


@login_required
@require_http_methods(["POST"])
def add_sample(request):
    u"""Adds a new sample to the database.  It is added without processes.
    This view can only be used by admin accounts.  If the query string contains
    ``"legacy=True"``, the sample gets a quirky legacy name (and an appropriate
    alias).

    :Parameters:
      - `request`: the current HTTP Request object; it must contain the sample
        data in the POST data.

    :Returns:
      The primary key of the created sample.  ``False`` if something went
      wrong.  It may return a 404 if the topic or the currently responsible
      person wasn't found.

    :rtype: ``HttpResponse``
    """
    if not request.user.is_staff:
        return respond_in_json(False)
    try:
        name = request.POST["name"]
        current_location = request.POST.get("current_location", u"")
        currently_responsible_person = request.POST.get("currently_responsible_person")
        purpose = request.POST.get("purpose", u"")
        tags = request.POST.get("tags", u"")
        topic = request.POST.get("topic")
    except KeyError:
        return respond_in_json(False)
    if len(name) > 30:
        return respond_in_json(False)
    is_legacy_name = request.GET.get("legacy") == u"True"
    if is_legacy_name:
        year_digits = request.GET.get("timestamp", "")[2:4]
        try:
            int(year_digits)
        except ValueError:
            return respond_in_json(False)
        name = get_next_quirky_name(name, year_digits)[:30]
    if currently_responsible_person:
        currently_responsible_person = get_object_or_404(django.contrib.auth.models.User,
                                                         pk=utils.int_or_zero(currently_responsible_person))
    if topic:
        topic = get_object_or_404(Topic, pk=utils.int_or_zero(topic))
    try:
        sample = models.Sample.objects.create(name=name, current_location=current_location,
                                              currently_responsible_person=currently_responsible_person, purpose=purpose,
                                              tags=tags, topic=topic)
        if is_legacy_name:
            models.SampleAlias.objects.create(name=request.POST["name"], sample=sample)
        else:
            for alias in models.SampleAlias.objects.filter(name=name):
                # They will be shadowed anyway.  Nevertheless, this action is
                # an emergency measure.  Probably the samples the aliases point
                # to should be merged with the sample but this can't be decided
                # automatically.
                alias.delete()
    except IntegrityError:
        return respond_in_json(False)
    sample.watchers.add(request.user)
    return respond_in_json(sample.pk)


@login_required
@require_http_methods(["POST"])
def add_alias(request):
    u"""Adds a new sample alias name to the database.  This view can only be
    used by admin accounts.

    :Parameters:
      - `request`: the current HTTP Request object; it must contain the
        sample's primary key and the alias name in the POST data.

    :type request: ``HttpRequest``

    :Returns:
      ``True`` if it worked, ``False`` if something went wrong.  It returns a
      404 if the sample wasn't found.

    :rtype: ``HttpResponse``
    """
    if not request.user.is_staff:
        return respond_in_json(False)
    try:
        sample_pk = request.POST["sample"]
        alias = request.POST["alias"]
    except KeyError:
        return respond_in_json(False)
    sample = get_object_or_404(models.Sample, pk=utils.int_or_zero(sample_pk))
    try:
        models.models.SampleAlias.create(name=alias, sample=sample)
    except IntegrityError:
        # Alias already present
        return respond_in_json(False)
    return respond_in_json(True)


@login_required
@require_http_methods(["POST"])
def change_my_samples(request):
    u"""Adds or remove samples from “My Samples”.

    :Parameters:
      - `request`: The current HTTP Request object.  It must contain the sample
        IDs of the to-be-removed samples comma-separated list in ``"remove"``
        and the to-be-added sample IDs in ``"add"``.  Both can be empty.

    :type request: ``HttpRequest``

    :Returns:
      ``True`` if it worked, ``False`` if something went wrong.  It returns a
      404 if one sample wasn't found.

    :rtype: ``HttpResponse``
    """
    try:
        sample_ids_to_remove = [int(id_) for id_ in request.POST.get("remove", "").split(",") if id_]
        sample_ids_to_add = [int(id_) for id_ in request.POST.get("add", "").split(",") if id_]
    except ValueError:
        raise Http404("One or more of the sample IDs were invalid.")
    # taken from `samples.views.sample.search`.
    base_query = models.Sample.objects.filter(Q(topic__confidential=False) | Q(topic__members=request.user) |
                                              Q(currently_responsible_person=request.user) |
                                              Q(clearances__user=request.user) | Q(topic__isnull=True)).distinct()
    try:
        samples_to_remove = models.Sample.objects.in_bulk(sample_ids_to_remove)
        samples_to_add = base_query.in_bulk(sample_ids_to_add)
    except models.Sample.DoesNotExist:
        raise Http404("One or more of the sample IDs could not be found.")
    request.user.my_samples.remove(*samples_to_remove.values())
    request.user.my_samples.add(*samples_to_add.values())
    return respond_in_json(True)
