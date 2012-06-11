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


"""Collection of tags and filters that I found useful for the IEK-PV extension
of Chantal.
"""

from __future__ import division, absolute_import, unicode_literals

import os.path
from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from chantal_institute.views import form_utils
from chantal_institute import settings, models, mfc_calibrations
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
def three_digits(number):
    """Filter for padding an integer with zeros so that it has at least three
    digits.
    """
    return mark_safe(form_utils.three_digits(number))

@register.filter
def four_digits(number):
    """Filter for padding an integer with zeros so that it has at least four
    digits.
    """
    return mark_safe("{0:04}".format(number))

@register.filter
def calculate_silane_concentration(value):
    """Filter for calculating the silane concentration for a
    deposition layer from the silane and hydrogen fluxes.
    """
    if value.sih4 == None or value.h2 == None:
        return None
    silane = float(value.sih4) * 0.6
    hydrogen = float(value.h2)
    if silane + hydrogen == 0:
        return None
    # Cheap way to cut the digits
    calculate_sc = lambda s, h: float("{0:5.2f}".format(100 * s / (s + h))) if s + h != 0 else "NaN"
    sc = calculate_sc(silane, hydrogen)
    try:
        silane_end = float(value.sih4_end) * 0.6 if value.sih4_end is not None else silane
        hydrogen_end = float(value.h2_end) if value.h2_end is not None else hydrogen
        sc_end = calculate_sc(silane_end, hydrogen_end)
    except AttributeError:
        return sc
    if value.sih4_end is None and value.h2_end is None:
        return sc
    else:
        return sc, sc_end


@register.filter
def cluster_tool_layer_type(value, type_="standard"):
    """Filter for detecting the layer type (hot-wire, PECVD, sputter) for
    cluster-tool layers.  ``type_`` may be ``"standard"``, ``"short"``, or
    ``"verbose"``."""
    if isinstance(value, (models.OldClusterToolHotWireLayer, models.NewClusterToolHotWireLayer)):
        return {"verbose": _("hot-wire"), "short": "HW"}.get(type_, "hot-wire")
    elif isinstance(value, (models.OldClusterToolPECVDLayer, models.NewClusterToolPECVDLayer)):
        return {"verbose": "PECVD", "short": "P"}.get(type_, "PECVD")
    elif isinstance(value, models.NewClusterToolSputterLayer):
        return {"verbose": _("sputter"), "short": "Sp"}.get(type_, "sputter")


@register.filter
def slot_may_be(value, mode):
    """Filter for detecting whether a sputter slot (used in the cluster tool
    II) may have a certain mode.  This is necessary to decide which field
    should be displayed in the edit view.
    """
    return mode in [item[0] for item in value.fields["mode"].choices]


@register.filter
def extract_channel(layer, gasname):
    """Filter for extracting a flow rate for a 6-chamber deposition layer.

    :Parameters:
      - `layer`: the layer instance
      - `fieldname`: the name of the gas flow attribute

    :type layer: ``samples.models.Layer``
    :type fieldname: unicode
    """
    for channel in layer.channels.all():
        if channel.gas == gasname:
            return channel.flow_rate
    return ""


@register.filter
def gradient(instance, fieldname):
    """Filter for extracting a gradient for a deposition layer.

    :Parameters:
      - `instance`: the layer instance
      - `fieldname`: the name of the gas flow attribute.  For example, if you
        give ``sih4`` here, both ``sih4`` and ``sih4_end`` must exist in the
        layer model.  Furthermore, ``sih4`` must be required, and ``sih4_end``
        may be ``None``.  This is the parameter after the filter

    :type instance: ``samples.models.Layer``
    :type fieldname: unicode
    """
    flow_rate = getattr(instance, fieldname)
    flow_rate_end = getattr(instance, "{0}_end".format(fieldname))
    if flow_rate_end is None:
        return flow_rate
    else:
        return flow_rate, flow_rate_end


@register.filter
def salutation(user):
    """Filter for getting the correct form of address for the institute
    member.  Except for Mr Rau, Mr Carius, and Mr Beyer, all members are called
    by their first name.
    """
    if user.username in ["u.rau", "r.carius", "w.beyer"]:
        return _("Mr {lastname}").format(lastname=user.last_name)
    else:
        return user.first_name or user.username


@register.filter
@stringfilter
def basename(filepath):
    return os.path.basename(filepath)


@register.filter
def sputter_mode(layer):
    if isinstance(layer, models.NewClusterToolSputterLayer):
        return " + ".join(slot.get_mode_display() for slot in layer.slots.all() if slot.mode)


@register.filter
def sputter_target(layer):
    if isinstance(layer, models.NewClusterToolSputterLayer):
        return " + ".join(slot.get_target_display() for slot in layer.slots.all() if slot.target)


@register.filter
def was_dynamic_sputtering(sputter_characterization):
    if sputter_characterization.large_sputter_deposition and sputter_characterization.large_sputter_deposition:
        layer = sputter_characterization.large_sputter_deposition.layers.all()[0]
        return layer.feed_rate and layer.steps


@register.filter
def solarsimulator_color(measurement):
    """Returns the colour which is associated with the solarsimulator
    measurement.  The returned string is ready-to-be-used in CSS directives as
    a colour name.
    """
    return {"dark": "gray", "AM1.5": "inherited", "BG7": "lightblue", "OG590": "darkorange"}[measurement.irradiance]


@register.filter
def raman_color(measurement):
    """Returns the colour which is associated with the raman
    measurement.  The returned string is ready-to-be-used in CSS directives as
    a colour name.
    """
    return {"??": "", "413": "DarkOrchid", "488": "DarkTurquoise", "532": "Lime", "647": "Crimson", "752": "DarkRed"} \
        [measurement.excitation_wavelength]


@register.filter
def sort_cells(cells):
    """Sort solarsimulator cells smartly.
    """
    def sort_function(cell):
        try:
            return int(cell.position)
        except ValueError:
            return cell.position
    return sorted(cells, key=sort_function)


@register.filter
def fraction(value, fraction=0.8):
    return fraction * value


@register.simple_tag
def get_calibrate_gas_flow(layer, gas_attr_name, mfc_number):
    """Calibrates the gas flow rates for the lada deposition lab notebook.
    This method detects a gas flow gradient automatically, so you must only call this method
    for the start value.

    :Parameters:
      - `layer`: the layer instance
      - `gas_attr_name`: the name of the gas flow attribute. If the gas flow has a gradient,
      just give the attribute name of the start value. But the attribute name of the end value
      must end with ``_end``.
      - `mfc_number`: the number of the mass flow controller

    :type layer: ``chantal_institute.models.LADALayer``
    :type gas_attr_name: unicode
    :type mfc_number: int
    """
    if mfc_number:
        calibrations = mfc_calibrations.get_calibrations_from_datafile(settings.LADA_MFC_CALIBRATION_FILE_PATH, "lada")
        calibrations.sort(reverse=True)
        for calibration in calibrations:
            if layer.date > calibration.date:
                calibration_set = calibration
                break
        mfc = "{gas_name}_{mfc_number}".format(gas_name=gas_attr_name.split("_")[0] if "_" in gas_attr_name else gas_attr_name,
                                               mfc_number=mfc_number).lower()
        attribute_name = "additional_gas_flow" if gas_attr_name == "Ar" else gas_attr_name
        calibrated_gas_flow = "{0:5.2f}".format(calibration_set.get_real_flow(getattr(layer, attribute_name), mfc)) \
            if hasattr(layer, attribute_name) and getattr(layer, attribute_name) is not None else ""
        gas_attr_end_name = "{0}_end".format(gas_attr_name)
        calibrated_gas_flow_end = "–{0:5.2f}".format(calibration_set.get_real_flow(getattr(layer, gas_attr_end_name), mfc)) \
            if hasattr(layer, gas_attr_end_name) and getattr(layer, gas_attr_end_name) is not None else ""
        if not calibrated_gas_flow == "" and gas_attr_name not in ["ch4", "co2", "Ar"]:
            display_mfc = "MFC#{mfc_number}: ".format(mfc_number=mfc_number)
        else:
            display_mfc = ""
        return mark_safe("{display_mfc}{calibrated_gas}{calibrated_gas_end}".format(display_mfc=display_mfc,
                                                                                    calibrated_gas=calibrated_gas_flow,
                                                                                    calibrated_gas_end=calibrated_gas_flow_end))
    else:
        return ""


@register.filter
def depostion_time(time):
    if time:
        time_components = time.split(":")
        if len(time_components) == 2:
            minutes, seconds = time_components
            hours = 0
        else:
            hours, minutes, seconds = time_components
        return "{0}:{1:02}:{2:02}".format(int(hours), int(minutes), int(seconds))
    else:
        return "—"


@register.filter
def convert_thickness(process_instance):
    return "{0:0.02f}".format(models.LayerThicknessMeasurement.convert_thickness(process_instance.thickness, "nm", process_instance.unit))

