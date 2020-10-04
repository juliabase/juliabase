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


import copy, datetime
from django import forms
from django.contrib.auth.models import User
from django.forms.utils import ValidationError
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.http import require_http_methods
import django.utils.timezone
from django.utils.text import capfirst
from django.utils.encoding import force_text
from django.apps import apps
import jb_common.utils.base as common_utils
from jb_common.utils.base import help_link
from jb_common.models import Department
from samples.models import Process, Task
from samples import permissions
import samples.utils.views as utils


class SamplesForm(forms.Form):
    """Form for the list selection of samples.
    """
    sample_list = utils.MultipleSamplesField(label=capfirst(_("samples")))

    def __init__(self, user, preset_sample, task, data=None, **kwargs):
        samples = user.my_samples.all()
        important_samples = set()
        if task:
            kwargs["initial"] = {"sample_list": list(task.samples.values_list("pk", flat=True))}
            if user != task.customer or task.status != "1 new":
                super().__init__(**kwargs)
                self.fields["sample_list"].disabled = True
            else:
                super().__init__(data, **kwargs)
            important_samples.update(task.samples.all())
        else:
            super().__init__(data, **kwargs)
            self.fields["sample_list"].initial = []
            if preset_sample:
                important_samples.add(preset_sample)
                self.fields["sample_list"].initial.append(preset_sample.pk)
        self.fields["sample_list"].set_samples(user, samples, important_samples)
        self.fields["sample_list"].widget.attrs.update({"size": "17", "style": "vertical-align: top"})


class TaskForm(forms.ModelForm):
    """Model form for a task.
    """
    operator = forms.ChoiceField(label=capfirst(_("operator")), required=False)
    process_class = forms.ChoiceField(label=capfirst(_("process class")))
    finished_process = forms.ChoiceField(label=capfirst(_("finished process")), required=False)

    class Meta:
        model = Task
        exclude = ("samples",)

    def __init__(self, user, data=None, **kwargs):
        self.task = kwargs.get("instance")
        self.user = user
        self.fixed_fields = set()
        if self.task:
            eligible_operators = set(permissions.get_all_adders(self.task.process_class.model_class()))
            if self.task.operator:
                eligible_operators.add(self.task.operator)
            self.fixed_fields.add("process_class")
            if self.task.status == "1 new":
                self.fixed_fields.add("finished_process")
                if self.user not in eligible_operators:
                    self.fixed_fields.update(["operator", "status"])
            elif self.task.status in ["2 accepted", "3 in progress"]:
                if self.user != self.task.operator:
                    self.fixed_fields.update(["status", "priority", "finished_process", "operator"])
                    if self.user != self.task.customer:
                        self.fixed_fields.add("comments")
            else:
                self.fixed_fields.update(["priority", "finished_process", "operator"])
                if self.user != self.task.operator:
                    self.fixed_fields.add("status")
                    if self.user != self.task.customer:
                        self.fixed_fields.add("comments")
        else:
            self.fixed_fields.update(["status", "finished_process", "operator"])
        if data is not None:
            data = data.copy()
            if self.task:
                data.update(forms.model_to_dict(self.task, self.fixed_fields))
            else:
                initial = kwargs.get("initial", {})
                initial.update({"status": "1 new"})
                data.update(initial)
        super().__init__(data, **kwargs)
        self.fields["customer"].required = False
        self.fields["operator"].choices = [("", "---------")]
        if self.task:
            self.fields["operator"].choices.extend((user.pk, common_utils.get_really_full_name(user))
                                                   for user in common_utils.sorted_users_by_first_name(eligible_operators))
        self.fields["process_class"].choices = utils.choices_of_content_types(
            permissions.get_all_addable_physical_process_models())
        self.fields["finished_process"].choices = [("", "---------")]
        if self.task:
            old_finished_process_id = self.task.finished_process.id if self.task.finished_process else None
            if self.user == self.task.operator:
                self.fields["finished_process"].choices.extend(
                    [(process.id, process.actual_instance)
                     for process in Process.objects.filter(
                            Q(operator=self.user, content_type=self.task.process_class) |
                            Q(id=old_finished_process_id)).filter(finished=True).order_by("-timestamp")[:10]])
            elif old_finished_process_id:
                self.fields["finished_process"].choices.append((old_finished_process_id, self.task.finished_process))
        self.fields["comments"].widget.attrs["cols"] = 30
        self.fields["comments"].widget.attrs["rows"] = 5
        for field_name in self.fixed_fields:
            self.fields[field_name].disabled = True
            self.fields[field_name].required = False

    def clean_status(self):
        if "status" in self.fixed_fields:
            return self.task.status if self.task else "1 new"
        return self.cleaned_data["status"]

    def clean_process_class(self):
        if "process_class" in self.fixed_fields:
            return self.task.process_class
        pk = self.cleaned_data.get("process_class")
        if pk:
            return ContentType.objects.get(pk=int(pk))

    def clean_priority(self):
        if "priority" in self.fixed_fields:
            return self.task.priority
        return self.cleaned_data["priority"]

    def clean_finished_process(self):
        if "finished_process" in self.fixed_fields:
            return self.task.finished_process if self.task else None
        pk = self.cleaned_data.get("finished_process")
        if pk:
            return Process.objects.get(pk=int(pk))

    def clean_comments(self):
        if "comments" in self.fixed_fields:
            return self.task.comments
        return self.cleaned_data["comments"]

    def clean_customer(self):
        return self.task.customer if self.task else self.user

    def clean_operator(self):
        if "operator" in self.fixed_fields:
            return self.task.operator if self.task else None
        pk = self.cleaned_data.get("operator")
        if pk:
            return User.objects.get(pk=int(pk))

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("status") in ["2 accepted", "3 in progress", "0 finished"]:
            if not cleaned_data.get("operator"):
                self.add_error("operator", ValidationError(_("With this status, you must set an operator."), code="required"))
        return cleaned_data


class ChooseTaskListsForm(forms.Form):
    """Form for the task lists multiple selection list.
    """
    visible_task_lists = forms.MultipleChoiceField(label=capfirst(_("show task lists for")), required=False)

    def __init__(self, user, data=None, **kwargs):
        super().__init__(data, **kwargs)
        choices = []
        for department in user.samples_user_details.show_users_from_departments.iterator():
            process_from_department = {process for process in permissions.get_all_addable_physical_process_models().keys()
                                       if process._meta.app_label == department.app_label}
            choices.append((department.name, utils.choices_of_content_types(process_from_department)))
        if len(choices) == 1:
            choices = choices[0][1]
        if not choices:
            choices = (("", 9 * "-"),)
        self.fields["visible_task_lists"].choices = choices
        self.fields["visible_task_lists"].initial = [content_type.id for content_type
                                                     in user.samples_user_details.visible_task_lists.iterator()]
        self.fields["visible_task_lists"].widget.attrs["size"] = "15"


class TaskForTemplate:
    """Class for preparing the tasks for the show template.
    """
    def __init__(self, task, user):
        self.task = task
        self.samples = [sample if (sample.topic and not sample.topic.confidential)
                        or (permissions.has_permission_to_fully_view_sample(user, sample) or
                            permissions.has_permission_to_add_edit_physical_process(user, self.task.finished_process,
                                                                                    self.task.process_class.model_class()))
                        else _("confidential sample") for sample in self.task.samples.all()]
        self.user_can_edit = user == self.task.customer or \
            permissions.has_permission_to_add_physical_process(user, task.process_class.model_class())
        self.user_can_see_everything = self.user_can_edit or \
            all([permissions.has_permission_to_fully_view_sample(user, sample) for sample in self.task.samples.all()])
        self.user_can_delete = user == self.task.customer


def save_to_database(task_form, samples_form, old_task):
    """Saves the data for a task into the database.  All validation checks
    must have done before calling this function.

    :param task_form: a bound and valid task form
    :param samples_form: a bound and valid samples form iff we create a new
        task, or an unbound samples form
    :param old_task: the old task instance, which is ``None`` if we newly create
        one

    :type task_form: `TaskForm`
    :type samples_form: `SamplesForm`
    :type old_task: `samples.models.Task`

    :return:
     the saved task database object.

    :rtype: `samples.models.Task`
    """
    task = task_form.save()
    if samples_form.is_bound:
        task.samples.set(samples_form.cleaned_data["sample_list"])
    if old_task and task.operator and old_task.operator != task.operator:
        task.operator.my_samples.add(*task.samples.all())
    return task


@help_link("demo.html#tasks")
@login_required
def edit(request, task_id):
    """Edit or create a task.

    :param request: the current HTTP Request object
    :param task_id: number of the task to be edited.  If this is
        ``None``, create a new one.

    :type request: HttpRequest
    :type task_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    task = get_object_or_404(Task, id=utils.convert_id_to_int(task_id)) if task_id else None
    user = request.user
    if task and user != task.customer:
        permissions.assert_can_add_physical_process(request.user, task.process_class.model_class())
    preset_sample = utils.extract_preset_sample(request) if not task_id else None
    if request.method == "POST":
        task_form = TaskForm(user, request.POST, instance=task)
        samples_form = SamplesForm(user, preset_sample, task, request.POST)
        if task_id:
            old_task = copy.deepcopy(task)
            old_samples = set(task.samples.all())
        if task_form.is_valid() and (not samples_form.is_bound or samples_form.is_valid()):
            task = save_to_database(task_form, samples_form, old_task=old_task if task_id else None)
            if task_id:
                edit_description = {"important": True, "description": ""}
                if old_task.status != task.status:
                    edit_description["description"] += \
                        _("* Status is now “{new_status}”.\n").format(new_status=task.get_status_display())
                if old_task.priority != task.priority:
                    edit_description["description"] += \
                        _("* Priority is now “{new_priority}̣”.\n").format(new_priority=task.get_priority_display())
                if old_task.finished_process != task.finished_process:
                    edit_description["description"] += _("* Connected process.\n")
                if old_task.operator != task.operator:
                    if task.operator:
                        edit_description["description"] += _("* Operator is now {operator}.\n").format(
                            operator=common_utils.get_really_full_name(task.operator))
                    else:
                        edit_description["description"] += _("* No operator is set anymore.\n")
                if old_samples != set(task.samples.all()):
                    edit_description["description"] += "* {0}.\n".format(common_utils.capitalize_first_letter(_("samples")))
                if old_task.comments != task.comments:
                    edit_description["description"] += "* {0}.\n".format(common_utils.capitalize_first_letter(_("comments")))
            else:
                edit_description = None
            utils.Reporter(request.user).report_task(task, edit_description)
            message = _("Task was {verb} successfully.").format(verb=_("edited") if task_id else _("added"))
            return utils.successful_response(request, message, "samples:show_task_lists")
    else:
        samples_form = SamplesForm(user, preset_sample, task)
        initial = {}
        if "process_class" in request.GET:
            initial["process_class"] = request.GET["process_class"]
        task_form = TaskForm(request.user, instance=task, initial=initial)
    title = capfirst(_("edit task")) if task else capfirst(_("add task"))
    return render(request, "samples/edit_task.html", {"title": title, "task": task_form, "samples": samples_form})


def create_task_lists(user):
    """Create the datastructure containing the tasks associated with a user.  This
    can be used in the template to create a nested overview of the tasks.

    :param user: the user for which the tasks should be generated

    :type user: ``django.contrib.auth.models.User``

    :return:
      the tasks as list of (content type, verbose name, list of task info
      objects)

    :rtype: list of (``ContentType``, str, `TaskForTemplate`)
    """
    def get_department_name_of_type(content_type):
        # FixMe: It is possible that some processes are in more than one
        # department available.  Maybe we need a better way to determine the
        # department.
        app_label = content_type.model_class()._meta.app_label
        department_names = set(Department.objects.filter(app_label=app_label).values_list("name", flat=True))
        assert len(department_names) == 1
        return department_names.pop()
    one_week_ago = django.utils.timezone.now() - datetime.timedelta(weeks=1)
    task_lists = []
    seen_process_names = set()
    ambiguous_process_names = set()
    for process_content_type in user.samples_user_details.visible_task_lists.all():
        process_name = capfirst(force_text(process_content_type.model_class()._meta.verbose_name))
        active_tasks = process_content_type.tasks.order_by("-status", "priority", "last_modified"). \
            exclude(Q(status="0 finished") & Q(last_modified__lt=one_week_ago))
        task_lists.append((process_name, process_content_type, [TaskForTemplate(task, user) for task in active_tasks]))
        if process_name in seen_process_names:
            ambiguous_process_names.add(process_name)
        else:
            seen_process_names.add(process_name)
    disambiguated_task_lists = []
    for process_name, process_content_type, tasks in task_lists:
        if process_name in ambiguous_process_names:
            department_name = get_department_name_of_type(process_content_type)
            process_name += " ({})".format(department_name)
        disambiguated_task_lists.append((process_name, process_content_type, tasks))
    return disambiguated_task_lists


@help_link("demo.html#adding-a-task")
@login_required
def show(request):
    """Shows the task lists the user wants to see.
    It also provides the multiple choice list to select the task lists
    for the user.

    :Paramerters:
    :param request: the current HTTP Request object

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    if request.method == "POST":
        choose_task_lists_form = ChooseTaskListsForm(request.user, request.POST)
        if choose_task_lists_form.is_valid():
            request.user.samples_user_details.visible_task_lists.set(
                [ContentType.objects.get_for_id(int(id_))
                 for id_ in choose_task_lists_form.cleaned_data["visible_task_lists"] if id_])
            # In order to have a GET instead of a POST as the last request
            return utils.successful_response(request, view="samples:show_task_lists")
    else:
        choose_task_lists_form = ChooseTaskListsForm(request.user)
    task_lists = create_task_lists(request.user)
    return render(request, "samples/task_lists.html", {"title": capfirst(_("task lists")),
                                                       "choose_task_lists": choose_task_lists_form,
                                                       "task_lists": task_lists})


@login_required
@require_http_methods(["POST"])
def remove(request, task_id):
    """Deletes a task from the database.

    :Paramerters:
    :param request: the current HTTP Request object
    :param task_id: the id from the task, which has to be deleted

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    task = get_object_or_404(Task, id=utils.convert_id_to_int(task_id))
    if task.customer != request.user:
        raise permissions.PermissionError(request.user, _("You are not the customer of this task."))
    utils.Reporter(request.user).report_removed_task(task)
    task.delete()
    return utils.successful_response(request, _("The task was successfully removed."), "samples:show_task_lists")


_ = ugettext
