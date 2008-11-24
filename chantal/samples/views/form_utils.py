#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Helper classes and function which have something to do with form generation
and validation.
"""

import re, datetime
from django.forms.util import ErrorList, ValidationError
from django.http import QueryDict
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms import ModelForm, ModelChoiceField
import django.forms as forms
import django.contrib.auth.models
from chantal.samples import models
from chantal.samples.views import utils

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
        return []
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
        fitting_items.append((u"%d-%d" % (deposition_id, layer_number), nickname))
    return fitting_items

class AddLayersForm(forms.Form):
    _ = ugettext_lazy
    number_of_layers_to_add = forms.IntegerField(label=_(u"Number of layers to be added"), min_value=0, required=False)
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
        if models.Initials.objects.filter(initials=initials).count():
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
                if models.Initials.objects.filter(user=self.person).count() == 0:
                    models.Initials.objects.create(initials=initials, user=self.person)
            else:
                if models.Initials.objects.filter(external_operator=self.person).count() == 0:
                    models.Initials.objects.create(initials=initials, external_operator=self.person)

class EditDescriptionForm(forms.Form):
    _ = ugettext_lazy
    description = forms.CharField(label=_(u"Description of edit"), widget=forms.Textarea)
    important = forms.BooleanField(label=_(u"Important edit"), required=False)
    def __init__(self, *args, **kwargs):
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
    def set_samples(self, samples):
        u"""Set the sample list shown in the widget.  You *must* call this
        method in the constructor of the form in which you use this field,
        otherwise the selection box will remain emtpy.

        :Parameters:
          - `samples`: Samples to be included into the list.  Typically, these
            are the current user's “My Samples”, plus the samples that were
            already connected with the deposition or measurement when you edit
            it.

        :type samples: list of `models.Sample`
        """
        groups, groupless_samples = utils.build_structured_sample_list(samples)
        self.choices = [(sample.pk, unicode(sample)) for sample in groupless_samples]
        for group in groups:
            seriesless_samples = [(sample.pk, unicode(sample)) for sample in group.samples]
            self.choices.append((group.group.name, seriesless_samples))
            for series in group.sample_series:
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
        users = set(django.contrib.auth.models.User.objects.filter(is_active=True).all())
        if additional_user:
            users.add(additional_user)
        users = sorted(users, key=lambda user: user.last_name if user.last_name else user.username)
        self.choices.extend((user.pk, utils.get_really_full_name(user)) for user in users)
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
        users = set(django.contrib.auth.models.User.objects.filter(is_active=True).all())
        users.remove(excluded_user)
        users = sorted(users, key=lambda user: user.last_name if user.last_name else user.username)
        self.choices.extend((user.pk, utils.get_really_full_name(user)) for user in users)
    def clean(self, value):
        value = super(UserField, self).clean(value)
        if value:
            return django.contrib.auth.models.User.objects.get(pk=int(value))

class MultipleUsersField(forms.MultipleChoiceField):
    u"""Form field class for the selection of zero or more users.  This can be
    the set of members for a particular group.
    """
    def set_users(self, additional_users=[]):
        u"""Set the user list shown in the widget.  You *must* call this method
        in the constructor of the form in which you use this field, otherwise
        the selection box will remain emtpy.  The selection list will consist
        of all currently active users, plus the given additional users if any.

        :Parameters:
          - `additional_users`: Optional additional users to be included into
            the list.  Typically, it is the current users for the group whose
            memberships are to be changed.

        :type additional_users: iterable of ``django.contrib.auth.models.User``
        """
        users = set(django.contrib.auth.models.User.objects.filter(is_active=True).all())
        users |= set(additional_users)
        users = sorted(users, key=lambda user: user.last_name if user.last_name else user.username)
        self.choices = [(user.pk, utils.get_really_full_name(user)) for user in users]
        if not self.choices:
            self.choices = ((u"", 9*u"-"),)
    def clean(self, value):
        if value == [u""]:
            value = []
        value = super(MultipleUsersField, self).clean(value)
        return django.contrib.auth.models.User.objects.in_bulk([int(pk) for pk in set(value)]).values()

class GroupField(forms.ChoiceField):
    u"""Form field class for the selection of a single group.  This can be the
    group for a sample or a sample series, for example.
    """
    def set_groups(self, additional_group=None):
        u"""Set the group list shown in the widget.  You *must* call this
        method in the constructor of the form in which you use this field,
        otherwise the selection box will remain emtpy.  The selection list will
        consist of all currently active groups, plus the given additional group
        if any.  The “currently active groups” are all groups with at least one
        active user amongst its members.

        :Parameters:
          - `additional_group`: Optional additional group to be included into
            the list.  Typically, it is the current group of the sample, for
            example.

        :type additional_group: ``django.contrib.auth.models.Group``
        """
        self.choices = [(u"", 9*u"-")]
        groups = set(django.contrib.auth.models.Group.objects.filter(user__is_active=True).all())
        if additional_group:
            groups.add(additional_group)
        groups = sorted(groups, key=lambda group: group.name)
        self.choices.extend((group.pk, unicode(group)) for group in groups)
    def clean(self, value):
        value = super(GroupField, self).clean(value)
        if value:
            return django.contrib.auth.models.Group.objects.get(pk=int(value))

class FixedOperatorField(forms.ChoiceField):
    u"""Form field class for the *fixed* selection of a single user.  This is
    intended for edit-process views when the operator must be the currently
    logged-in user, or the previous operator.  In other words, it must be
    impossible to change it.  Then, you can use this form field for the
    operator, and hide the field from display by ``style="display: none"`` in
    the HTML template.

    Important: This field must *always* be made required!
    """
    def set_operator(self, operator):
        u"""Set the user list shown in the widget.  You *must* call this method
        in the constructor of the form in which you use this field, otherwise
        the selection box will remain emtpy.  The selection list will consist
        only of the given operator, with no other choice (not even the empty
        field).

        :Parameters:
          - `operator`: operator to be included into the list.  Typically, it
            is the current user.

        :type operator: ``django.contrib.auth.models.User``
        """
        self.choices = ((operator.pk, unicode(operator)),)
    def clean(self, value):
        value = super(FixedOperatorField, self).clean(value)
        return django.contrib.auth.models.User.objects.get(pk=int(value))

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
        return "%d:%02d" % (minutes, seconds)
    else:
        return "%d:%02d:%02d" % (hours, minutes, seconds)

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
        raise ValidationError(_(u"The unit is invalid.  Valid units are: %s")%", ".join(units))
    return match.group("number") + " " + unit

deposition_number_pattern = re.compile("\d\d[A-Za-z]-\d{3,4}$")
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
        raise ValidationError(_(u"Invalid deposition number.  It must be of the form YYL-NNN."))
    if value[2] != letter:
        raise ValidationError(_(u"The deposition letter must be an uppercase “%s”.") % letter)
    return value

def append_error(form, error_message, fieldname="__all__"):
    u"""This function is called if a validation error is found in form data
    which cannot be found by the ``is_valid`` method itself.  The reason is
    very simple: For many types of invalid data, you must take other forms in
    the same view into account.

    See, for example, `split_after_deposition.is_referentially_valid`.

    :Parameters:
      - `form`: the form to which the erroneous field belongs
      - `error_message`: the message to be presented to the user
      - `fieldname`: the name of the field that triggered the validation
        error.  It is optional, and if not given, the error is considered an
        error of the form as a whole.

    :type form: ``forms.Form`` or ``forms.ModelForm``.
    :type fieldname: str
    :type error_message: unicode
    """
    form.is_valid()
    form._errors.setdefault(fieldname, ErrorList()).append(error_message)

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
                new_post_data.setlist("%d-%s" % (level0_indices.index(key[0]), key[1]), value)
            else:
                new_level0_index = level0_indices.index(key[1])
                new_post_data.setlist("%d_%d-%s" % (new_level0_index, level1_indices[key[1]].index(key[0]), key[2]), value)
    else:
        new_post_data = post_data
    return new_post_data, len(level0_indices), [len(level1_indices[i]) for i in level0_indices]

dangerous_markup_pattern = re.compile(r"([^\\]|\A)!\[|[\n\r][-=]")
def check_markdown(text):
    u"""Checks whether the Markdown input by the user contains only permitted
    syntax elements.  I forbid images and headings so far.

    :Parameters:
      - `text`: the Markdown input to be checked

    :Exceptions:
      - `ValidationError`: if the ``text`` contained forbidden syntax
        elements.
    """
    if dangerous_markup_pattern.search(text):
        raise ValidationError(_(u"You mustn't use image and headings syntax in Markdown markup."))

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
