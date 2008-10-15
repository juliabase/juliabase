#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from chantal.samples import models
from chantal.samples.views import utils

@login_required
def show_user(request, login_name):
    u"""View for showing basic information about a user, like the email
    address.  Maybe this could be fleshed out with phone number, picture,
    position, and field of interest.

    :Parameters:
      - `request`: the current HTTP Request object
      - `login_name`: the login name of the user to be shown

    :type request: ``HttpRequest``
    :type login_name: str

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user = get_object_or_404(django.contrib.auth.models.User, username=login_name)
    userdetails = utils.get_profile(user)
    username = models.get_really_full_name(user)
    return render_to_response("show_user.html", {"title": username, "user": user, "userdetails": userdetails},
                              context_instance=RequestContext(request))
