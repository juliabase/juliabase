#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""Helper classes and function which have something to do with form generation
and validation.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six

import re, datetime, json
from django.db.models import Q
from django.conf import settings
from django.forms.util import ValidationError
from django.http import QueryDict
from django.utils.translation import ugettext_lazy as _, ugettext
from django.forms import ModelForm
import django.forms as forms
import django.contrib.auth.models
from django.contrib.contenttypes.models import ContentType
from django.utils.text import capfirst
from jb_common.utils.base import get_really_full_name, check_markdown, int_or_zero
from samples import models
from . import base as utils


__all__ = ("OperatorField", "ProcessForm", "DepositionForm", "get_my_layers", "InitialsForm",
           "EditDescriptionForm", "SampleField", "MultipleSamplesField", "FixedOperatorField", "DepositionSamplesForm",
           "SamplePositionForm", "RemoveFromMySamplesForm", "time_pattern", "clean_time_field", "clean_timestamp_field",
           "clean_quantity_field", "collect_subform_indices", "normalize_prefixes", "dead_samples",
           "choices_of_content_types", "check_sample_name", "SampleSelectForm", "MultipleSamplesSelectForm")


class OperatorField(forms.ChoiceField):
    # FixMe: This is the new variant of :py:class:`FixedOperatorField`.  It
    # makes :py:class:`FixedOperatorField` obsolete.
    """Form field class for the selection of a single operator.  This is
    intended for edit-process views when the operator must be the currently
    logged-in user, an external contact of that user, or the previous
    (external) operator.  It can be used in model forms.

    Normally, you use this field through :py:class:`ProcessForm`.

    The result of this field (if there was no validation error) is a tuple of
    two values, namely the operator and the external operator.  Exactly one of
    both is ``None`` if the respective type of operator was not given.

    It is senseful to show this field only to non-staff, and staff gets the
    usual operator/external operator fields.  In the IEK-5/FZJ implementation,
    we even allow all three fields for staff users as long as there no
    contradicting values are given.

    If you want to use this field for *non-staff*, do the following things:

    1. This field must be made required

    2. Make the possible choices of the operator and the external operator
       fields empty.  Exclude those fields from the HTML.

    3. Check in your ``clean()`` method whether non-staff submits an operator.
       Since the operator is required in ``samples.models.Process``, you must
       provide a senseful default for the operator if none was returned
       (because an external operator was selected).  I recommend to use the
       currently logged-in user in this case.

    A good example is in :py:mod:`institute.views.samples.substrate` of the INM
    adaption of JuliaBase.  There, you can also see how one can deal with staff
    users (especially interesting for the remote client).
    """

    def set_choices(self, user, old_process):
        """Set the operator list shown in the widget.  It combines selectable users and
        external operators.  You must call this method in the constructor of
        the form in which you use this field, otherwise the selection box will
        remain emtpy.  The selectable operators are:

        - the former operator of the process (if any)
        - the current user
        - the former external operator (if any)
        - all external operators for which the current user is the contact person.

        It works also for staff users, which can choose from *all* users and
        external operators (including inactive users such as “nobody”).

        :param user: the currently logged-in user.
        :param old_process: if the process is to be edited, the former instance
            of the process; otherwise, ``None``

        :type operator: django.contrib.auth.models.User
        :type old_process: `samples.models.Process`
        """
        self.user = user
        if user.is_staff:
            self.choices = django.contrib.auth.models.User.objects.values_list("pk", "username")
            external_operators = set(models.ExternalOperator.objects.all())
        else:
            self.choices = []
            if old_process:
                if old_process.operator != user:
                    self.choices.append((old_process.operator.pk, get_really_full_name(old_process.operator)))
                external_operators = {old_process.external_operator} if old_process.external_operator else set()
            else:
                external_operators = set()
            self.choices.append((user.pk, get_really_full_name(user)))
            external_operators |= set(user.external_contacts.all())
        if old_process:
            self.initial = "extern-{0}".format(old_process.external_operator.pk) if old_process.external_operator else \
                old_process.operator.pk
        else:
            self.initial = user.pk
        for external_operator in sorted(external_operators, key=lambda external_operator: external_operator.name):
            self.choices.append(("extern-{0}".format(external_operator.pk), external_operator.name))

    def clean(self, value):
        """Return the selected operator.  Additionally, it sets the attribute
        `external_operator` if the user selected one (it sets it to ``None``
        otherwise).  If an external operator was selected, this routine returns
        the currently logged-in user.

        If there was an error, this method returns ``("", None)`` (i.e., both
        values evaluate to ``False``).  Otherwise, it returns a tupe with
        exactly one non-``False`` value.

        :return:
          the selected operator, the selected external operator

        :rtype: django.contrib.auth.models.User,
          django.contrib.auth.models.User
        """
        value = super(OperatorField, self).clean(value)
        if value.startswith("extern-"):
            external_operator = models.ExternalOperator.objects.get(pk=int(value[7:]))
            return None, external_operator
        else:
            return value and django.contrib.auth.models.User.objects.get(pk=int(value)), None


class ProcessForm(ModelForm):
    """Abstract model form class for processes.  It ensures that timestamps are not
    in the future, and that comments contain only allowed Markdown syntax.

    Moreover, it defines a field “combined_operator” of the type
    :py:class:`OperatorField`.  In the HTML template, you should offer this
    field to non-staff, and the usual operator/external operator to staff.
    """
    combined_operator = OperatorField(label=_("Operator"))

    def __init__(self, user, *args, **kwargs):
        """
        :param user: the currently logged-in user

        :type user: django.contrib.auth.models.User
        """
        self.user = user
        self.process = kwargs.get("instance")
        self.unfinished = self.process and not self.process.finished
        if not self.process or self.unfinished:
            kwargs.setdefault("initial", {}).setdefault("timestamp", datetime.datetime.now())
        if not self.process:
            kwargs.setdefault("initial", {}).setdefault("operator", user.pk)
            kwargs["initial"].setdefault("combined_operator", user.pk)
        super(ProcessForm, self).__init__(*args, **kwargs)
        if self.process and self.process.finished:
            self.fields["finished"].widget.attrs["disabled"] = "disabled"
        self.fields["combined_operator"].set_choices(user, self.process)
        if not user.is_staff:
            self.fields["external_operator"].choices = []
            self.fields["operator"].choices = []
            self.fields["operator"].required = False
        else:
            self.fields["combined_operator"].required = False

    def clean_comments(self):
        """Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        check_markdown(comments)
        return comments

    def clean_timestamp(self):
        """Forbid timestamps that are in the future.
        """
        timestamp = clean_timestamp_field(self.cleaned_data["timestamp"])
        if self.process and self.process.timestamp > timestamp:
            raise ValidationError(_("The timestamp was older than the one in the database.  Probably someone else has "
                                    "edited the process by now.  If so, open the process in another tab and combine the "
                                    "changes."))
        return timestamp

    def clean_finished(self):
        """Return ``True`` always.  If you want to implement the
        “unfinished-process” functionality in your process class, you must
        override this method.
        """
        return True

    def clean(self):
        cleaned_data = super(ProcessForm, self).clean()
        final_operator = cleaned_data.get("operator")
        final_external_operator = cleaned_data.get("external_operator")
        if cleaned_data.get("combined_operator"):
            operator, external_operator = cleaned_data["combined_operator"]
            if operator:
                if final_operator and final_operator != operator:
                    self.add_error("combined_operator", "Your operator and combined operator didn't match.")
                else:
                    final_operator = operator
            if external_operator:
                if final_external_operator and final_external_operator != external_operator:
                    self.add_error("combined_external_operator",
                                   "Your external operator and combined external operator didn't match.")
                else:
                    final_external_operator = external_operator
        if not final_operator:
            # Can only happen for non-staff.  I deliberately overwrite a
            # previous operator because this way, we can log who changed it.
            final_operator = self.user
        cleaned_data["operator"], cleaned_data["external_operator"] = final_operator, final_external_operator
        return cleaned_data

    def is_referentially_valid(self, sample_form):
        """Test whether the forms are consistent with each other and with the database.
        In its current form, it only checks whether the sample is still “alive”
        at the time of the measurement.

        :param sample_form: a bound sample selection form

        :type sample_form: `SampleForm`

        :return:
          whether the forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if self.is_valid() and sample_form.is_valid() and \
           dead_samples([sample_form.cleaned_data["sample"]], self.cleaned_data["timestamp"]):
            self.add_error("timestamp", _("Sample is already dead at this time."))
            referentially_valid = False
        return referentially_valid


class DepositionForm(ProcessForm):
    """Model form for depositions (not their layers).
    """
    def __init__(self, user, data=None, **kwargs):
        super(DepositionForm, self).__init__(user, data, **kwargs)
        if self.process and self.process.finished:
            self.fields["number"].widget.attrs.update({"readonly": "readonly"})

    def clean_number(self):
        number = self.cleaned_data["number"]
        if self.process and self.process.finished:
            if self.process.number != number:
                raise ValidationError(_("The deposition number must not be changed."))
        else:
            if models.Deposition.objects.filter(number=number).exists():
                raise ValidationError(_("This deposition number exists already."))
        return number


def get_my_layers(user_details, deposition_model):
    """Parse the ``my_layers`` string of a user and convert it to valid input
    for a form selection field (``ChoiceField``).  Notethat the user is not
    forced to select a layer.  Instead, the result always includes a “nothing
    selected” option.

    :param user_details: the details of the current user
    :param deposition_model: the model class for which “MyLayers” should be
        generated

    :type user_details: `samples.models.UserDetails`
    :type deposition_model: class, descendent of `samples.models.Deposition`

    :return:
      a list ready-for-use as the ``choices`` attribute of a ``ChoiceField``.
      The MyLayer IDs are given as strings in the form “<deposition id>-<layer
      number>”.

    :rtype: list of (MyLayer-ID, nickname)
    """
    choices = [("", "---------")]
    if user_details.my_layers:
        for nickname, process_id, layer_number in json.loads(user_details.my_layers):
            try:
                deposition = deposition_model.objects.get(pk=process_id)
            except deposition_model.DoesNotExist:
                continue
            try:
                layer = deposition.layers.get(number=layer_number)
            except:
                continue
            # FixMe: Maybe it is possible to avoid serialising the deposition ID
            # and layer number, so that change_structure() doesn't have to re-parse
            # it.  In other words: Maybe the first element of the tuples can be of
            # any type and needn't be strings.
            choices.append(("{0}-{1}".format(process_id, layer_number), nickname))
    return choices


class InitialsForm(forms.Form):
    """Form for a person's initials.  A “person” can be a user, an external
    operator, or `None`.  Initials are optional, however, if you choose them, you cannot
    change (or delete) them anymore.
    """
    initials = forms.CharField(label=capfirst(_("initials")), max_length=4, required=False)

    def __init__(self, person, initials_mandatory, *args, **kwargs):
        super(InitialsForm, self).__init__(*args, **kwargs)
        self.fields["initials"].required = initials_mandatory
        self.person = person
        self.is_user = isinstance(person, django.contrib.auth.models.User)
        self.readonly = False
        if person:
            try:
                initials = person.initials
                self.readonly = True
            except models.Initials.DoesNotExist:
                pass
        if self.readonly:
            self.fields["initials"].widget.attrs["readonly"] = "readonly"
            self.fields["initials"].initial = initials

    def clean_initials(self):
        initials = self.cleaned_data["initials"]
        if not initials or self.readonly:
            return initials
        properties = settings.INITIALS_FORMATS["user" if self.is_user else "external_contact"]
        pattern = properties["regex"]
        if not pattern.match(initials):
            raise ValidationError(properties["description"])
        if models.Initials.objects.filter(initials=initials).exists():
            raise ValidationError(_("These initials are already used."))
        return initials

    def save(self, person=None):
        """Although this is not a model form, I add a ``save()`` method in
        order to avoid code duplication.  Here, I test whether the “initials”
        field in the database is still empty, and if so, add it to the
        database.
        """
        initials = self.cleaned_data["initials"]
        self.person = self.person or person
        if initials:
            if self.is_user:
                if not models.Initials.objects.filter(user=self.person).exists():
                    models.Initials.objects.create(initials=initials, user=self.person)
            else:
                if not models.Initials.objects.filter(external_operator=self.person).exists():
                    models.Initials.objects.create(initials=initials, external_operator=self.person)


class EditDescriptionForm(forms.Form):
    """Form for letting the user enter a short description of the changes they
    made.
    """
    description = forms.CharField(label=_("Description of edit"), widget=forms.Textarea)
    important = forms.BooleanField(label=_("Important edit"), required=False)

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "edit_description"
        super(EditDescriptionForm, self).__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["rows"] = 3

    def clean_description(self):
        """Forbid image and headings syntax in Markdown markup.
        """
        description = self.cleaned_data["description"]
        check_markdown(description)
        return description


class GeneralSampleField(object):
    """Mixin class for the samples selection box.  It is used in the two form
    field classes `SampleField` and `MultipleSamplesField`.  Never instantiate
    this class.

    The clever bit here is that I use the ``<OPTGROUP>`` feature of HTML in
    order to have a structured list.  Some samples may occur twice in the list
    because of this; you may select both without a negative effect.
    """

    def set_samples(self, user, samples=None):
        """Set the sample list shown in the widget.  You *must* call this
        method in the constructor of the form in which you use this field,
        otherwise the selection box will remain emtpy.

        :param user: the user for which this field is generated; he may not be
            allowed to see all topic names, therefore it is necessary to know
            who it is
        :param samples: Samples to be included into the list.  Typically, these
            are the current user's “My Samples”, plus the samples that were
            already connected with the deposition or measurement when you edit
            it.  It defaults to the user's “My Samples”.

        :type user: django.contrib.auth.models.User
        :type samples: iterable of `samples.models.Sample`
        """
        def get_samples_from_topic(topic, folded_topics_and_sample_series):
            if not topic.topic.id in folded_topics_and_sample_series:
                seriesless_samples = [(sample.pk, sample.name_with_tags(user)) for sample in topic.samples]
                self.choices.append((topic.topic_name, seriesless_samples))
                for series in topic.sample_series:
                    if not series.sample_series.get_hash_value() in folded_topics_and_sample_series:
                        samples = [(sample.pk, 4 * " " + sample.name_with_tags(user)) for sample in series.samples]
                        self.choices.append((4 * " " + series.name, samples))
                for sub_topic in topic.sub_topics:
                    get_samples_from_topic(sub_topic, folded_topics_and_sample_series)

        folded_topics_and_sample_series = []
        folded_topics_and_sample_series.extend(json.loads(user.samples_user_details.folded_series))
        folded_topics_and_sample_series.extend(json.loads(user.samples_user_details.folded_topics))
        topics, topicless_samples = utils.build_structured_sample_list(user, samples)
        self.choices = [(sample.pk, sample.name_with_tags(user)) for sample in topicless_samples]
        for topic in topics:
            get_samples_from_topic(topic, folded_topics_and_sample_series)
        if not isinstance(self, forms.MultipleChoiceField) or not self.choices:
            self.choices.insert(0, ("", 9 * "-"))


class SampleField(GeneralSampleField, forms.ChoiceField):
    """Form field class for sample selection boxes where you can select a
    single sample.  This is typically used in measurement forms because
    normally, one measures only *one* sample at a time.
    """

    def clean(self, value):
        value = super(SampleField, self).clean(value)
        if value:
            return models.Sample.objects.get(pk=int(value))


class MultipleSamplesField(GeneralSampleField, forms.MultipleChoiceField):
    """Form field class for sample selection boxes where you can select many
    samples at once.  This is typically used in deposition forms because most
    deposition systems can deposit more than one sample in a single run.
    """

    def clean(self, value):
        if value == [""]:
            value = []
        value = super(MultipleSamplesField, self).clean(value)
        return models.Sample.objects.in_bulk([int(pk) for pk in set(value)]).values()


class FixedOperatorField(forms.ChoiceField):
    """Form field class for the *fixed* selection of a single user.  This is
    intended for edit-process views when the operator must be the currently
    logged-in user, or the previous operator.  In other words, it must be
    impossible to change it.  Then, you can use this form field for the
    operator, and hide the field from display by ``style="display: none"`` in
    the HTML template.

    Important: This field must *always* be made required!
    """

    def set_operator(self, operator, is_staff=False):
        """Set the user list shown in the widget.  You *must* call this method
        in the constructor of the form in which you use this field, otherwise
        the selection box will remain emtpy.  The selection list will consist
        only of the given operator, with no other choice (not even the empty
        field).

        :param operator: operator to be included into the list.  Typically, it
            is the current user.
        :param is_staff: whether the currently logged-in user is an
            administrator

        :type operator: django.contrib.auth.models.User
        :type is_staff: bool
        """
        if not is_staff:
            self.choices = ((operator.pk, operator.username),)
        else:
            self.choices = django.contrib.auth.models.User.objects.values_list("pk", "username")

    def clean(self, value):
        value = super(FixedOperatorField, self).clean(value)
        return django.contrib.auth.models.User.objects.get(pk=int(value))


class DepositionSamplesForm(forms.Form):
    """Form for the list selection of samples that took part in the deposition.
    This form has the special behaviour that it prevents changing the samples
    when editing an *existing* process.
    """
    sample_list = MultipleSamplesField(label=_("Samples"))

    def __init__(self, user, deposition, preset_sample, data=None, **kwargs):
        samples = list(user.my_samples.all())
        if deposition:
            kwargs["initial"] = {"sample_list": deposition.samples.values_list("pk", flat=True)}
            if deposition.finished:
                # If editing a finished, existing deposition, always have an
                # *unbound* form so that the samples are set although sample
                # selection is "disabled" and thus never successful when
                # submitting.  This is necessary for depositions because they can
                # change the name of samples, and so changing the affected samples
                # afterwards is a source of big trouble.
                super(DepositionSamplesForm, self).__init__(**kwargs)
                self.fields["sample_list"].widget.attrs["disabled"] = "disabled"
            else:
                super(DepositionSamplesForm, self).__init__(data, **kwargs)
            samples.extend(deposition.samples.all())
        else:
            super(DepositionSamplesForm, self).__init__(data, **kwargs)
            self.fields["sample_list"].initial = []
            if preset_sample:
                samples.append(preset_sample)
                self.fields["sample_list"].initial.append(preset_sample.pk)
        self.fields["sample_list"].set_samples(user, samples)
        self.fields["sample_list"].widget.attrs.update({"size": "17", "style": "vertical-align: top"})


class SamplePositionForm(forms.Form):
    sample = forms.CharField(label=capfirst(_("sample")))
    position = forms.CharField(label=capfirst(_("sample position")), required=False)

    def __init__(self, user, preset_sample, preset_sample_position, *args, **kwargs):
        """
        :param user: the current user
        :param preset_sample: the selected sample to which the sample position should be
            appended when creating a new process
        :param preset_sample_position: the place from the selected sample in the apparatus

        :type user: django.contrib.auth.models.User
        :type preset_sample: `samples.models.Sample`
        :type preset_sample_position: str
        """
        super(SamplePositionForm, self).__init__(*args, **kwargs)
        self.fields["sample"].initial = preset_sample
        self.fields["sample"].widget.attrs['readonly'] = True
        if preset_sample_position:
            self.fields["position"].initial = preset_sample_position


    def clean_sample(self):
        sample_name = self.cleaned_data.get("sample")
        if sample_name:
            if sample_name.startswith("*"):
                sample_name = "*{0:05}".format(int(sample_name.strip("*")))
            return models.Sample.objects.get(name=sample_name)

    def clean(self):
        cleaned_data = super(SamplePositionForm, self).clean()
        sample = cleaned_data.get("sample")
        place = cleaned_data.get("position")
        if sample and not place:
            self.add_error("position", _("This field is required."))
            del cleaned_data["sample"]
        return cleaned_data


class RemoveFromMySamplesForm(forms.Form):
    """Form for the question whether the user wants to remove the samples
    from the “My Samples” list after the process.
    """
    remove_from_my_samples = forms.BooleanField(label=_("Remove processed sample(s) from My Samples"),
                                                required=False, initial=False)


time_pattern = re.compile(r"^\s*((?P<H>\d{1,3}):)?(?P<M>\d{1,2}):(?P<S>\d{1,2})\s*$")
"""Standard regular expression pattern for time durations in JuliaBase:
HH:MM:SS, where hours can also be 3-digit and are optional."""
def clean_time_field(value):
    """General helper function for use in the ``clean_...`` methods in forms.
    It tests whether the time format is correct, and normalises the duration so
    that minutes and seconds are 2-digit, and leading zeros are eliminated from
    the hours.

    :param value: the value input by the user.  Usually this is the result of a
        ``cleaned_data[...]`` call.

    :type value: str

    :return:
      the normalised time

    :rtype: str

    :raises ValidationError: if the value given was not a valid duration time.
    """
    if not value:
        return ""
    match = time_pattern.match(value)
    if not match:
        raise ValidationError(_("Time must be given in the form HH:MM:SS."))
    hours, minutes, seconds = match.group("H"), int(match.group("M")), int(match.group("S"))
    hours = int(hours) if hours is not None else 0
    if minutes >= 60 or seconds >= 60:
        raise ValidationError(_("Minutes and seconds must be smaller than 60."))
    if not hours:
        return "{0}:{1:02}".format(minutes, seconds)
    else:
        return "{0}:{1:02}:{2:02}".format(hours, minutes, seconds)


def clean_timestamp_field(value):
    """General helper function for use in the ``clean_...`` methods in forms.
    It tests whether the given timestamp is not in the future or to far in the past.
    It also works for date fields.

    The test of correct input is performed by the field class itself.

    :param value: the value input by the user.  Usually this is the result of a
        ``cleaned_data[...]`` call.

    :type value: datetime.date or datetime.datetime

    :return:
        the original ``value`` (unchanged)

    :rtype: datetime.date or datetime.datetime

    :raises ValidationError: if the specified timestamp lies in the future or
        to far in the past.
    """
    if isinstance(value, datetime.datetime):
        # Allow mis-sychronisation of clocks of up to one minute.
        if value > datetime.datetime.now() + datetime.timedelta(minutes=1):
            raise ValidationError(_("The timestamp must not be in the future."))
    else:
        if value > datetime.date.today():
            raise ValidationError(_("The date must not be in the future."))
    if value.year < 1900:
        raise ValidationError(_("The year must not be earlier than 1900."))
    return value


quantity_pattern = re.compile(r"^\s*(?P<number>[-+]?\d+(\.\d+)?(e[-+]?\d+)?)\s*(?P<unit>[a-uA-Zµ]+)\s*$")
"""Regular expression pattern for valid physical quantities."""
def clean_quantity_field(value, units):
    """General helper function for use in the ``clean_...`` methods in forms.
    It tests whether the format of the physical quantity is correct, and
    normalises it so that it only contains decimal points (no commas), a proper
    »µ«, and exactly one space sign between value and unit.

    :param value: the value input by the user.  Usually this is the result of a
        ``cleaned_data[...]`` call.

    :type value: str

    :return:
      the normalised physical quantity

    :rtype: str

    :raises ValidationError: if the value given was not a valid physical
        quantity.
    """
    if not value:
        return ""
    value = six.text_type(value).replace(",", ".").replace("μ", "µ")  # No, these µ are not the same!
    match = quantity_pattern.match(value)
    if not match:
        raise ValidationError(_("Must be a physical quantity with number and unit."))
    original_unit = match.group("unit").lower()
    for unit in units:
        if unit.lower() == original_unit.lower():
            break
    else:
        raise ValidationError(_("The unit is invalid.  Valid units are: {units}").format(units=", ".join(units)))
    return match.group("number") + " " + unit


def collect_subform_indices(post_data, subform_key="number", prefix=""):
    """Find all indices of subforms of a certain type (e.g. layers) and return
    them so that the objects (e.g. layers) have a sensible order (e.g. sorted
    by layer number).  This is necessary because indices are used as form
    prefixes and cannot be changed easily, even if the layers are rearranged,
    duplicated, or deleted.  By using this function, the view has the chance to
    have everything in proper order nevertheless.

    :param post_data: the result from ``request.POST``
    :param subform_key: the fieldname in the forms that is used for ordering.
        Defaults to ``number``.
    :param prefix: an additional prefix to prepend to every form field name
        (even before the index).  (Is almost never used.)

    :type post_data: QueryDict

    :return:
      list with all found indices having this form prefix and key.
      Their order is so that the respective values for that key are ascending.

    :rtype: list of int
    """
    subform_name_pattern = re.compile(re.escape(prefix) + r"(?P<index>\d+)(_\d+)*-(?P<key>.+)")
    values = {}
    for key, value in post_data.items():
        match = subform_name_pattern.match(key)
        if match:
            index = int(match.group("index"))
            if match.group("key") == subform_key:
                values[index] = value
            elif index not in values:
                values[index] = None
    last_value = 0
    for index in sorted(values):
        try:
            value = int(values[index])
        except (TypeError, ValueError):
            value = last_value + 0.01
        last_value = values[index] = value
    return sorted(values, key=lambda index: values[index])


level0_pattern = re.compile(r"(?P<level0_index>\d+)-(?P<id>.+)")
level1_pattern = re.compile(r"(?P<level0_index>\d+)_(?P<level1_index>\d+)-(?P<id>.+)")
def normalize_prefixes(post_data):
    """Manipulates the prefixes of POST data keys for bringing them in
    consecutive order.  It only works for at most two-level numeric prefixes,
    which is sufficient for most purposes.  For example, in the 6-chamber
    deposition view, top-level is the layer index, and second-level is the
    channel index.

    The format of prefixes must be "1" for layers, and "1_1" for channels.

    By deleting layers or channels, the indeces might be sparse, so this
    routine re-indexes everything so that the gaps are filled.

    :param post_data: the POST data as returned by ``request.POST``.

    :type post_data: QueryDict

    :return:
      the normalised POST data, the number of top-level prefixes, and a list
      with the number of all second-level prefixes.

    :rtype: QueryDict, int, list of int
    """
    level0_indices = set()
    level1_indices = {}
    digested_post_data = {}
    for key in post_data:
        match = level0_pattern.match(key)
        if match:
            level0_index = int(match.group("level0_index"))
            level0_indices.add(level0_index)
            level1_indices.setdefault(level0_index, set())
            digested_post_data[level0_index, match.group("id")] = post_data.getlist(key)
        else:
            match = level1_pattern.match(key)
            if match:
                level0_index, level1_index = int(match.group("level0_index")), int(match.group("level1_index"))
                level0_indices.add(level0_index)
                level1_indices.setdefault(level0_index, set()).add(level1_index)
                digested_post_data[level1_index, level0_index, match.group("id")] = post_data.getlist(key)
            else:
                digested_post_data[key] = post_data.getlist(key)
    level0_indices = sorted(level0_indices)
    normalization_necessary = level0_indices and level0_indices[-1] != len(level0_indices) - 1
    for key, value in level1_indices.items():
        level1_indices[key] = sorted(value)
        normalization_necessary = normalization_necessary or (
            level1_indices[key] and level1_indices[key][-1] != len(level1_indices[key]) - 1)
    if normalization_necessary:
        new_post_data = QueryDict("").copy()
        for key, value in digested_post_data.items():
            if isinstance(key, six.string_types):
                new_post_data.setlist(key, value)
            elif len(key) == 2:
                new_post_data.setlist("{0}-{1}".format(level0_indices.index(key[0]), key[1]), value)
            else:
                new_level0_index = level0_indices.index(key[1])
                new_post_data.setlist("{0}_{1}-{2}".format(new_level0_index, level1_indices[key[1]].index(key[0]), key[2]),
                                      value)
    else:
        new_post_data = post_data
    return new_post_data, len(level0_indices), [len(level1_indices[i]) for i in level0_indices]


def dead_samples(samples, timestamp):
    """Determine all samples from ``samples`` which are already dead at the
    given ``timestamp``.

    :param samples: the samples to be tested
    :param timestamp: the timestamp for which the dead samples should be found

    :type samples: list of `samples.models.Sample`
    :type timestamp: datetime.datetime

    :return:
      set of all samples which are dead at ``timestamp``

    :rtype: set of `samples.models.Sample`
    """
    result = set()
    for sample in samples:
        death_timestamps = \
            sample.processes.filter(sampledeath__timestamp__isnull=False).values_list("timestamp", flat=True)
        assert len(death_timestamps) <= 1
        if death_timestamps and death_timestamps[0] <= timestamp:
            result.add(sample)
    return result


def choices_of_content_types(classes):
    """Returns the ``choices`` field for a ``MultipleChoiceField`` which
    contains content types.  Typically, the `classes` are process classes that
    can be picked by the user.

    This routine is necessary for two reasons: It translates the model names
    behind the content types – ``six.text_type(contentype_instance)`` yields the
    English model name only.  And secondly, it sorts the choices by their
    (translated) names.

    :param classes: the classes which should be included into the selection box

    :type classes: list of class

    :return:
      the choices, ready to be used for a ``MultipleChoiceField``

    :rtype: list of (int, unicode)
    """
    # FixMe: The translation functionality in this function may become
    # superfluous when Django Ticket #16803 is fixed.
    choices = [(ContentType.objects.get_for_model(cls).id, cls._meta.verbose_name) for cls in classes]
    choices.sort(key=lambda item: item[1].lower())
    return choices


def check_sample_name(match, user, is_new=True):
    """Check whether the sample name match contains valid data.  This enforces
    additional constraints to sample names.  With `utils.sample_name_format`,
    you check whether the sample names matches and pattern, given as a regular
    explression.  However, if the pattern contains e.g. user initials, it is
    not checked whether the user initials actually belong to the current user.
    This is done here.  If anything fails, a `ValidationError` is raised.  This
    way, it can be called conveniently from ``Form`` methods.

    :param match: the match object as returned by `utils.sample_name_format`.
    :param user: the currently logged-in user
    :param is_new: whether the sample name is created right in this moment; if
        ``False``, we are checking old sample names, which results in _much_
        lesser checks

    :type match: re.MatchObject
    :type user: django.contrib.auth.models.User
    :type is_new: bool

    :raises ValidationError: if the sample name (represented by the match object)
        contained invalid fields.
    """
    groups = {key: value for key, value in match.groupdict().items() if value is not None}
    if "year" in groups:
        if int(groups["year"]) != datetime.datetime.now().year:
            raise ValidationError(_("The year must be the current year."))
    if "short_year" in groups:
        if 2000 + int(groups["short_year"]) != datetime.datetime.now().year:
            raise ValidationError(_("The year must be the current year."))
    if "user_initials" in groups:
        try:
            error = groups["user_initials"] != user.initials.initials
        except models.Initials.DoesNotExist:
            error = True
        if error:
            raise ValidationError(_("The initials do not match yours."))
    if "external_contact_initials" in groups:
        if not models.Initials.objects.filter(initials=groups["external_contact_initials"],
                                              external_operator__contact_persons=user).exists():
            raise ValidationError(_("The initials do not match any of your external contacts."))
    if "combined_initials" in groups:
        if not models.Initials.objects.filter(initials=groups["combined_initials"]). \
           filter(Q(external_operator__contact_persons=user) | Q(user=user)).exists():
            raise ValidationError(_("The initials do not match yours, nor any of your external contacts."))


class SampleSelectForm(forms.Form):
    """Form for the sample selection field.  You can only select *one* sample
    per process (in contrast to depositions).
    """
    sample = SampleField(label=capfirst(_("sample")))

    def __init__(self, user, process_instance, preset_sample, *args, **kwargs):
        """
        :param user: the current user
        :param process_instance: the process instance to be edited, or ``None`` if
            a new is about to be created
        :param preset_sample: the sample to which the process should be
            appended when creating a new process; see
            `utils.extract_preset_sample`

        :type user: django.contrib.auth.models.User
        :type process_instance: `samples.models.Process`
        :type preset_sample: `samples.models.Sample`
        """
        super(SampleSelectForm, self).__init__(*args, **kwargs)
        samples = list(user.my_samples.all())
        if process_instance:
            sample = process_instance.samples.get()
            samples.append(sample)
            self.fields["sample"].initial = sample.pk
        if preset_sample:
            samples.append(preset_sample)
            self.fields["sample"].initial = preset_sample.pk
        self.fields["sample"].set_samples(user, samples)


class MultipleSamplesSelectForm(forms.Form):
    """Form for the list selection of samples that took part in a process.
    """
    sample_list = MultipleSamplesField(label=capfirst(_("samples")))

    def __init__(self, user, process_instance, preset_sample, *args, **kwargs):
        super(MultipleSamplesSelectForm, self).__init__(*args, **kwargs)
        samples = list(user.my_samples.all())
        if process_instance:
            samples.extend(process_instance.samples.all())
            self.fields["sample_list"].initial = process_instance.samples.values_list("pk", flat=True)
        else:
            self.fields["sample_list"].initial = []
        if preset_sample:
            samples.append(preset_sample)
            self.fields["sample_list"].initial.append(preset_sample.pk)
        self.fields["sample_list"].set_samples(user, samples)
        self.fields["sample_list"].widget.attrs.update({"size": "17", "style": "vertical-align: top"})


_ = ugettext
