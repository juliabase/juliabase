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

u"""Add and show status messages for the physical processes
"""
from __future__ import absolute_import
from chantal_common.utils import check_markdown
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.forms import widgets
from django.forms.util import ValidationError
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy
from samples import models
from samples.permissions import get_all_addable_physical_process_models
from samples.views import form_utils, feed_utils, utils
import datetime
import django.forms as forms
import settings


class SimpleRadioSelectRenderer(widgets.RadioFieldRenderer):
    def render(self):
        return mark_safe(u"""<ul class="radio-select">\n{0}\n</ul>""".format(u"\n".join(
                    u"<li>{0}</li>".format(force_unicode(w)) for w in self)))


class StatusForm(forms.ModelForm):
    u"""The status message model form class.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_(u"Operator"))
    status_level =  forms.ChoiceField(widget=forms.RadioSelect(renderer=SimpleRadioSelectRenderer),
                                          choices=models.status_level_choices)

    def __init__(self, user, *args, **kwargs):
        super(StatusForm, self).__init__(*args, **kwargs)
        self.user = user
        self.fields["operator"].set_operator(user, user.is_staff)
        self.fields["operator"].initial = user.pk
        self.fields["timestamp"].initial = datetime.datetime.now()
        #FixMe: this list should be global but something don't work correctly
        list = [ContentType.objects.get_for_model(cls).id for cls in get_all_addable_physical_process_models() \
                   if not cls._meta.verbose_name in settings.PHYSICAL_PROCESS_BLACKLIST]
        self.fields["processes"].queryset = ContentType.objects.filter(id__in=list)

    def clean_message(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        message = self.cleaned_data["message"]
        check_markdown(message)
        return message

    def clean_begin(self):
        begin = self.cleaned_data.get("begin")
        if not begin:
            begin = datetime.datetime(1,1,1)
        return begin

    def clean_end(self):
        end = self.cleaned_data.get("end")
        if not end:
            end = datetime.datetime(9999,12,31)
        return end

    def clean_timestamp(self):
        u"""Forbid timestamps that are in the future.
        """
        timestamp = self.cleaned_data["timestamp"]
        if timestamp > datetime.datetime.now():
            raise ValidationError(_(u"The timestamp must not be in the future."))
        return timestamp

    class Meta:
        model = models.StatusMessages


class Status:
    u"""Class for displaying a status message for a physical process.
    """
    def __init__(self, status_dict, process_name, username):
        u"""
        :Parameters:
          - `status_dict`: contains the informations of the current status level
          - `process_name`: the verbose name of the process
          - `username`: the first name and last name of the user who has written the status message

        :type status_dict: dictionary
        :type process_name: unicode
        :type username: unicode
        """
        self.process_name = process_name
        self.user = username
        self.status_level = status_dict['status_level']
        self.starting_time = "" if status_dict['begin'] == datetime.datetime(1,1,1) else status_dict['begin']
        self.end_time = "" if status_dict['end'] == datetime.datetime(9999,12,31) else status_dict['end']
        self.timestamp = status_dict['timestamp']
        self.status_message = status_dict['message']


@login_required
def add(request):
    u"""With this function, the messages are stored into the database.
    It also gets the information for displaying the 'add_status_message' template.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    if request.method == "POST":
        status_form = StatusForm(request.user, request.POST)
        if status_form.is_valid():
            status = status_form.save()
            for physical_process in status.processes.all():
                feed_utils.Reporter(request.user).report_status_message(physical_process, status)
            return utils.successful_response(request,
                    _(u"The status message was successfully added to the database."))
    else:
        status_form = StatusForm(request.user)
    title =  _(u"Add status message")
    return render_to_response("samples/add_status_message.html",
                              {"title": title, "status": status_form},
                              context_instance=RequestContext(request))


@login_required
def show(request):
    u"""This function shows the current status messages for the physical processes.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    status_list_for_context = []
    process_list = [ContentType.objects.get_for_model(cls) for cls in get_all_addable_physical_process_models() \
                   if not cls._meta.verbose_name in settings.PHYSICAL_PROCESS_BLACKLIST]
    while process_list:
        process = process_list.pop()
        status_list = list(models.StatusMessages.objects.filter(processes=process.id) \
                           .filter(begin__lt=datetime.datetime.today()) \
                           .filter(end__gt=datetime.datetime.today()).values())
        if status_list:
            status_list.sort(key=lambda status_dict: status_dict.get("begin"), reverse=True)
            max_index = 0
            if len(status_list) >1:
                for index, status in enumerate(status_list):
                    if status_list[max_index]["begin"] == status["begin"]:
                        if status_list[max_index]["timestamp"] < status["timestamp"]:
                            max_index = index
                    else:
                        break
            user = User.objects.get(id=status_list[max_index]["operator_id"])
            status_list_for_context.append(Status(status_list[max_index],process.name,
                                                  u"{0} {1}".format(user.first_name, user.last_name)))
        else:
            continue
    status_list_for_context.sort(key=lambda Status: Status.process_name.lower())
    template_context = {"title": _(u"Status messages for processes"),
                        "status_messages": status_list_for_context}
    return render_to_response("samples/show_status.html", template_context, context_instance=RequestContext(request))
