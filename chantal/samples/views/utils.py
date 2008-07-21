#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from django.newforms.util import ErrorList, ValidationError
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from functools import update_wrapper

time_pattern = re.compile(r"^\s*((?P<H>\d{1,3}):)?(?P<M>\d{1,2}):(?P<S>\d{1,2})\s*$")
def clean_time_field(value):
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
        raise ValidationError(_("Must be a physical quantity with number and unit."))
    original_unit = match.group("unit").lower()
    for unit in units:
        if unit.lower() == original_unit.lower():
            break
    else:
        raise ValidationError(_("The unit is invalid.  Valid units are: %s")%", ".join(units))
    return match.group("number") + " " + unit
    
def int_or_zero(number):
    try:
        return int(number)
    except ValueError:
        return 0

def prefix_dict(dictionary, prefix):
    return dict([(prefix+"-"+key, dictionary[key]) for key in dictionary])

def append_error(form, fieldname, error_message):
    form._errors.setdefault(fieldname, ErrorList()).append(error_message)

class _PermissionCheck(object):
    def __init__(self, original_view_function, permission):
        self.original_view_function, self.permission = original_view_function, "samples."+permission
        update_wrapper(self, original_view_function)
    def __call__(self, request, *args, **kwargs):
        if self.permission not in request.user.get_all_permissions():
            return HttpResponseRedirect("permission_error")
        return self.original_view_function(request, *args, **kwargs)
    
def check_permission(permission):
    def decorate(original_view_function):
        return _PermissionCheck(original_view_function, permission)
    return decorate
