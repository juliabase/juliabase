#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views that are intended only for the Remote Client.  While also users can
visit these links with their browser directly, it is not really useful what
they get there.
"""

from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
import django.contrib.auth.models
import django.contrib.auth
from chantal.samples.views import utils

@login_required
@never_cache
def primary_keys(request):
    u"""Generate a pickle document in plain text (*no* HTML!) containing
    mappings of names of database objects to primary keys.  While this can be
    used by everyone by entering the URL directly, this view is intended to be
    used only by the remote client program to get primary keys.  The reason for
    this is simple: In forms, you have to give primary keys in POST data sent
    to the web server.  However, a priori, the remote client doesn't know
    them.  Therefore, it can query this view to get them.

    The syntax of the query string to be appended to the URL is very simple.
    If you say::

        ...?samples=01B410,01B402

    you get the primary keys of those two samples::

        {"samples": {"01B410": 5, "01B402": 42}}

    The same works for ``"groups"`` and ``"users"``.  You can also mix all tree
    in the query string.  If you pass ``"*"`` instead of a values list, you get
    *all* primary keys.  For samples, however, this is limited to “My Samples”.

    The result is a pickled representation of the resulting nested dictionary.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    query_dict = utils.parse_query_string(request)
    result_dict = {}
    if "groups" in query_dict:
        if query_dict["groups"] == "*":
            result_dict["groups"] = dict(django.contrib.auth.models.Group.objects.values_list("name", "id"))
        else:
            groupnames = query_dict["groups"].split(",")
            result_dict["groups"] = dict(django.contrib.auth.models.Group.objects.filter(name__in=groupnames).
                                         values_list("name", "id"))
    if "samples" in query_dict:
        if query_dict["samples"] == "*":
            result_dict["samples"] = dict(utils.get_profile(request.user).my_samples.values_list("name", "id"))
        else:
            sample_names = query_dict["samples"].split(",")
            result_dict["samples"] = dict(models.Sample.objects.filter(name__in=sample_names).values_list("name", "id"))
    if "users" in query_dict:
        if query_dict["users"] == "*":
            result_dict["users"] = dict(django.contrib.auth.models.User.objects.values_list("username", "id"))
        else:
            user_names = query_dict["users"].split(",")
            # FixMe: Return only *active* users
            result_dict["users"] = dict(django.contrib.auth.models.User.objects.filter(username__in=user_names).
                                        values_list("username", "id"))
    return utils.respond_to_remote_client(result_dict)

def login_remote_client(request):
    u"""Login for the Chantal Remote Client.  It only supports the HTTP POST
    method and expects ``username`` and ``password``.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object.  It is a pickled boolean object, whether the
      login was successful or not.

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

def logout_remote_client(request):
    u"""By requesting this view, the Chantal Remote Client can log out.  This
    view can never fail.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object.  It is a pickled boolean object and always
      ``True``.

    :rtype: ``HttpResponse``
    """
    django.contrib.auth.logout(request)
    return utils.respond_to_remote_client(True)

def next_deposition_number(request, letter):
    u"""Send the next free deposition number to the Chantal Remote Client.  It
    only supports the HTTP POST method and expects ``username`` and
    ``password``.

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
