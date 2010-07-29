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


u"""Helper classes and function which have something to do with form generation
and validation.
"""

from __future__ import absolute_import

import re, os.path, datetime
from django.forms.util import ErrorList, ValidationError
from django.http import QueryDict
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms import ModelForm
import django.forms as forms
import django.contrib.auth.models
from chantal_common.utils import get_really_full_name, check_markdown
from chantal_common.models import Topic
from samples import models, permissions
from samples.views import utils


# FixMe: Should this also contain "operator = OperatorField"?

class ProcessForm(ModelForm):
    u"""Abstract model form class for processes.  It ensures that timestamps
    are not in the future, and that comments contain only allowed Markdown
    syntax.
    """

    def clean_comments(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        check_markdown(comments)
        return comments

    def clean_timestamp(self):
        u"""Forbid timestamps that are in the future.
        """
        timestamp = self.cleaned_data["timestamp"]
        if timestamp > datetime.datetime.now():
            raise ValidationError(_(u"The timestamp must not be in the future."))
        return timestamp


class DataModelForm(ModelForm):
    _ = ugettext_lazy
    u"""Model form class for accessing the data fields of a bound form, whether
    it is valid or not.  This is sometimes useful if you want to do structural
    changes to the forms in a view, and you don't want to do that only if the
    data the user has given is totally valid.

    Actually, using this class is bad style nevertheless.  It is used in the
    module `six_chamber_deposition`, however, for upcoming processes, it should
    be avoided and extra forms used instead.
    """

    def uncleaned_data(self, fieldname):
        u"""Get the field value of a *bound* form, even if it is invalid.

        :Parameters:
          - `fieldname`: name (=key) of the field

        :type fieldname: str

        :Return:
          the value of the field

        :rtype: unicode
        """
        return self.data.get(self.prefix + "-" + fieldname)


def get_my_layers(user_details, deposition_model):
    u"""Parse the ``my_layers`` string of a user and convert it to valid input
    for a form selection field (``ChoiceField``).  Notethat the user is not
    forced to select a layer.  Instead, the result always includes a “nothing
    selected” option.

    :Parameters:
      - `user_details`: the details of the current user
      - `deposition_model`: the model class for which “MyLayers” should be
        generated

    :type user_details: `models.UserDetails`
    :type deposition_model: class, descendent of `models.Deposition`

    :Return:
      a list ready-for-use as the ``choices`` attribute of a ``ChoiceField``.
      The MyLayer IDs are given as strings in the form “<deposition id>-<layer
      number>”.

    :rtype: list of (MyLayer-ID, nickname)
    """
    if not user_details.my_layers:
        return [(u"", u"---------")]
    items = [item.split(":", 1) for item in user_details.my_layers.split(",")]
    items = [(item[0].strip(),) + tuple(item[1].rsplit("-", 1)) for item in items]
    items = [(item[0], int(item[1]), int(item[2])) for item in items]
    fitting_items = [(u"", u"---------")]
    for nickname, deposition_id, layer_number in items:
        try:
            deposition = deposition_model.objects.get(pk=deposition_id)
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
        fitting_items.append((u"{0}-{1}".format(deposition_id, layer_number), nickname))
    return fitting_items


class AddLayersForm(forms.Form):
    _ = ugettext_lazy
    number_of_layers_to_add = forms.IntegerField(label=_(u"Number of layers to be added"), min_value=0, max_value=10, required=False)
    my_layer_to_be_added = forms.ChoiceField(label=_(u"Nickname of My Layer to be added"), required=False)

    def __init__(self, user_details, model, data=None, **kwargs):
        super(AddLayersForm, self).__init__(data, **kwargs)
        self.fields["my_layer_to_be_added"].choices = get_my_layers(user_details, model)
        self.model = model

    def clean_number_of_layers_to_add(self):
        return utils.int_or_zero(self.cleaned_data["number_of_layers_to_add"])

    def clean_my_layer_to_be_added(self):
        nickname = self.cleaned_data["my_layer_to_be_added"]
        if nickname and "-" in nickname:
            deposition_id, layer_number = self.cleaned_data["my_layer_to_be_added"].split("-")
            deposition_id, layer_number = int(deposition_id), int(layer_number)
            try:
                deposition = self.model.objects.get(pk=deposition_id)
            except self.model.DoesNotExist:
                pass
            else:
                layer_query = deposition.layers.filter(number=layer_number)
                if layer_query.count() == 1:
                    return layer_query.values()[0]


initials_pattern = re.compile(ur"[A-Z]{2,4}[0-9]*$")

class InitialsForm(forms.Form):
    u"""Form for a person's initials.  A “person” can be a user or an external
    operator.  Initials are optional, however, if you choose them, you cannot
    change (or delete) them anymore.
    """
    _ = ugettext_lazy
    # FixMe: Use lowercase form and .capitalize() to ease translating.
    initials = forms.CharField(label=_(u"Initials"), max_length=4, required=False)

    def __init__(self, person, initials_mandatory, *args, **kwargs):
        super(InitialsForm, self).__init__(*args, **kwargs)
        self.fields["initials"].required = initials_mandatory
        self.person = person
        self.is_user = isinstance(person, django.contrib.auth.models.User)
        try:
            initials = person.initials
            self.readonly = True
        except models.Initials.DoesNotExist:
            self.readonly = False
        if self.readonly:
            self.fields["initials"].widget.attrs["readonly"] = "readonly"
            self.fields["initials"].initial = initials
        self.fields["initials"].min_length = 2 if self.is_user else 4

    def clean_initials(self):
        initials = self.cleaned_data["initials"]
        if not initials or self.readonly:
            return initials
        # Note that minimal and maximal length are already checked.
        if not initials_pattern.match(initials):
            raise ValidationError(_(u"The initials must start with two uppercase letters.  "
                                    u"They must contain uppercase letters and digits only.  Digits must be at the end."))
        if models.Initials.objects.filter(initials=initials).exists():
            raise ValidationError(_(u"These initials are already used."))
        return initials

    def save(self):
        u"""Although this is not a model form, I add a ``save()`` method in
        order to avoid code duplication.  Here, I test whether the “initials”
        field in the database is still empty, and if so, add it to the
        database.
        """
        initials = self.cleaned_data["initials"]
        if initials:
            if self.is_user:
                if not models.Initials.objects.filter(user=self.person).exists():
                    models.Initials.objects.create(initials=initials, user=self.person)
            else:
                if not models.Initials.objects.filter(external_operator=self.person).exists():
                    models.Initials.objects.create(initials=initials, external_operator=self.person)


class EditDescriptionForm(forms.Form):
    _ = ugettext_lazy
    description = forms.CharField(label=_(u"Description of edit"), widget=forms.Textarea)
    important = forms.BooleanField(label=_(u"Important edit"), required=False)

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "edit_description"
        super(EditDescriptionForm, self).__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["rows"] = 3

    def clean_description(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        description = self.cleaned_data["description"]
        check_markdown(description)
        return description


class GeneralSampleField(object):
    u"""Mixin class for the samples selection box.  It is used in the two form
    field classes `SampleField` and `MultipleSamplesField`.  Never instantiate
    this class.

    The clever bit here is that I use the ``<OPTGROUP>`` feature of HTML in
    order to have a structured list.  Some samples may occur twice in the list
    because of this; you may select both without a negative effect.
    """

    def set_samples(self, samples, user):
        u"""Set the sample list shown in the widget.  You *must* call this
        method in the constructor of the form in which you use this field,
        otherwise the selection box will remain emtpy.

        :Parameters:
          - `samples`: Samples to be included into the list.  Typically, these
            are the current user's “My Samples”, plus the samples that were
            already connected with the deposition or measurement when you edit
            it.
          - `user`: the user for which this field is generated; he may not be
            allowed to see all topic names, therefore it is necessary to know
            who it is

        :type samples: list of `models.Sample`
        :type user: ``django.contrib.auth.models.User``
        """
        topics, topicless_samples = utils.build_structured_sample_list(samples, user)
        self.choices = [(sample.pk, unicode(sample)) for sample in topicless_samples]
        for topic in topics:
            seriesless_samples = [(sample.pk, unicode(sample)) for sample in topic.samples]
            self.choices.append((topic.topic_name, seriesless_samples))
            for series in topic.sample_series:
                samples = [(sample.pk, 4*u" " + unicode(sample)) for sample in series.samples]
                self.choices.append((4*u" " + series.name, samples))
        if not isinstance(self, forms.MultipleChoiceField) or not self.choices:
            self.choices.insert(0, (u"", 9*u"-"))


class SampleField(GeneralSampleField, forms.ChoiceField):
    u"""Form field class for sample selection boxes where you can select a
    single sample.  This is typically used in measurement forms because
    normally, one measures only *one* sample at a time.
    """

    def clean(self, value):
        value = super(SampleField, self).clean(value)
        if value:
            return models.Sample.objects.get(pk=int(value))


class MultipleSamplesField(GeneralSampleField, forms.MultipleChoiceField):
    u"""Form field class for sample selection boxes where you can select many
    samples at once.  This is typically used in deposition forms because most
    deposition systems can deposit more than one sample in a single run.
    """

    def clean(self, value):
        if value == [u""]:
            value = []
        value = super(MultipleSamplesField, self).clean(value)
        return models.Sample.objects.in_bulk([int(pk) for pk in set(value)]).values()


class UserField(forms.ChoiceField):
    u"""Form field class for the selection of a single user.  This can be the
    new currently responsible person for a sample, or the person you wish to
    send “My Samples” to.
    """

    def set_users(self, additional_user=None):
        u"""Set the user list shown in the widget.  You *must* call this method
        (or `set_users_without`) in the constructor of the form in which you
        use this field, otherwise the selection box will remain emtpy.  The
        selection list will consist of all currently active users, plus the
        given additional user if any.

        :Parameters:
          - `additional_user`: Optional additional user to be included into the
            list.  Typically, it is the current user for the process to be
            edited.

        :type additional_user: ``django.contrib.auth.models.User``
        """
        self.choices = [(u"", 9*u"-")]
        users = set(django.contrib.auth.models.User.objects.filter(is_active=True, is_staff=False))
        if additional_user:
            users.add(additional_user)
        users = sorted(users, key=lambda user: user.last_name if user.last_name else user.username)
        self.choices.extend((user.pk, get_really_full_name(user)) for user in users)

    def set_users_without(self, excluded_user):
        u"""Set the user list shown in the widget.  You *must* call this method
        (or `set_users`) in the constructor of the form in which you use this
        field, otherwise the selection box will remain emtpy.  The selection
        list will consist of all currently active users, minus the given user.

        :Parameters:
          - `excluded_user`: User to be excluded from the list.  Typically, it
            is the currently logged-in user.

        :type excluded_user: ``django.contrib.auth.models.User``
        """
        self.choices = [(u"", 9*u"-")]
        users = set(django.contrib.auth.models.User.objects.filter(is_active=True, is_staff=False))
        users.remove(excluded_user)
        users = sorted(users, key=lambda user: user.last_name if user.last_name else user.username)
        self.choices.extend((user.pk, get_really_full_name(user)) for user in users)

    def clean(self, value):
        value = super(UserField, self).clean(value)
        if value:
            return django.contrib.auth.models.User.objects.get(pk=int(value))


class MultipleUsersField(forms.MultipleChoiceField):
    u"""Form field class for the selection of zero or more users.  This can be
    the set of members for a particular topic.
    """

    def set_users(self, additional_users=[]):
        u"""Set the user list shown in the widget.  You *must* call this method
        in the constructor of the form in which you use this field, otherwise
        the selection box will remain emtpy.  The selection list will consist
        of all currently active users, plus the given additional users if any.

        :Parameters:
          - `additional_users`: Optional additional users to be included into
            the list.  Typically, it is the current users for the topic whose
            memberships are to be changed.

        :type additional_users: iterable of ``django.contrib.auth.models.User``
        """
        users = set(django.contrib.auth.models.User.objects.filter(is_active=True, is_staff=False))
        users |= set(additional_users)
        users = sorted(users, key=lambda user: user.last_name if user.last_name else user.username)
        self.choices = [(user.pk, get_really_full_name(user)) for user in users]
        if not self.choices:
            self.choices = ((u"", 9*u"-"),)

    def clean(self, value):
        if value == [u""]:
            value = []
        value = super(MultipleUsersField, self).clean(value)
        return django.contrib.auth.models.User.objects.in_bulk([int(pk) for pk in set(value)]).values()


class TopicField(forms.ChoiceField):
    u"""Form field class for the selection of a single topic.  This can be
    the topic for a sample or a sample series, for example.
    """

    def set_topics(self, user, additional_topic=None):
        u"""Set the topic list shown in the widget.  You *must* call this
        method in the constructor of the form in which you use this field,
        otherwise the selection box will remain emtpy.  The selection list will
        consist of all currently active topics, plus the given additional
        topic if any.  The “currently active topics” are all topics with
        at least one active user amongst its members.

        :Parameters:
          - `user`: the currently logged-in user
          - `additional_topic`: Optional additional topic to be included
            into the list.  Typically, it is the current topic of the sample,
            for example.

        :type user: ``django.contrib.auth.models.User``
        :type additional_topic: ``chantal_common.models.Topic``
        """
        self.choices = [(u"", 9*u"-")]
        all_topics = Topic.objects.filter(members__is_active=True).distinct()
        user_topics = user.topics.all()
        topics = \
            set(topic for topic in all_topics if not topic.confidential or topic in user_topics)
        if additional_topic:
            topics.add(additional_topic)
        topics = sorted(topics, key=lambda topic: topic.name)
        self.choices.extend((topic.pk, unicode(topic)) for topic in topics)

    def clean(self, value):
        value = super(TopicField, self).clean(value)
        if value:
            return Topic.objects.get(pk=int(value))


class FixedOperatorField(forms.ChoiceField):
    u"""Form field class for the *fixed* selection of a single user.  This is
    intended for edit-process views when the operator must be the currently
    logged-in user, or the previous operator.  In other words, it must be
    impossible to change it.  Then, you can use this form field for the
    operator, and hide the field from display by ``style="display: none"`` in
    the HTML template.

    Important: This field must *always* be made required!
    """

    def set_operator(self, operator, is_staff=False):
        u"""Set the user list shown in the widget.  You *must* call this method
        in the constructor of the form in which you use this field, otherwise
        the selection box will remain emtpy.  The selection list will consist
        only of the given operator, with no other choice (not even the empty
        field).

        :Parameters:
          - `operator`: operator to be included into the list.  Typically, it
            is the current user.
          - `is_staff`: whether the currently logged-in user is an
            administrator

        :type operator: ``django.contrib.auth.models.User``
        :type is_staff: bool
        """
        if not is_staff:
            self.choices = ((operator.pk, operator.username),)
        else:
            self.choices = django.contrib.auth.models.User.objects.values_list("pk", "username")

    def clean(self, value):
        value = super(FixedOperatorField, self).clean(value)
        return django.contrib.auth.models.User.objects.get(pk=int(value))


class OperatorField(forms.ChoiceField):
    u"""Form field class for the selection of a single operator.  This is
    intended for edit-process views when the operator must be the currently
    logged-in user, or the previous operator.  In other words, it must be
    impossible to change it.  Then, you can use this form field for the
    operator, and hide the field from display by ``style="display: none"`` in
    the HTML template.

    If you want to use this field, do the following things::

        1. This field must be made required

        2. If the user is not staff, make the possible choices of the external
           operator field empty.

        3. Assure in your ``clean()`` method that non-staff doesn't submit an
           external operator.  In the same method, say if the
           ``external_operator`` field was empty::

               self.cleaned_data["external_operator"] = \
                   self.fields["operator"].external_operator

        4. In the template, show the external operator field only for staff.

    A good example is in ``substrate.py`` of the IPV adaption of Chantal.
    """

    def set_choices(self, user, old_process):
        u"""Set the operator list shown in the widget.  It combines selectable
        users and external operators.  You *must* call this method in the
        constructor of the form in which you use this field, otherwise the
        selection box will remain emtpy.  It works even for staff users, which
        can choose from *all* users and external operators (including inactive
        users such as “nobody”).

        :Parameters:
          - `user`: the currently logged-in user.
          - `old_process`: if the process is to be edited, the former instance
            of the process; otherwise, ``None``

        :type operator: ``django.contrib.auth.models.User``
        :type old_process: `models.Process`
        """
        self.user = user
        if user.is_staff:
            self.choices = django.contrib.auth.models.User.objects.values_list("pk", "username")
            external_operators = list(models.ExternalOperator.objects.all())
        else:
            if old_process:
                self.choices = [(old_process.operator.pk, old_process.operator.username)]
            else:
                self.choices = [(user.pk, user.username)]
            external_operators = list(user.external_contacts.all())
        self.initial = old_process.operator.pk if old_process else user.pk
        self.default_operator = old_process.operator if old_process else user
        if old_process and old_process.external_operator:
            if not old_process.external_operator in external_operators:
                external_operators.append(old_process.external_operator)
            self.initial = "extern-" + str(old_process.external_operator.pk)
        for external_operator in external_operators:
            self.choices.append(("extern-" + str(external_operator.pk), external_operator.name))

    def clean(self, value):
        u"""Return the selected operator.  Additionally, it sets the attribute
        `external_operator` if the user selected one (it sets it to ``None``
        otherwise).  If an external operator was selected, this routine returns
        the currently logged-in user.
        """
        value = super(OperatorField, self).clean(value)
        if value.startswith("extern-"):
            self.external_operator = models.ExternalOperator.objects.get(pk=int(value[7:]))
            return self.default_operator
        else:
            self.external_operator = None
            return django.contrib.auth.models.User.objects.get(pk=int(value))


# FixMe: This should be moved to chantal_ipv, because this special case is only
# necessary because samples may get renamed after depositions.  Maybe
# refactoring should be done because it is used for substrates, too.

class DepositionSamplesForm(forms.Form):
    u"""Form for the list selection of samples that took part in the
    deposition.  Depositions need a special form class for this because it must
    be disabled when editing an *existing* deposition.
    """
    _ = ugettext_lazy
    sample_list = MultipleSamplesField(label=_(u"Samples"))

    def __init__(self, user, preset_sample, deposition, data=None, **kwargs):
        u"""Class constructor.  Note that I have to distinguish clearly here
        between new and existing depositions.
        """
        samples = list(user.my_samples.all())
        if deposition:
            # If editing an existing deposition, always have an *unbound* form
            # so that the samples are set although sample selection is
            # "disabled" and thus never successful when submitting.  This is
            # necessary for depositions because they can change the name of
            # samples, and so changing the affected samples afterwards is a
            # source of big trouble.
            kwargs["initial"] = {"sample_list": deposition.samples.values_list("pk", flat=True)}
            super(DepositionSamplesForm, self).__init__(**kwargs)
            self.fields["sample_list"].widget.attrs["disabled"] = "disabled"
            samples.extend(deposition.samples.all())
        else:
            super(DepositionSamplesForm, self).__init__(data, **kwargs)
            if preset_sample:
                samples.append(preset_sample)
                self.fields["sample_list"].initial = [preset_sample.pk]
        self.fields["sample_list"].set_samples(samples, user)
        self.fields["sample_list"].widget.attrs.update({"size": "17", "style": "vertical-align: top"})


class RemoveFromMySamplesForm(forms.Form):
    u"""Form for the question whether the user wants to remove the samples
    from the “My Samples” list after the process.
    """
    _ = ugettext_lazy
    remove_from_my_samples = forms.BooleanField(label=_(u"Remove processed sample(s) from My Samples"),
                                                          required=False, initial=False)


time_pattern = re.compile(r"^\s*((?P<H>\d{1,3}):)?(?P<M>\d{1,2}):(?P<S>\d{1,2})\s*$")
u"""Standard regular expression pattern for time durations in Chantal:
HH:MM:SS, where hours can also be 3-digit and are optional."""
def clean_time_field(value):
    u"""General helper function for use in the ``clean_...`` methods in forms.
    It tests whether the time format is correct, and normalises the duration so
    that minutes and seconds are 2-digit, and leading zeros are eliminated from
    the hours.

    :Parameters:
      - `value`: the value input by the user.  Usually this is the result of a
        ``cleaned_data[...]`` call.

    :type value: str

    :Return:
      the normalised time

    :rtype: str

    :Exceptions:
      - `ValidationError`: if the value given was not a valid duration time.
    """
    if not value:
        return ""
    match = time_pattern.match(value)
    if not match:
        raise ValidationError(_(u"Time must be given in the form HH:MM:SS."))
    hours, minutes, seconds = match.group("H"), int(match.group("M")), int(match.group("S"))
    hours = int(hours) if hours is not None else 0
    if minutes >= 60 or seconds >= 60:
        raise ValidationError(_(u"Minutes and seconds must be smaller than 60."))
    if not hours:
        return "{0}:{1:02}".format(minutes, seconds)
    else:
        return "{0}:{1:02}:{2:02}".format(hours, minutes, seconds)


def clean_date_field(value):
    u"""General helper function for use in the ``clean_...`` methods in forms.
    It tests whether the given date is not in the future.
    It is a small an trivial test, but it is used in the most layer forms.

    The test of correct input is performed by the `date field` itself.

    :Parameter:
        - `value`: the value input by the user.  Usually this is the result of a
        ``cleaned_data[...]`` call.

    :type value: datetime.date object

    :Return:
        the original ``value`` (unchanged)

    :rtype: datetime.date object

    :Exception:
        -`ValidationError`: if the specified date lies in the future.
    """
    if value > datetime.date.today():
        raise ValidationError(_(u"The date must not be in the future."))
    return value


quantity_pattern = re.compile(ur"^\s*(?P<number>[-+]?\d+(\.\d+)?(e[-+]?\d+)?)\s*(?P<unit>[a-uA-Zµ]+)\s*$")
u"""Regular expression pattern for valid physical quantities."""
def clean_quantity_field(value, units):
    u"""General helper function for use in the ``clean_...`` methods in forms.
    It tests whether the format of the physical quantity is correct, and
    normalises it so that it only contains decimal points (no commas), a proper
    »µ«, and exactly one space sign between value and unit.

    :Parameters:
      - `value`: the value input by the user.  Usually this is the result of a
        ``cleaned_data[...]`` call.

    :type value: str

    :Return:
      the normalised physical quantity

    :rtype: str

    :Exceptions:
      - `ValidationError`: if the value given was not a valid physical
        quantity.
    """
    if not value:
        return ""
    value = unicode(value).replace(",", ".").replace(u"μ", u"µ")  # No, these µ are not the same!
    match = quantity_pattern.match(value)
    if not match:
        raise ValidationError(_(u"Must be a physical quantity with number and unit."))
    original_unit = match.group("unit").lower()
    for unit in units:
        if unit.lower() == original_unit.lower():
            break
    else:
        raise ValidationError(_(u"The unit is invalid.  Valid units are: {units}").format(units=", ".join(units)))
    return match.group("number") + " " + unit


deposition_number_pattern = re.compile("\d\d[A-Z]-\d{3,4}$")
def clean_deposition_number_field(value, letter):
    u"""Checks wheter a deposition number given by the user in a form is a
    valid one.  Note that it does not check whether a deposition with this
    number already exists in the database.  It just checks the syntax of the
    number.

    :Parameters:
      - `value`: the deposition number entered by the user
      - `letter`: the single uppercase letter denoting the deposition system

    :type value: unicode
    :type letter: unicode

    :Return:
      the original ``value`` (unchanged)

    :rtype: unicode

    :Exceptions:
      - `ValidationError`: if the deposition number was not a valid deposition
        number
    """
    if not deposition_number_pattern.match(value):
        # Translation hint: “YY” is year, “L” is letter, and “NNN” is number
        raise ValidationError(_(u"Invalid deposition number.  It must be of the form YYL-NNN."))
    if value[2] != letter:
        raise ValidationError(_(u"The deposition letter must be an uppercase “{letter}”.").format(letter))
    return value


def collect_subform_indices(post_data, subform_key="number", prefix=u""):
    u"""Find all indices of subforms of a certain type (e.g. layers) and return
    them so that the objects (e.g. layers) have a sensible order (e.g. sorted
    by layer number).  This is necessary because indices are used as form
    prefixes and cannot be changed easily, even if the layers are rearranged,
    duplicated, or deleted.  By using this function, the view has the chance to
    have everything in proper order nevertheless.

    :Parameters:
      - `post_data`: the result from ``request.POST``
      - `subform_key`: the fieldname in the forms that is used for ordering.
        Defaults to ``number``.
      - `prefix`: an additional prefix to prepend to every form field name
        (even before the index).  (Is almost never used.)

    :type post_data: ``QueryDict``

    :Return:
      list with all found indices having this form prefix and key.
      Their order is so that the respective values for that key are ascending.

    :rtype: list of int
    """
    subform_name_pattern = re.compile(re.escape(prefix) + ur"(?P<index>\d+)(_\d+)*-(?P<key>.+)")
    values = {}
    for key, value in post_data.iteritems():
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


level0_pattern = re.compile(ur"(?P<level0_index>\d+)-(?P<id>.+)")
level1_pattern = re.compile(ur"(?P<level0_index>\d+)_(?P<level1_index>\d+)-(?P<id>.+)")
def normalize_prefixes(post_data):
    u"""Manipulates the prefixes of POST data keys for bringing them in
    consecutive order.  It only works for at most two-level numeric prefixes,
    which is sufficient for most purposes.  For example, in the 6-chamber
    deposition view, top-level is the layer index, and second-level is the
    channel index.

    The format of prefixes must be "1" for layers, and "1_1" for channels.

    By deleting layers or channels, the indeces might be sparse, so this
    routine re-indexes everything so that the gaps are filled.

    :Parameters:
      - `post_data`: the POST data as returned by ``request.POST``.

    :type post_data: ``QueryDict``

    :Return:
      the normalised POST data, the number of top-level prefixes, and a list
      with the number of all second-level prefixes.

    :rtype: ``QueryDict``, int, list of int
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
            digested_post_data[(level0_index, match.group("id"))] = post_data.getlist(key)
        else:
            match = level1_pattern.match(key)
            if match:
                level0_index, level1_index = int(match.group("level0_index")), int(match.group("level1_index"))
                level1_indices.setdefault(level0_index, set()).add(level1_index)
                digested_post_data[(level1_index, level0_index, match.group("id"))] = post_data.getlist(key)
            else:
                digested_post_data[key] = post_data.getlist(key)
    level0_indices = sorted(level0_indices)
    normalization_necessary = level0_indices and level0_indices[-1] != len(level0_indices) - 1
    for key, value in level1_indices.iteritems():
        level1_indices[key] = sorted(value)
        normalization_necessary = normalization_necessary or (
            level1_indices[key] and level1_indices[key][-1] != len(level1_indices[key]) - 1)
    if normalization_necessary:
        new_post_data = QueryDict("").copy()
        for key, value in digested_post_data.iteritems():
            if isinstance(key, basestring):
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
    u"""Determine all samples from ``samples`` which are already dead at the
    given ``timestamp``.

    :Parameters:
      - `samples`: the samples to be tested
      - `timestamp`: the timestamp for which the dead samples should be found

    :type samples: list of `models.Sample`
    :type timestamp: ``datetime.datetime``

    :Return:
      set of all samples which are dead at ``timestamp``

    :rtype: set of `models.Sample`
    """
    result = set()
    for sample in samples:
        death_timestamps = \
            sample.processes.filter(sampledeath__timestamp__isnull=False).values_list("timestamp", flat=True)
        assert len(death_timestamps) <= 1
        if death_timestamps and death_timestamps[0] <= timestamp:
            result.add(sample)
    return result

def test_for_datafile(filename, root_dir):
    u"""Test whether a certain file is openable by Chantal.

    :Parameters:
    - `filename`: Path to the file to be tested.  Note that this is a
    relative path: The `root_dir` is implicitly prepended to the
    filename.

    :type filename: str
    """
    if filename:
        try:
            open(os.path.join(root_dir, filename))
        except IOError:
            raise ValidationError(_(u"Couldn't open {filename}.".format(filename=filename)))
