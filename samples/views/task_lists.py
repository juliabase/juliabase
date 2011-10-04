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


import re, datetime, urllib
from django import forms
from django.forms.util import ValidationError
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django.template import RequestContext
from chantal_common.utils import append_error
from samples import models, permissions
from samples.views import utils, feed_utils, form_utils, shared_utils
from samples.permissions import get_all_addable_physical_process_models
from django.utils.text import capfirst
from django.contrib.contenttypes.models import ContentType
from chantal_common import utils as chantal_common_utils


class SamplesForm(forms.Form):
    u"""Form for the list selection of samples.
    """
    _ = ugettext_lazy
    sample_list = form_utils.MultipleSamplesField(label=_(u"Samples"))

    def __init__(self, user, preset_sample, task, data=None, **kwargs):
        samples = list(user.my_samples.all())
        if task:
            kwargs["initial"] = {"sample_list": task.samples.values_list("pk", flat=True)}
            super(SamplesForm, self).__init__(data, **kwargs)
            samples.extend(task.samples.all())
        else:
            super(SamplesForm, self).__init__(data, **kwargs)
            self.fields["sample_list"].initial = []
            if preset_sample:
                samples.append(preset_sample)
                self.fields["sample_list"].initial.append(preset_sample.pk)
        self.fields["sample_list"].set_samples(samples, user)
        self.fields["sample_list"].widget.attrs.update({"size": "17", "style": "vertical-align: top"})


class TaskForm(forms.ModelForm):

    _ = ugettext_lazy

    def __init__(self, user, data=None, **kwargs):
        self.task = kwargs.get("instance")
        super(TaskForm, self).__init__(data, **kwargs)
        self.user = user
        self.fields["process_content_type"].choices = form_utils.choices_of_content_types(
                                           list(get_all_addable_physical_process_models()))
        if self.task and self.user == self.task.costumer:
            self.fields["priority"].widget.attrs.update({"disabled": "disabled"})
        if self.task and self.user == self.task.operator:
            self.fields["finished_process"].choices = [(process.actual_instance, process.actual_instance._meta.verbose_name)
                for process in models.Process.objects.filter(operator=self.user).order_by("-timestamp")[:10]]
        if not self.task or self.user == self.task.costumer:
            self.fields["finished_process"].widget.attrs.update({"disabled": "disabled"})

    def clean_priority(self):
        if self.task and self.user == self.task.costumer:
            priority = self.task.priority
        else:
            priority = self.cleaned_data["priority"]
        if not priority:
            raise ValidationError(_(u"This field is required."))
        return priority

    class Meta:
        model = models.Task
        exclude = ("samples", "costumer")


def save_to_database(task_form, samples, user):
    task = task_form.save()
    task.samples = samples
    if not task.costumer:
        task.costumer = user
    if task.status == "accepted" and not task.operqator:
        task.operqator = user
        user.my_samples.add(*samples)
    task.save()


@login_required
def edit(request, task_id):

    task = get_object_or_404(models.Task, id=utils.convert_id_to_int(task_id)) \
        if task_id is not None else None
    user = request.user
    preset_sample = utils.extract_preset_sample(request) if not task else None
    if request.method == "POST":
        task_form = TaskForm(user, request.POST, instance=task)
        samples_form = SamplesForm(user, preset_sample, task, request.POST)
        if task_form.is_valid() and samples_form.is_valid():
            samples = samples_form.cleaned_data["sample_list"]
            save_to_database(task_form, samples, user)
            next_view = "samples.views.task_lists.show"
            message = _(u"Task was {verb} successfully.".format(verb="edited" if task_id else "added"))
            return utils.successful_response(request, message, next_view, forced=next_view is not None, json_response=True)
    else:
        samples_form = SamplesForm(user, preset_sample, task)
        initial = {}
        if task:
            initial["process_content_type"] = task.process_content_type.id
        elif request.GET.get("process_class"):
            initial["process_content_type"] = request.GET["process_class"]
        task_form = TaskForm(request.user, instance=task, initial=initial)
    title = _(u"Edit task") if task else _(u"Add task")
    return render_to_response("samples/edit_task.html", {"title": title, "task": task_form, "samples": samples_form},
                              context_instance=RequestContext(request))


class ChooseTaskListsForm(forms.ModelForm):

    visible_task_lists = forms.MultipleChoiceField(label=capfirst(_(u"show task lists for")), required=False)

    def __init__(self, user, data=None, **kwargs):
        super(ChooseTaskListsForm, self).__init__(data, **kwargs)
        self.fields["visible_task_lists"].choices = form_utils.choices_of_content_types(
            list(get_all_addable_physical_process_models()))
        self.fields["visible_task_lists"].initial = [content_type.id for content_type
                                                     in user.samples_user_details.visible_task_lists.iterator()]
        self.fields["visible_task_lists"].widget.attrs["size"] = "15"

    class Meta:
        model = models.UserDetails
        fields = ()


class TaskForTemplate(object):
    def __init__(self, task, user):
        self.id = task.id
        self.status = task.get_status_display()
        self.status_id = task.status
        self.priority = task.get_priority_display()
        self.costumer = task.costumer
        self.last_modified = task.last_modified
        self.creating_timestamp = task.creating_timestamp
        self.operator = task.operator
        self.finished_process = task.finished_process
        self.samples = [sample if (sample.topic and not sample.topic.confidential)
                        or (permissions.has_permission_to_fully_view_sample(user, sample)
                        or permissions.has_permission_to_add_edit_physical_process(user, self.finished_process,
                                                                                   task.process_content_type.model_class()))
                        else _(u"confidential sample") for sample in task.samples.all()]
        self.comments = task.comments
        self.user_can_edit = user == task.costumer or permissions.has_permission_to_add_edit_physical_process(user,
                                                    self.finished_process, task.process_content_type.model_class())



@login_required
def show(request):
    if request.method == "POST":
        choose_task_lists_form = ChooseTaskListsForm(request.user, request.POST)
        if choose_task_lists_form.is_valid():
            request.user.samples_user_details.visible_task_lists = [ContentType.objects.get_for_id(id) for id
                                        in map(int, choose_task_lists_form.cleaned_data["visible_task_lists"])]
    else:
        choose_task_lists_form = ChooseTaskListsForm(request.user)
    task_lists = dict([(content_type, [TaskForTemplate(task, request.user)
                                       for task in content_type.tasks.order_by("-status", "priority", "last_modified")])
                       for content_type in request.user.samples_user_details.visible_task_lists.iterator()])
    return render_to_response("samples/show_task_lists.html", {"title": "Task lists",
                                                               "chose_task_lists": choose_task_lists_form,
                                                               "task_lists": task_lists},
                              context_instance=RequestContext(request))

@login_required
def remove(request, task_id):
    task = get_object_or_404(models.Task, id=utils.convert_id_to_int(task_id))
    if task.costumer == request.user:
        task.delete()
    else:
        raise permissions.PermissionError(request.user, u"You cannot remove this task.")
    return utils.successful_response(request, _(u"The task was successfully remove."), show)

