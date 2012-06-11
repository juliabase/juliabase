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


"""Views with statistical data visualisation, and the “about” view.  So far, I
have only one comprehensive statistics page.  However, I need many helper
functions for it.
"""

from __future__ import absolute_import, division, unicode_literals

import datetime, re, json, hashlib
from django.utils.translation import ugettext as _, ugettext, ugettext_lazy
from django.shortcuts import render_to_response
from django.forms.util import ValidationError
import django.contrib.auth.models
import django.forms as forms
from django.views.decorators.http import condition
from django.template import RequestContext
from samples.views import utils
import chantal_common.utils
from chantal_institute import models


time_pattern = re.compile(r"(\d{1,2}):(\d{1,2})")

class StartTimeForm(forms.Form):
    """Form class for the stating time of the meeting.
    """
    _ = ugettext_lazy
    start_time = forms.CharField(label=_("start time"), max_length=5)

    def __init__(self, *args, **kwargs):
        super(StartTimeForm, self).__init__(*args, **kwargs)
        self.fields["start_time"].widget.attrs["size"] = 5

    def clean_start_time(self):
        _ = ugettext
        start_time = self.cleaned_data["start_time"]
        match = time_pattern.match(start_time)
        if not match:
            raise ValidationError(_("This field must be of the form HH:MM."))
        hour, minute = match.group(1, 2)
        hour, minute = int(hour), int(minute)
        if hour > 23 or minute > 59:
            raise ValidationError(_("Invalid time."))
        return start_time


class TimeForm(forms.Form):
    """Form class for the duration in minutes one of the collegues wants to
    speak in the meeting.
    """
    _ = ugettext_lazy
    time = forms.IntegerField(label=_("time"), min_value=0)

    def __init__(self, *args, **kwargs):
        super(TimeForm, self).__init__(*args, **kwargs)
        self.fields["time"].widget.attrs["size"] = 5


class Member(object):

    def __init__(self, id_or_name, time):
        try:
            self.user = django.contrib.auth.models.User.objects.get(id=utils.int_or_zero(id_or_name))
        except django.contrib.auth.models.User.DoesNotExist:
            self.user = id_or_name
        self.time = time

    def get_as_tuple(self):
        try:
            id_or_name = self.user.id
        except AttributeError:
            id_or_name = self.user
        self.time = self.time_form.cleaned_data["time"]
        return id_or_name, self.time

    def get_really_full_name(self):
        try:
            return chantal_common.utils.get_really_full_name(self.user)
        except AttributeError:
            return self.user


def embed_schedule(request):
    """Put a schedule field in the request object that is used by both
    `meeting_schedule_timestamp` and `meeting_schedule_etag`.  It's really a
    pity that you can't give *one* function for returning both with Django's
    API for conditional view processing.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``
    """
    if not hasattr(request, "_meeting_schedule"):
        request._meeting_schedule = models.GroupMeetingSchedule.objects.get_or_create(group="carius")[0]


def meeting_schedule_etag(request):
    """Calculate the ETag of the meeting schedule.  It bases solely on the
    timestamp of the schedule.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the ETag of the meeting schedule

    :rtype: str
    """
    embed_schedule(request)
    if request._meeting_schedule:
        hash_ = hashlib.sha1()
        hash_.update(str(request._meeting_schedule.last_modified))
        try:
            hash_.update(str(request.user.pk))
        except AttributeError:
            pass
        return hash_.hexdigest()


def meeting_schedule_timestamp(request):
    """Calculate the timestamp of the meeting schedule.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the timestamp of the last modification of the meeting schedule

    :rtype: ``datetime.datetime``
    """
    embed_schedule(request)
    return chantal_common.utils.adjust_timezone_information(request._meeting_schedule.last_modified)


@condition(meeting_schedule_etag, meeting_schedule_timestamp)
def meeting_schedule(request):
    """View for the schedule of a group meeting.  At the moment, this view is
    some sort of singleton because it only works for the Carius group.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    schedule = models.GroupMeetingSchedule.objects.get_or_create(group="carius")[0]
    members = [Member(member, time) for member, time in json.loads(schedule.members_and_times)]
    if request.method == "POST":
        start_time_form = StartTimeForm(request.POST)
        for i, member in enumerate(members):
            member.time_form = TimeForm(request.POST, prefix=str(i))
        if all([member.time_form.is_valid() for member in members]) and start_time_form.is_valid():
            schedule.start_time = start_time_form.cleaned_data["start_time"]
            schedule.members_and_times = json.dumps([member.get_as_tuple() for member in members])
            schedule.save()
    else:
        start_time_form = StartTimeForm(initial={"start_time": schedule.start_time})
        for i, member in enumerate(members):
            member.time_form = TimeForm(initial={"time": member.time}, prefix=str(i))
    global_start_timestamp = datetime.datetime.strptime(schedule.start_time, "%H:%M")
    minutes = 0
    for member in members:
        member.start_time = (global_start_timestamp + datetime.timedelta(minutes=minutes)).strftime("%H:%M")
        minutes += member.time
    return render_to_response("chantal_institute/group_meeting_schedule.html",
                              {"title": _("Group meeting {group_name}").format(group_name="Cariusgruppe"),
                               "start_time": start_time_form, "members": members},
                              context_instance=RequestContext(request))
