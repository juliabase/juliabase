#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views that are intended only for the Remote Client.  While also users can
visit these links with their browser directly, it is not really useful what
they get there.  Note that the whole communication to the remote client happens
in JSON format.
"""

from __future__ import absolute_import

import sys
from django.db.utils import IntegrityError
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
from samples.views import utils
from samples import models, permissions


@login_required
@never_cache
@require_http_methods(["GET"])
def primary_keys(request):
    u"""Return the mappings of names of database objects to primary keys.
    While this can be used by everyone by entering the URL directly, this view
    is intended to be used only by the remote client program to get primary
    keys.  The reason for this is simple: In forms, you have to give primary
    keys in POST data sent to the web server.  However, a priori, the remote
    client doesn't know them.  Therefore, it can query this view to get them.

    The syntax of the query string to be appended to the URL is very simple.
    If you say::

        ...?samples=01B410,01B402

    you get the primary keys of those two samples::

        {"samples": {"01B410": 5, "01B402": 42}}

    The same works for ``"topics"`` and ``"users"``.  You can also mix all
    tree in the query string.  If you pass ``"*"`` instead of a values list,
    you get *all* primary keys.  For samples, however, this is limited to
    “My Samples”.

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
                         if not topic.restricted or topic in request.user.topics)
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
                                         if not external_operator.restricted or
                                         external_operator.contact_person == request.user)
        if query_dict["external_operators"] == "*":
            external_operators = all_external_operators
        else:
            external_operator_names = query_dict["external_operators"].split(",")
            external_operators = set(external_operator for external_operator in all_external_operators
                                     if external_operator.name in external_operator_names)
        result_dict["external_operators"] = dict((external_operator.name, external_operator.id)
                                                 for external_operator in external_operators)
    return utils.respond_to_remote_client(result_dict)


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
        raise Http404(_("Model name not found."))
    # FixMe: Add all interesing models here.
    id_field = {"PDSMeasurement": "number"}.get(model_name, "id")
    return utils.respond_to_remote_client(list(model.objects.values_list(id_field, flat=True)))


@require_http_methods(["POST"])
def login_remote_client(request):
    u"""Login for the Chantal Remote Client.  It only supports the HTTP POST
    method and expects ``username`` and ``password``.

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
        return utils.respond_to_remote_client(False)
    user = django.contrib.auth.authenticate(username=username, password=password)
    if user is not None and user.is_active:
        django.contrib.auth.login(request, user)
        return utils.respond_to_remote_client(True)
    return utils.respond_to_remote_client(False)


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
    return utils.respond_to_remote_client(True)


@require_http_methods(["GET"])
def next_deposition_number(request, letter):
    u"""Send the next free deposition number to the Chantal Remote Client.

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
    return utils.respond_to_remote_client(utils.get_next_deposition_number(letter))


def get_next_quirky_name(sample_name):
    u"""Returns the next sample name for legacy samples that don't fit into any
    known name scheme.

    :Parameters:
      - `sample_name`: the legacy sample name

    :type sample_name: unicode

    :Return:
      the Chantal legacy sample name

    :rtype: unicode
    """
    prefixes = set()
    for name in models.Sample.objects.filter(name__startswith="LGCY-").values_list("name", flat=True):
        prefix, __, original_name = name[8:].partition("-")
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
    return u"LGCY-{0}-{1}".format(free_prefix, sample_name)


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
        return utils.respond_to_remote_client(False)
    try:
        name = request.POST["name"]
        current_location = request.POST.get("current_location", u"")
        currently_responsible_person = request.POST.get("currently_responsible_person")
        purpose = request.POST.get("purpose", u"")
        tags = request.POST.get("tags", u"")
        topic = request.POST.get("topic")
    except KeyError:
        return utils.respond_to_remote_client(False)
    is_legacy_name = request.GET.get("legacy") == u"True"
    if is_legacy_name:
        name = get_next_quirky_name(name)
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
        return utils.respond_to_remote_client(False)
    sample.watchers.add(request.user)
    return utils.respond_to_remote_client(sample.pk)


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
        return utils.respond_to_remote_client(False)
    try:
        sample_pk = request.POST["sample"]
        alias = request.POST["alias"]
    except KeyError:
        return utils.respond_to_remote_client(False)
    sample = get_object_or_404(models.Sample, pk=utils.int_or_zero(sample_pk))
    try:
        models.models.SampleAlias.create(name=alias, sample=sample)
    except IntegrityError:
        # Alias already present
        return utils.respond_to_remote_client(False)
    return utils.respond_to_remote_client(True)
