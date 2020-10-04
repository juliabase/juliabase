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


"""Add and show status messages for the apparatuses.
"""

import datetime
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.forms.utils import ValidationError
from django.shortcuts import render, get_object_or_404
import django.utils.timezone
from django.utils.translation import ugettext_lazy as _, ugettext
from django.utils.text import capfirst
import django.forms as forms
from jb_common.utils.base import check_markdown
from jb_common.search import DateTimeField
from samples import models
from samples.permissions import get_all_addable_physical_process_models, PermissionError
import samples.utils.views as utils


class StatusForm(forms.ModelForm):
    """The status message model form class.
    """
    operator = utils.FixedOperatorField(label=capfirst(_("operator")))
    status_level = forms.ChoiceField(label=capfirst(_("status level")), choices=models.StatusMessage.StatusLevel.choices,
                                     widget=forms.RadioSelect)
    begin = DateTimeField(label=capfirst(_("begin")), start=True, required=False, with_inaccuracy=True,
                          help_text=_("YYYY-MM-DD HH:MM:SS"))
    end = DateTimeField(label=capfirst(_("end")), start=False, required=False, with_inaccuracy=True,
                        help_text=_("YYYY-MM-DD HH:MM:SS"))
    process_classes = forms.MultipleChoiceField(label=capfirst(_("processes")))

    class Meta:
        model = models.StatusMessage
        fields = "__all__"

    @staticmethod
    def is_editable(cls):
        try:
            return cls.JBMeta.editable_status
        except AttributeError:
            return True

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["operator"].set_operator(user, user.is_superuser)
        self.fields["operator"].initial = user.pk
        self.fields["timestamp"].initial = django.utils.timezone.now()
        self.fields["process_classes"].choices = utils.choices_of_content_types(
            cls for cls in get_all_addable_physical_process_models() if self.is_editable(cls))
        self.fields["process_classes"].widget.attrs["size"] = 24

    def clean_message(self):
        """Forbid image and headings syntax in Markdown markup.
        """
        message = self.cleaned_data.get("message")
        if message:
            check_markdown(message)
        return message

    def clean_timestamp(self):
        """Forbid timestamps that are in the future.
        """
        timestamp = self.cleaned_data["timestamp"]
        if timestamp > django.utils.timezone.now():
            raise ValidationError(_("The timestamp must not be in the future."), code="invalid")
        return timestamp

    def clean(self):
        cleaned_data = super().clean()
        begin, end = cleaned_data.get("begin"), cleaned_data.get("end")
        if begin:
            cleaned_data["begin"], cleaned_data["begin_inaccuracy"] = cleaned_data["begin"]
        else:
            cleaned_data["begin"], cleaned_data["begin_inaccuracy"] = \
                    django.utils.timezone.make_aware(datetime.datetime(1900, 1, 1)), 6
        if end:
            cleaned_data["end"], cleaned_data["end_inaccuracy"] = cleaned_data["end"]
        else:
            cleaned_data["end"], cleaned_data["end_inaccuracy"] = \
                    django.utils.timezone.make_aware(datetime.datetime(9999, 12, 31)), 6
        if cleaned_data["begin"] > cleaned_data["end"]:
            self.add_error("begin", ValidationError(_("The begin must be before the end."), code="invalid"))
            del cleaned_data["begin"]
        if cleaned_data["status_level"] in ["red", "yellow"] and not cleaned_data.get("message"):
            self.add_error("message", ValidationError(
                _("A message must be given when the status level is red or yellow."), code="required"))
        return cleaned_data


@login_required
def add(request):
    """With this function, the messages are stored into the database.  It also gets
    the information for displaying the "add_status_message" template.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    if request.method == "POST":
        status_form = StatusForm(request.user, request.POST)
        if status_form.is_valid():
            status = status_form.save()
            for process_class in status.process_classes.all():
                utils.Reporter(request.user).report_status_message(process_class, status)
            return utils.successful_response(request, _("The status message was successfully added to the database."))
    else:
        status_form = StatusForm(request.user)
    title = _("Add status message")
    return render(request, "samples/add_status_message.html", {"title": title, "status": status_form})


@login_required
def show(request):
    """This function shows the current status messages for the physical process
    classes.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    now = django.utils.timezone.now()
    eligible_status_messages = models.StatusMessage.objects.filter(withdrawn=False, begin__lt=now, end__gt=now)
    process_classes = set()
    for status_message in eligible_status_messages:
        process_classes |= set(status_message.process_classes.all())
    status_messages = []
    for process_class in process_classes:
        current_status = eligible_status_messages.filter(process_classes=process_class).order_by("-begin", "-timestamp")[0]
        status_messages.append((current_status, process_class.model_class()._meta.verbose_name))
    consumed_status_message_ids = {item[0].id for item in status_messages}
    status_messages.sort(key=lambda item: item[1].lower())
    further_status_messages = {}
    for status_message in models.StatusMessage.objects.filter(withdrawn=False, end__gt=now).exclude(
        id__in=consumed_status_message_ids).order_by("end"):
        for process_class in status_message.process_classes.all():
            further_status_messages.setdefault(process_class.model_class()._meta.verbose_name, []).append(status_message)
    further_status_messages = sorted(further_status_messages.items(), key=lambda item: item[0].lower())
    return render(request, "samples/show_status.html", {"title": capfirst(_("status messages")),
                                                        "status_messages": status_messages,
                                                        "further_status_messages": further_status_messages})


@login_required
@require_http_methods(["POST"])
def withdraw(request, id_):
    """This function withdraws a status message for good.  Note that it
    withdraws it for all its connected process types.  It is idempotent.

    :param request: the current HTTP Request object
    :param id_: the id of the message to be withdrawn

    :type request: HttpRequest
    :type id_: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    status_message = get_object_or_404(models.StatusMessage, withdrawn=False, pk=utils.convert_id_to_int(id_))
    if request.user != status_message.operator:
        raise PermissionError(request.user, "You cannot withdraw status messages of another user.")
    status_message.withdrawn = True
    status_message.save()
    for process_class in status_message.process_classes.all():
        utils.Reporter(request.user).report_withdrawn_status_message(process_class, status_message)
    return utils.successful_response(request, _("The status message was successfully withdrawn."), "samples:show_status")


_ = ugettext
