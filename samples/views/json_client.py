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


"""Views that are intended only for the Remote Client and AJAX code (called
“JSON clients”).  While also users can visit these links with their browser
directly, it is not really useful what they get there.  Note that the whole
communication to the remote client happens in JSON format.
"""

from __future__ import absolute_import, unicode_literals

import sys, json
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
from jb_common.models import Topic
from jb_common.utils import respond_in_json, JSONRequestException
from samples.views import utils
from samples import models, permissions
from django.contrib.contenttypes.models import ContentType


@login_required
@never_cache
@require_http_methods(["GET"])
def primary_keys(request):
    """Return the mappings of names of database objects to primary keys.
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
    result_dict = {}
    if "topics" in request.GET:
        all_topics = set(topic for topic in Topic.objects.all()
                         if not topic.confidential or request.user in topic.members.all() or request.user.is_staff)
        if request.GET["topics"] == "*":
            topics = all_topics
        else:
            topicnames = request.GET["topics"].split(",")
            topics = set(topic for topic in all_topics if topic.name in topicnames)
        result_dict["topics"] = dict((topic.name, topic.id) for topic in topics)
    if "samples" in request.GET:
        if request.GET["samples"] == "*":
            result_dict["samples"] = dict(request.user.my_samples.values_list("name", "id"))
        else:
            sample_names = request.GET["samples"].split(",")
            result_dict["samples"] = {}
            for alias, sample_id in models.SampleAlias.objects.filter(name__in=sample_names).values_list("name", "sample"):
                result_dict["samples"].setdefault(alias, []).append(sample_id)
            result_dict["samples"].update(models.Sample.objects.filter(name__in=sample_names).values_list("name", "id"))
    if "depositions" in request.GET:
        deposition_numbers = request.GET["depositions"].split(",")
        result_dict["depositions"] = dict(models.Deposition.objects.
                                          filter(number__in=deposition_numbers).values_list("number", "id"))
    if "users" in request.GET:
        if request.GET["users"] == "*":
            result_dict["users"] = dict(django.contrib.auth.models.User.objects.values_list("username", "id"))
        else:
            user_names = request.GET["users"].split(",")
            # FixMe: Return only *active* users
            result_dict["users"] = dict(django.contrib.auth.models.User.objects.filter(username__in=user_names).
                                        values_list("username", "id"))
    if "external_operators" in request.GET:
        if request.user.is_staff:
            all_external_operators = set(models.ExternalOperator.objects.all())
        else:
            all_external_operators = set(external_operator for external_operator in models.ExternalOperator.objects.all()
                                         if not external_operator.confidential or
                                         request.user in external_operator.contact_persons.all())
        if request.GET["external_operators"] == "*":
            external_operators = all_external_operators
        else:
            external_operator_names = request.GET["external_operators"].split(",")
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
    """Returns the unique ids of all items that are already in the database for
    this model.  The point is that it will return primary keys only as a
    fallback.  Instead, it returns the “official” id of the respective model,
    represented by the result of the `natural_key` method.  This may be the
    number of a deposition, or the name of the sample, etc.

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
        raise permissions.PermissionError(request.user, _("Only the administrator can access this resource."))
    # FixMe: This must be revisited; it is ugly.
    for app_name in settings.INSTALLED_APPS:
        try:
            model = sys.modules[app_name + ".models"].__dict__[model_name]
        except KeyError:
            continue
        break
    else:
        raise Http404("Model name not found.")
    try:
        return respond_in_json([instance.natural_key() for instance in model.objects.all()])
    except AttributeError:
        return respond_in_json(list(model.objects.values_list("pk", flat=True)))


# FixMe: The following two functions must go to jb_common.

@require_http_methods(["POST"])
def login_remote_client(request):
    """Login for the JuliaBase Remote Client.  It only supports the HTTP POST
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
        raise JSONRequestException(3, '"username" and/or "password" missing')
    user = django.contrib.auth.authenticate(username=username, password=password)
    if user is not None and user.is_active:
        django.contrib.auth.login(request, user)
        return respond_in_json(True)
    raise JSONRequestException(4, "user could not be authenticated")


@never_cache
@require_http_methods(["GET"])
def logout_remote_client(request):
    """By requesting this view, the JuliaBase Remote Client can log out.  This
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


@login_required
@require_http_methods(["POST"])
def add_alias(request):
    """Adds a new sample alias name to the database.  This view can only be
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
    sample = get_object_or_404(models.Sample, pk=utils.convert_id_to_int(sample_pk))
    try:
        models.models.SampleAlias.create(name=alias, sample=sample)
    except IntegrityError:
        # Alias already present
        return respond_in_json(False)
    return respond_in_json(True)


@login_required
@require_http_methods(["POST"])
def change_my_samples(request):
    """Adds or remove samples from “My Samples”.

    :Parameters:
      - `request`: The current HTTP Request object.  It must contain the sample
        IDs of the to-be-removed samples comma-separated list in ``"remove"``
        and the to-be-added sample IDs in ``"add"``.  Both can be empty.

    :type request: ``HttpRequest``

    :Returns:
      The IDs of the samples for which the change had to be actually made.  It
      returns a 404 if one sample wasn't found.

    :rtype: ``HttpResponse``
    """
    try:
        sample_ids_to_remove = set(int(id_) for id_ in request.POST.get("remove", "").split(",") if id_)
        sample_ids_to_add = set(int(id_) for id_ in request.POST.get("add", "").split(",") if id_)
    except ValueError:
        raise Http404("One or more of the sample IDs were invalid.")
    doubled_ids = sample_ids_to_remove & sample_ids_to_add
    sample_ids_to_remove -= doubled_ids
    sample_ids_to_add -= doubled_ids
    try:
        samples_to_remove = models.Sample.objects.in_bulk(list(sample_ids_to_remove))
        samples_to_add = utils.restricted_samples_query(request.user).in_bulk(list(sample_ids_to_add))
    except models.Sample.DoesNotExist:
        raise Http404("One or more of the sample IDs could not be found.")
    current_my_samples = set(request.user.my_samples.values_list("id", flat=True))
    changed_sample_ids = sample_ids_to_remove & current_my_samples | \
        sample_ids_to_add - (current_my_samples - sample_ids_to_remove)
    request.user.my_samples.remove(*samples_to_remove.values())
    request.user.my_samples.add(*samples_to_add.values())
    return respond_in_json(changed_sample_ids)


def _is_folded(process_id, folded_process_classes, exceptional_processes, switch):
    """Helper routine to determine whether the process is folded or not. Is the switch
    parameter is ``True``, the new status is saved.

    :Parameters:
     - `process_id`: The process ID from the process, which should be checked.
     - `folded_process_classes`: The content types from the process classes, which are folded by default.
     - `exceptional_processes`: The process IDs from the processes that do not follow the default settings.
     - `switch`: It says whether the new status should be saved or not.

    :type process_id: int
    :type folded_process_classes: list
    :type exceptional_processes: list
    :type switch: bool

    :Retruns:
     True when the process is now folded else False.

    :rtype: bool
    """
    content_type = get_object_or_404(models.Process, pk=process_id).content_type
    default_is_folded = content_type in folded_process_classes
    if switch:
        if process_id in exceptional_processes:
            exceptional_processes.remove(process_id)
        else:
            exceptional_processes.append(process_id)
    exceptional = process_id in exceptional_processes
    process_is_folded = not default_is_folded and exceptional or default_is_folded and not exceptional
    return process_is_folded


@login_required
@never_cache
@require_http_methods(["POST"])
def fold_process(request, sample_id):
    """Fold a single process in one sample data sheet. The new behavior is also saved.

    :Parameters:
     - `request`: The current HTTP Request object.  It must contain the process
        ID of the process which behavior should be changed.
     - `sample_id`: The sample ID represent the data sheet where the process has to be changed.

    :type request: ``HttpRequest``
    :type sample_id: unicode

    :Returns:
      True when the process is now folded else False.

    :rtype: ``HttpResponse``
    """
    process_id = utils.int_or_zero(request.POST["process_id"])
    folded_process_classes = ContentType.objects.filter(dont_show_to_user=request.user.samples_user_details)
    folded_processes = json.loads(request.user.samples_user_details.folded_processes)
    exceptional_processes = folded_processes.setdefault(sample_id, [])
    is_folded = _is_folded(process_id, folded_process_classes, exceptional_processes, switch=True)
    request.user.samples_user_details.folded_processes = json.dumps(folded_processes)
    request.user.samples_user_details.save()
    return respond_in_json(is_folded)


@login_required
@never_cache
@require_http_methods(["GET"])
def get_folded_processes(request, sample_id):
    """Get all the IDs from the processes, who have to be folded.

    :Parameters:
     - `request`: The current HTTP Request object.  It must contain all the process
        IDs of the processes from the selected sample.
     - `sample_id`: The sample ID represent the data sheet the user wants to see.

    :type request: ``HttpRequest``
    :type sample_id: unicode

    :Returns:
     The process IDs of the processes, who have to be folded on the samples data sheet.

    :rtype: ``HttpResponse``
    """
    try:
        process_ids = [utils.convert_id_to_int(id_) for id_ in request.GET["process_ids"].split(",")]
    except KeyError:
        raise JSONRequestException(3, '"process_ids" missing')
    utils.convert_id_to_int(sample_id)
    folded_process_classes = ContentType.objects.filter(dont_show_to_user=request.user.samples_user_details)
    exceptional_processes_by_sample_id = json.loads(request.user.samples_user_details.folded_processes).get(sample_id, [])
    folded_process_ids = []
    for process_id in process_ids:
        if _is_folded(process_id, folded_process_classes, exceptional_processes_by_sample_id, switch=False):
            folded_process_ids.append(process_id)
    return respond_in_json(folded_process_ids)


@login_required
@never_cache
@require_http_methods(["POST"])
def fold_main_menu_element(request):
    """Fold a single topic or sample series from the main menu.

    :Parameters:
     - `request`: The current HTTP Request object.  It must contain the the topic ID or
        sample series name.
    - `element_id`: The id from the topic or sample series

    :type request: ``HttpRequest``

    :Returns:
     True when the topic or sample series is now folded else False

    :rtype: ``HttpResponse``
    """
    def fold_element(element_id, folded_elements):
        folded_elements = json.loads(folded_elements)
        if element_id in folded_elements:
            folded_elements.remove(element_id)
            is_folded = False
        else:
            folded_elements.append(element_id)
            is_folded = True
        folded_elements = json.dumps(folded_elements)
        return is_folded, folded_elements

    element_id = utils.int_or_zero(request.POST["element_id"])

    if not element_id:
        element_id = request.POST["element_id"]
        element_is_folded, request.user.samples_user_details.folded_series = \
            fold_element(element_id, request.user.samples_user_details.folded_series)
    else:
        element_is_folded, request.user.samples_user_details.folded_topics = \
            fold_element(element_id, request.user.samples_user_details.folded_topics)
    request.user.samples_user_details.save()
    return respond_in_json(element_is_folded)


@login_required
@never_cache
@require_http_methods(["GET"])
def get_folded_main_menu_elements(request):
    """Get all IDs or names from the folded topics or sample series.

    :Parameters:
     - `request`: The current HTTP Request object.

    :type request: ``HttpRequest``

    :Returns:
     The topic IDs and sample series names, who have to be folded on the main menu.

    :rtype: ``HttpResponse``
    """
    folded_elements = (json.loads(request.user.samples_user_details.folded_topics),
                       json.loads(request.user.samples_user_details.folded_series))
    return respond_in_json(folded_elements)
