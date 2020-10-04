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


"""Views that are intended only for the Remote Client and AJAX code (called
“JSON clients”).  While also users can visit these links with their browser
directly, it is not really useful what they get there.  Note that the whole
communication to the remote client happens in JSON format.
"""

import sys, copy
from django.db.utils import IntegrityError
from django.db.models import Q
from django.conf import settings
from django.http import Http404
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
import django.contrib.auth.models
import django.contrib.auth
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType
from jb_common.models import Topic
from jb_common.utils.base import respond_in_json, JSONRequestException, int_or_zero
import samples.utils.views as utils
from samples.utils import sample_names
from samples import models, permissions


@login_required
@require_http_methods(["POST"])
@ensure_csrf_cookie
def add_sample(request):
    """Adds a new sample to the database.  It is added without processes.  This
    view can only be used by admin accounts.

    :param request: the current HTTP Request object; it must contain the sample
        data in the POST data.

    :return:
      The primary key of the created sample.  ``False`` if something went
      wrong.  It may return a 404 if the topic or the currently responsible
      person wasn't found.

    :rtype: HttpResponse
    """
    try:
        name = request.POST["name"]
        current_location = request.POST["current_location"]
        currently_responsible_person = request.POST["currently_responsible_person"]
        purpose = request.POST.get("purpose", "")
        tags = request.POST.get("tags", "")
        topic = request.POST.get("topic")
    except KeyError as error:
        raise JSONRequestException(3, "'{}' parameter missing.".format(error.args[0]))
    if len(name) > 30:
        raise JSONRequestException(5, "The sample name is too long.")
    name_format = sample_names.sample_name_format(name)
    if name_format is None or \
       not request.user.is_superuser and \
       name_format not in settings.SAMPLE_NAME_FORMATS["provisional"].get("possible_renames", set()):
        raise JSONRequestException(5, "The sample name is invalid.")
    eligible_users = django.contrib.auth.models.User.objects.filter(is_active=True, jb_user_details__department__isnull=False)
    try:
        currently_responsible_person = eligible_users.get(pk=utils.convert_id_to_int(currently_responsible_person))
    except django.contrib.auth.models.User.DoesNotExist:
        raise Http404("Currently reponsible user not found.")
    if topic:
        all_topics = Topic.objects.all() if request.user.is_superuser else \
                     Topic.objects.filter(Q(confidential=False) | Q(members=request.user))
        try:
            topic = all_topics.get(pk=utils.convert_id_to_int(topic))
        except Topic.DoesNotExist:
            raise Http404("Topic not found")
    try:
        sample = models.Sample.objects.create(name=name, current_location=current_location,
                                              currently_responsible_person=currently_responsible_person, purpose=purpose,
                                              tags=tags, topic=topic)
        # They will be shadowed anyway.  Nevertheless, this action is an
        # emergency measure.  Probably the samples the aliases point to should
        # be merged with the sample but this can't be decided automatically.
        models.SampleAlias.objects.filter(name=name).delete()
    except IntegrityError as error:
        error_message = "The sample with this data could not be added."
        if request.user.is_superuser:
            error_message += " {}".format(error)
        raise JSONRequestException(5, error_message)
    sample.watchers.add(request.user)
    return respond_in_json(sample.pk)


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
    is limited to “My Samples”.  If a sample name is mapped to a list, it is an
    alias (which may point to more than one sample).

    The result is the JSON representation of the resulting nested dictionary.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    result_dict = {}
    if "topics" in request.GET:
        all_topics = Topic.objects.all() if request.user.is_superuser else \
                     Topic.objects.filter(Q(confidential=False) | Q(members=request.user))
        if request.GET["topics"] == "*":
            topics = all_topics
        else:
            topicnames = request.GET["topics"].split(",")
            topics = {topic for topic in all_topics if topic.name in topicnames}
        result_dict["topics"] = {topic.name: topic.id for topic in topics}
    if "samples" in request.GET:
        if request.GET["samples"] == "*":
            result_dict["samples"] = dict(request.user.my_samples.values_list("name", "id"))
        else:
            restricted_samples = utils.restricted_samples_query(request.user)
            sample_names = request.GET["samples"].split(",")
            result_dict["samples"] = {}
            for alias, sample_id in models.SampleAlias.objects.filter(name__in=sample_names, sample__in=restricted_samples). \
               values_list("name", "sample"):
                result_dict["samples"].setdefault(alias, set()).add(sample_id)
            result_dict["samples"].update(restricted_samples.filter(name__in=sample_names).values_list("name", "id"))
    if "depositions" in request.GET:
        deposition_numbers = request.GET["depositions"].split(",")
        result_dict["depositions"] = dict(models.Deposition.objects.
                                          filter(number__in=deposition_numbers).values_list("number", "id"))
    if "users" in request.GET:
        eligible_users = django.contrib.auth.models.User.objects.all() if request.user.is_superuser else \
                django.contrib.auth.models.User.objects.filter(jb_user_details__department__isnull=False)
        if request.GET["users"] == "*":
            result_dict["users"] = dict(eligible_users.values_list("username", "id"))
        else:
            user_names = request.GET["users"].split(",")
            result_dict["users"] = dict(eligible_users.filter(username__in=user_names).values_list("username", "id"))
    if "external_operators" in request.GET:
        if request.user.is_superuser:
            all_external_operators = models.ExternalOperator.objects.all()
        else:
            all_external_operators = models.ExternalOperator.objects.filter(Q(confidential=False) | Q(contact_persons=request.user))
        if request.GET["external_operators"] == "*":
            external_operators = all_external_operators
        else:
            external_operator_names = request.GET["external_operators"].split(",")
            external_operators = all_external_operators.filter(name__in=external_operator_names)
        result_dict["external_operators"] = {external_operator.name: external_operator.id for external_operator in external_operators}
    return respond_in_json(result_dict)


# FixMe: This should be merged into `primary_keys`.

@login_required
@never_cache
@require_http_methods(["GET"])
def available_items(request, model_name):
    """Returns the unique ids of all items that are already in the database for
    this model.  The point is that it will return primary keys only as a
    fallback.  Instead, it returns the “official” id of the respective model,
    represented by the `JBMeta.identifying_field` attribute, if given.  This
    may be the number of a deposition, or the number of a measurement run, etc.

    :param request: the current HTTP Request object
    :param model_name: the name of the database model

    :type request: HttpRequest
    :type model_name: str

    :return:
      The HTTP response object.  It is a JSON list object with all the ids of
      the objects in the database for the model.

    :rtype: HttpResponse
    """
    if not request.user.is_superuser:
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
        pk = model.JBMeta.identifying_field
    except AttributeError:
        pk = "pk"
    return respond_in_json(list(model.objects.values_list(pk, flat=True)))


# FixMe: The following two functions must go to jb_common.

@never_cache
@ensure_csrf_cookie
def login_remote_client(request):
    """Login for the JuliaBase Remote Client.  It expects ``username`` and
    ``password``.  AJAX code shouldn't need it because it has the cookie
    already.  An HTTP GET request yields nothing – this can be used to get the
    CSRF cookie.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object.  It is a JSON boolean object, whether the login
      was successful or not.

    :rtype: HttpResponse
    """
    if request.method == "POST":
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
    else:
        return respond_in_json(None)


@never_cache
@require_http_methods(["GET"])
def logout_remote_client(request):
    """By requesting this view, the JuliaBase Remote Client can log out.  This
    view can never fail.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object.  It is a JSON boolean object and always
      ``True``.

    :rtype: HttpResponse
    """
    django.contrib.auth.logout(request)
    return respond_in_json(True)


@login_required
@require_http_methods(["POST"])
@ensure_csrf_cookie
def add_alias(request):
    """Adds a new sample alias name to the database.  This view can only be
    used by admin accounts.

    :param request: the current HTTP Request object; it must contain the
        sample's primary key and the alias name in the POST data.

    :type request: HttpRequest

    :return:
      ``True`` if it worked, ``False`` if something went wrong.  It returns a
      404 if the sample wasn't found.

    :rtype: HttpResponse
    """
    if not request.user.is_superuser:
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
@ensure_csrf_cookie
def change_my_samples(request):
    """Adds or remove samples from “My Samples”.

    :param request: The current HTTP Request object.  It must contain the sample
        IDs of the to-be-removed samples comma-separated list in ``"remove"``
        and the to-be-added sample IDs in ``"add"``.  Both can be empty.
        Moreover, it may contain the ID of the user whose “My Samples” should
        be changed in ``"user"``.  If not given, the logged-in user is used.
        If given, the currently logged-in user must be admin.

    :type request: HttpRequest

    :return:
      The IDs of the samples for which the change had to be actually made.  It
      returns a 404 if one sample wasn't found.

    :rtype: HttpResponse
    """
    try:
        sample_ids_to_remove = {int(id_) for id_ in request.POST.get("remove", "").split(",") if id_}
        sample_ids_to_add = {int(id_) for id_ in request.POST.get("add", "").split(",") if id_}
    except ValueError:
        raise Http404("One or more of the sample IDs were invalid.")
    user = request.user
    user_id = request.POST.get("user")
    if user_id:
        if not request.user.is_superuser:
            raise JSONRequestException(6, "Only admins can change other users' My Samples.")
        try:
            user = django.contrib.auth.models.User.objects.get(pk=user_id)
        except django.contrib.auth.models.User.DoesNotExist:
            raise Http404("User not found.")
    doubled_ids = sample_ids_to_remove & sample_ids_to_add
    sample_ids_to_remove -= doubled_ids
    sample_ids_to_add -= doubled_ids
    try:
        samples_to_remove = models.Sample.objects.in_bulk(list(sample_ids_to_remove))
        samples_to_add = utils.restricted_samples_query(request.user).in_bulk(list(sample_ids_to_add))
    except models.Sample.DoesNotExist:
        raise Http404("One or more of the sample IDs could not be found.")
    current_my_samples = set(user.my_samples.values_list("id", flat=True))
    changed_sample_ids = sample_ids_to_remove & current_my_samples | \
        sample_ids_to_add - (current_my_samples - sample_ids_to_remove)
    user.my_samples.remove(*samples_to_remove.values())
    user.my_samples.add(*samples_to_add.values())
    return respond_in_json(changed_sample_ids)


def _is_folded(process_id, folded_process_classes, exceptional_processes, switch):
    """Helper routine to determine whether the process is folded or not. Is the switch
    parameter is ``True``, the new status is saved.

    :param process_id: The process ID from the process, which should be checked.
    :param folded_process_classes: The content types from the process classes, which are folded by default.
    :param exceptional_processes: The process IDs from the processes that do not follow the default settings.
    :param switch: It says whether the new status should be saved or not.

    :type process_id: int
    :type folded_process_classes: list
    :type exceptional_processes: list
    :type switch: bool

    :Retruns:
      True if the process is now folded else False.

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
@ensure_csrf_cookie
def fold_process(request, sample_id):
    """Fold a single process in one sample data sheet. The new behavior is also saved.

    :param request: The current HTTP Request object.  It must contain the process
        ID of the process which behavior should be changed.
    :param sample_id: The sample ID represent the data sheet where the process has to be changed.

    :type request: HttpRequest
    :type sample_id: str

    :return:
      True if the process is now folded else False.

    :rtype: HttpResponse
    """
    process_id = int_or_zero(request.POST["process_id"])
    folded_process_classes = ContentType.objects.filter(dont_show_to_user=request.user.samples_user_details)
    folded_processes = request.user.samples_user_details.folded_processes
    exceptional_processes = folded_processes.setdefault(sample_id, [])
    is_folded = _is_folded(process_id, folded_process_classes, exceptional_processes, switch=True)
    request.user.samples_user_details.folded_processes = folded_processes
    request.user.samples_user_details.save()
    return respond_in_json(is_folded)


@login_required
@never_cache
@require_http_methods(["GET"])
def get_folded_processes(request, sample_id):
    """Get all the IDs from the processes, who have to be folded.

    :param request: The current HTTP Request object.  It must contain all the process
        IDs of the processes from the selected sample.
    :param sample_id: The sample ID represent the data sheet the user wants to see.

    :type request: HttpRequest
    :type sample_id: str

    :return:
     The process IDs of the processes, who have to be folded on the samples data sheet.

    :rtype: HttpResponse
    """
    try:
        process_ids = [utils.convert_id_to_int(id_) for id_ in request.GET["process_ids"].split(",")]
    except KeyError:
        raise JSONRequestException(3, '"process_ids" missing')
    utils.convert_id_to_int(sample_id)
    folded_process_classes = ContentType.objects.filter(dont_show_to_user=request.user.samples_user_details)
    exceptional_processes_by_sample_id = request.user.samples_user_details.folded_processes.get(sample_id, [])
    folded_process_ids = []
    for process_id in process_ids:
        if _is_folded(process_id, folded_process_classes, exceptional_processes_by_sample_id, switch=False):
            folded_process_ids.append(process_id)
    return respond_in_json(folded_process_ids)


@login_required
@never_cache
@require_http_methods(["POST"])
@ensure_csrf_cookie
def fold_main_menu_element(request):
    """Fold a single topic or sample series from the main menu.

    :param request: The current HTTP Request object.  It must contain the topic
        ID or sample series name.

    :type request: HttpRequest

    :return:
      True if the topic or sample series is now folded else False

    :rtype: HttpResponse
    """
    def fold_element(element_id, folded_elements):
        folded_elements = copy.deepcopy(folded_elements)
        if element_id in folded_elements:
            folded_elements.remove(element_id)
            is_folded = False
        else:
            folded_elements.append(element_id)
            is_folded = True
        return is_folded, folded_elements

    element_id = int_or_zero(request.POST["element_id"])

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

    :param request: The current HTTP Request object.

    :type request: HttpRequest

    :return:
     The topic IDs and sample series names, who have to be folded on the main menu.

    :rtype: HttpResponse
    """
    folded_elements = (request.user.samples_user_details.folded_topics, request.user.samples_user_details.folded_series)
    return respond_in_json(folded_elements)
