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

import datetime
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.forms import widgets
from django.forms.util import ValidationError
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy
from django.utils.text import capfirst
from chantal_common.utils import check_markdown, get_really_full_name
from chantal_common.search import DateTimeField
from samples import models
from samples.permissions import get_all_addable_physical_process_models
from samples.views import form_utils, feed_utils, utils
import django.forms as forms


class SimpleRadioSelectRenderer(widgets.RadioFieldRenderer):
    def render(self):
        return mark_safe(u"""<ul class="radio-select">\n{0}\n</ul>""".format(u"\n".join(
                    u"<li>{0}</li>".format(force_unicode(w)) for w in self)))


class StatusForm(forms.ModelForm):
    u"""The status message model form class.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=capfirst(_(u"operator")))
    status_level = forms.ChoiceField(label=capfirst(_(u"status level")), choices=models.status_level_choices,
                                     widget=forms.RadioSelect(renderer=SimpleRadioSelectRenderer))
    begin = DateTimeField(label=capfirst(_(u"begin")), start=True, required=False, with_inaccuracy=True,
                          help_text=_(u"YYYY-MM-DD HH:MM:SS"))
    end = DateTimeField(label=capfirst(_(u"end")), start=False, required=False, with_inaccuracy=True,
                        help_text=_(u"YYYY-MM-DD HH:MM:SS"))
    processes = forms.MultipleChoiceField(label=capfirst(_(u"processes")))

    def __init__(self, user, *args, **kwargs):
        super(StatusForm, self).__init__(*args, **kwargs)
        self.user = user
        self.fields["operator"].set_operator(user, user.is_staff)
        self.fields["operator"].initial = user.pk
        self.fields["timestamp"].initial = datetime.datetime.now()
        choices = [(ContentType.objects.get_for_model(cls).id, cls._meta.verbose_name)
                   for cls in get_all_addable_physical_process_models()
                   if not (cls._meta.app_label, cls._meta.module_name) in settings.PHYSICAL_PROCESS_BLACKLIST]
        choices.sort(key=lambda item: item[1].lower())
        self.fields["processes"].choices = choices
        self.fields["processes"].widget.attrs["size"] = 24

    def clean_message(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        message = self.cleaned_data["message"]
        check_markdown(message)
        return message

    def clean_timestamp(self):
        u"""Forbid timestamps that are in the future.
        """
        timestamp = self.cleaned_data["timestamp"]
        if timestamp > datetime.datetime.now():
            raise ValidationError(_(u"The timestamp must not be in the future."))
        return timestamp

    def clean(self):
        cleaned_data = self.cleaned_data
        begin, end = cleaned_data.get("begin"), cleaned_data.get("end")
        if begin:
            cleaned_data["begin"], cleaned_data["begin_inaccuracy"] = cleaned_data["begin"]
        else:
            cleaned_data["begin"], cleaned_data["begin_inaccuracy"] = datetime.datetime(1900, 1, 1), 6
        if end:
            cleaned_data["end"], cleaned_data["end_inaccuracy"] = cleaned_data["end"]
        else:
            cleaned_data["end"], cleaned_data["end_inaccuracy"] = datetime.datetime(9999, 12, 31), 6
        return cleaned_data

    class Meta:
        model = models.StatusMessage


@login_required
def add(request):
    u"""With this function, the messages are stored into the database.  It also
    gets the information for displaying the "add_status_message" template.

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
            return utils.successful_response(request, _(u"The status message was successfully added to the database."))
    else:
        status_form = StatusForm(request.user)
    title =  _(u"Add status message")
    return render_to_response("samples/add_status_message.html", {"title": title, "status": status_form},
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
    now = datetime.datetime.now()
    eligible_status_messages = models.StatusMessage.objects.filter(begin__lt=now, end__gt=now)
    process_types = set()
    for status_message in eligible_status_messages:
        process_types |= set(status_message.processes.all())
    status_messages = []
    for process_type in process_types:
        current_status = eligible_status_messages.filter(processes=process_type).order_by("-begin", "-timestamp")[0]
        status_messages.append((current_status, process_type.model_class()._meta.verbose_name))
    consumed_status_message_ids = set(item[0].id for item in status_messages)
    status_messages.sort(key=lambda item: item[1].lower())
    further_status_messages = {}
    for status_message in models.StatusMessage.objects.filter(end__gt=now).exclude(id__in=consumed_status_message_ids). \
            order_by("end"):
        for process_type in status_message.processes.all():
            further_status_messages.setdefault(process_type.model_class()._meta.verbose_name, []).append(status_message)
    further_status_messages = sorted(further_status_messages.items(), key=lambda item: item[0].lower())
    return render_to_response("samples/show_status.html", {"title": _(u"Status messages"),
                                                           "status_messages": status_messages,
                                                           "further_status_messages": further_status_messages},
                              context_instance=RequestContext(request))
