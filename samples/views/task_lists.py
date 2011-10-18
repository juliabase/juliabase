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


from django import forms
from django.forms.util import ValidationError
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.template import RequestContext
from samples import permissions
from samples .models import Process, Task
from samples.views import utils, feed_utils, form_utils
from samples.permissions import get_all_addable_physical_process_models
from django.utils.text import capfirst
from django.contrib.contenttypes.models import ContentType


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
    u"""Model form for a task.
    """
    _ = ugettext_lazy

    finished_process = forms.ChoiceField(label=capfirst(_(u"finished process")), required=False)

    def __init__(self, user, data=None, **kwargs):
        self.task = kwargs.get("instance")
        try:
            process_content_type_pk = kwargs.get("initial")["process_content_type"]
        except TypeError:
            try:
                process_content_type_pk = self.task.process_content_type.pk
            except AttributeError:
                process_content_type_pk = None
        super(TaskForm, self).__init__(data, **kwargs)
        self.user = user
        self.fields["process_content_type"].choices = form_utils.choices_of_content_types(
                                           list(get_all_addable_physical_process_models()))
        if self.task and (self.user == self.task.customer and self.user != self.task.operator):
            self.fields["priority"].widget.attrs.update({"disabled": "disabled"})
        if self.task and self.user == self.task.operator:
            self.fields["finished_process"].choices = [("", "----------")]
            self.fields["finished_process"].choices.extend([(process.pk, process.actual_instance._meta.verbose_name)
                for process in Process.objects.filter(operator=self.user,
                                                      content_type__pk=process_content_type_pk).order_by("-timestamp")[:10]])
        if not self.task or (self.user == self.task.customer and self.user != self.task.operator):
            self.fields["finished_process"].widget.attrs.update({"disabled": "disabled"})
        self.fields["operator"].initial = self.task.operator.pk if self.task and self.task.operator else None

    def clean_priority(self):
        if self.task and self.user == self.task.customer:
            priority = self.task.priority
        else:
            priority = self.cleaned_data["priority"]
        if not priority:
            raise ValidationError(_(u"This field is required."))
        return priority

    def clean_finished_process(self):
        finished_process_pk = self.cleaned_data.get("finished_process")
        if finished_process_pk:
            return Process.objects.get(pk=int(finished_process_pk))

    class Meta:
        model = Task
        exclude = ("samples", "customer", "finished_process")


class ChooseTaskListsForm(forms.Form):
    u"""Form for the task lists multiple selection list.
    """
    visible_task_lists = forms.MultipleChoiceField(label=capfirst(_(u"show task lists for")), required=False)

    def __init__(self, user, data=None, **kwargs):
        super(ChooseTaskListsForm, self).__init__(data, **kwargs)
        self.fields["visible_task_lists"].choices = form_utils.choices_of_content_types(
            list(get_all_addable_physical_process_models()))
        self.fields["visible_task_lists"].initial = [content_type.id for content_type
                                                     in user.samples_user_details.visible_task_lists.iterator()]
        self.fields["visible_task_lists"].widget.attrs["size"] = "15"


class TaskForTemplate(object):
    u"""Class for preparing the tasks for the show template.
    """
    def __init__(self, task, user):
        self.task = task
        self.samples = [sample if (sample.topic and not sample.topic.confidential)
                        or (permissions.has_permission_to_fully_view_sample(user, sample) or
                            permissions.has_permission_to_add_edit_physical_process(user, self.finished_process,
                                                                                    task.process_content_type.model_class()))
                        else _(u"confidential sample") for sample in task.samples.all()]
        self.user_can_edit = user == task.customer or permissions.has_permission_to_add_edit_physical_process(
            user, self.finished_process, task.process_content_type.model_class())


def save_to_database(task_form, samples, user, finished_process):
    u"""Saves the data for a task into the database.
    All validation checks must have done befor calling
    this function.

    :Parameters:
     - `task_form`: a bound and valid task form
     - `samples`: a list of samples who should processed
     - `user`: the user who has created or edited the task.
     it can be the customer or the operator of the physical
     process.

     :type task_form: `TaskForm`
     :type samples: list of `models.Sample`
     :type user: ``django.contrib.auth.models.User``

    :Returns:
     the saved task database object.

    :rtype: `samples.models.Task`
    """
    task = task_form.save()
    task.samples = samples
    if not task.customer:
        task.customer = user
    if task.status == "1_accepted" and not task.operator:
        task.operator = user
        user.my_samples.add(*samples)
    elif task.status == "3_finished" and finished_process:
        task.finished_process = finished_process
    task.save()
    return task


@login_required
def edit(request, task_id):
    u"""Edit or create a task.

    :Parameters:
      - `request`: the current HTTP Request object
      - `task_id`: number of the task to be edited.  If this is
        ``None``, create a new one.

    :type request: ``HttpRequest``
    :type task_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    task = get_object_or_404(Task, id=utils.convert_id_to_int(task_id)) if task_id is not None else None
    user = request.user
    preset_sample = utils.extract_preset_sample(request) if not task else None
    if request.method == "POST":
        task_form = TaskForm(user, request.POST, instance=task)
        samples_form = SamplesForm(user, preset_sample, task, request.POST)
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if task else None
        edit_description_form_is_valid = edit_description_form.is_valid() if edit_description_form else True
        if task_form.is_valid() and samples_form.is_valid() and edit_description_form_is_valid:
            samples = samples_form.cleaned_data["sample_list"]
            finished_process = task_form.cleaned_data.get("finished_process")

            task = save_to_database(task_form, samples, user, finished_process)
            feed_utils.Reporter(request.user).report_task(task,
                edit_description_form.cleaned_data if edit_description_form else None)
            message = _(u"Task was {verb} successfully.").format(verb=u"edited" if task_id else u"added")
            return utils.successful_response(request, message, "samples.views.task_lists.show")
    else:
        samples_form = SamplesForm(user, preset_sample, task)
        initial = {}
        if task:
            initial["process_content_type"] = task.process_content_type.pk
            initial["finished_process"] = task.finished_process.pk if task.finished_process else None
        elif request.GET.get("process_class"):
            initial["process_content_type"] = request.GET["process_class"]
        task_form = TaskForm(request.user, instance=task, initial=initial)
        edit_description_form = form_utils.EditDescriptionForm() if task else None
    title = _(u"Edit task") if task else _(u"Add task")
    return render_to_response("samples/edit_task.html", {"title": title,
                                                         "task": task_form,
                                                         "samples": samples_form,
                                                         "edit_description": edit_description_form},
                              context_instance=RequestContext(request))

@login_required
def show(request):
    u"""Shows the task lists the user wants to see.
    It also provides the multiple choice list to select the task lists
    for the user.

    :Paramerters:
     - `request`: the current HTTP Request object

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    if request.method == "POST":
        choose_task_lists_form = ChooseTaskListsForm(request.user, request.POST)
        if choose_task_lists_form.is_valid():
            request.user.samples_user_details.visible_task_lists = \
                [ContentType.objects.get_for_id(int(id_))
                 for id_ in choose_task_lists_form.cleaned_data["visible_task_lists"]]
            # In order to have a GET instead of a POST as the last request
            return utils.successful_response(request, view=show)
    else:
        choose_task_lists_form = ChooseTaskListsForm(request.user)
    task_lists = dict([(content_type, [TaskForTemplate(task, request.user)
                                       for task in content_type.tasks.order_by("-status", "priority", "last_modified")])
                       for content_type in request.user.samples_user_details.visible_task_lists.iterator()])
    return render_to_response("samples/task_lists.html", {"title": _(u"Task lists"),
                                                          "chose_task_lists": choose_task_lists_form,
                                                          "task_lists": task_lists},
                              context_instance=RequestContext(request))


@login_required
@require_http_methods(["POST"])
def remove(request, task_id):
    u"""Deletes a task from the database.

    :Paramerters:
     - `request`: the current HTTP Request object
     - `task_id`: the id from the task, which has to be deleted

    :Return:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    task = get_object_or_404(Task, id=utils.convert_id_to_int(task_id))
    if task.customer == request.user:
        physical_process_content_type = task.process_content_type
        samples = list(task.samples.all())
        task.delete()
        feed_utils.Reporter(request.user).report_removed_task(physical_process_content_type, samples)
    else:
        raise permissions.PermissionError(request.user, u"You cannot remove this task.")
    return utils.successful_response(request, _(u"The task was successfully removed."), show)
