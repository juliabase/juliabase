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

from __future__ import absolute_import
from django import forms


class SearchField(forms.Form):
    u"""
    """
    def __init__(self, *args, **kwargs):
        super(SearchField, self).__init__(*args, **kwargs)
        for field in args[1].keys():
            if args[1][field] == "string":
                self.fields[field] = forms.CharField(label=field, required=False)
            else:
                self.fields[field] = forms.IntegerField(label=field, required=False)

