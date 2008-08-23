#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re, string, copy, datetime
from django.forms.util import ErrorList, ValidationError
from django.http import HttpResponseRedirect, QueryDict, Http404
from django.utils.translation import ugettext as _
from functools import update_wrapper
from chantal.samples import models
from django.forms import ModelForm, ModelChoiceField
from django.template import Context, loader, RequestContext
from django.shortcuts import render_to_response

class DataModelForm(ModelForm):
    def uncleaned_data(self, fieldname):
        return self.data.get(self.prefix + "-" + fieldname)

class OperatorChoiceField(ModelChoiceField):
    def label_from_instance(self, operator):
        return operator.get_full_name() or unicode(operator)

time_pattern = re.compile(r"^\s*((?P<H>\d{1,3}):)?(?P<M>\d{1,2}):(?P<S>\d{1,2})\s*$")
def clean_time_field(value):
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
def clean_quantity_field(value, units):
    if not value:
        return ""
    value = unicode(value).replace(",", ".").replace(u"μ", u"µ")
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
    
def int_or_zero(number):
    try:
        return int(number)
    except ValueError:
        return 0

def append_error(form, fieldname, error_message):
    form._errors.setdefault(fieldname, ErrorList()).append(error_message)

class _PermissionCheck(object):
    def __init__(self, original_view_function, permissions):
        self.original_view_function = original_view_function
        try:
            self.permissions = set("samples." + permission for permission in permissions)
        except TypeError:
            self.permissions = set(["samples." + permissions])
        update_wrapper(self, original_view_function)
    def __call__(self, request, *args, **kwargs):
        if any(request.user.has_perm(permission) for permission in self.permissions):
            return self.original_view_function(request, *args, **kwargs)
        return HttpResponseRedirect("permission_error")
    
def check_permission(permissions):
    # If more than one permission is given, any of them would unlock the view.
    def decorate(original_view_function):
        return _PermissionCheck(original_view_function, permissions)
    return decorate

def get_sample(sample_name):
    try:
        sample = models.Sample.objects.get(name=sample_name)
    except models.Sample.DoesNotExist:
        aliases = [alias.sample for alias in models.SampleAlias.objects.filter(name=sample_name)]
        if len(aliases) == 1:
            return aliases[0]
        return aliases or None
    else:
        return sample

def does_sample_exist(sample_name):
    return (models.Sample.objects.filter(name=sample_name).count() or
            models.SampleAlias.objects.filter(name=sample_name).count())

def normalize_sample_name(sample_name):
    if models.Sample.objects.filter(name=sample_name).count():
        return sample_name
    try:
        sample_alias = models.SampleAlias.objects.get(name=sample_name)
    except models.SampleAlias.DoesNotExist:
        return
    else:
        return sample_alias.sample.name

level0_pattern = re.compile(ur"(?P<level0_index>\d+)-(?P<id>.+)")
level1_pattern = re.compile(ur"(?P<level0_index>\d+)_(?P<level1_index>\d+)-(?P<id>.+)")
def normalize_prefixes(post_data):
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

def get_my_layers(user_details, deposition_model, required=True):
    if not user_details.my_layers:
        return []
    items = [item.split(":", 1) for item in user_details.my_layers.split(",")]
    items = [(item[0].strip(),) + tuple(item[1].rsplit("-", 1)) for item in items]
    items = [(item[0], int(item[1]), int(item[2])) for item in items]
    fitting_items = [] if required else [(u"", u"---------")]
    for nickname, deposition_id, layer_number in items:
        try:
            deposition = deposition_model.objects.get(pk=deposition_id)
        except deposition_model.DoesNotExist:
            continue
        try:
            layer = deposition.layers.get(number=layer_number)
        except:
            continue
        fitting_items.append((u"%d-%d" % (deposition_id, layer_number), nickname))
    return fitting_items

def has_permission_for_sample(user, sample):
    return user.has_perm("samples.view_sample") or sample.group in user.groups.all() \
        or sample.currently_responsible_person == request.user

def name2url(name):
    return name.replace("/", "!")

def url2name(url):
    return url.replace("!", "/")

class ProcessContext(object):
    def __init__(self, user, original_sample=None, process=None):
        self.original_sample = self.current_sample = original_sample
        self.user = user
        self.__process = self.cutoff_timestamp = self.html_body = None
        if process:
            self.process = process
    def __set_process(self, process):
        self.__process = process.find_actual_instance()
    process = property(lambda self: self.__process, __set_process)
    def split(self, split):
        result = copy.copy(self)
        result.current_sample = split.parent
        result.cutoff_timestamp = split.timestamp
        return result
    def get_template_context(self):
        context_dict = {"process": self.__process}
        if hasattr(self.__process, "get_additional_template_context"):
            context_dict.update(self.__process.get_additional_template_context(self))
        return context_dict
    def get_processes(self):
        if self.cutoff_timestamp is None:
            return self.current_sample.processes.all()
        else:
            return self.current_sample.processes.filter(timestamp__lte=self.cutoff_timestamp)
    @staticmethod
    def camel_case_to_underscores(name):
        result = []
        for i, character in enumerate(name):
            if i == 0:
                result.append(character.lower())
            elif character in string.ascii_uppercase:
                result.extend(("_", character.lower()))
            else:
                result.append(character)
        return "".join(result)
    def digest_process(self, process=None):
        if process:
            self.process = process
        template = loader.get_template("show_" + self.camel_case_to_underscores(self.__process.__class__.__name__) + ".html")
        name = unicode(self.__process._meta.verbose_name)
        template_context = self.get_template_context()
        context_dict = {"name": name[0].upper()+name[1:], "operator": self.__process.operator,
                        "timestamp": self.__process.timestamp,
                        "html_body": template.render(Context(template_context))}
        for key in ["edit_url", "duplicate_url"]:
            if key in template_context:
                context_dict[key] = template_context[key]
        return context_dict
    def collect_processes(self):
        processes = []
        split_origin = self.current_sample.split_origin
        if split_origin:
            processes.extend(self.split(split_origin).collect_processes())
        for process in self.get_processes():
            processes.append(self.digest_process(process))
        return processes

deposition_number_pattern = re.compile(ur"\d{3,4}")
def get_next_deposition_number(letter):
    prefix = ur"%02d%s" % (datetime.date.today().year % 100, letter)
    pattern_string = ur"^%s[0-9]{3,4}" % prefix
    deposition_dicts = models.Deposition.objects.filter(number__regex=pattern_string).values("number")
    numbers = [int(deposition_number_pattern.match(deposition_dict["number"][3:]).group(0))
               for deposition_dict in deposition_dicts]
    return prefix + u"%03d" % (max(numbers + [0]) + 1)

def lookup_sample(sample_name, request):
    sample_name = url2name(sample_name)
    sample = get_sample(sample_name)
    if not sample:
        raise Http404(_(u"Sample %s could not be found (neither as an alias).") % sample_name)
    if isinstance(sample, list):
        return None, render_to_response(
            "disambiguation.html", {"alias": sample_name, "samples": sample, "title": _("Ambiguous sample name")},
            context_instance=RequestContext(request))
    if not has_permission_for_sample(request.user, sample):
        return None, HttpResponseRedirect("permission_error")
    return sample, None
