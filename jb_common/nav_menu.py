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


"""Functions and classes for building the main menu.
"""

from __future__ import absolute_import, unicode_literals

import collections


class MenuItem(object):

    def __init__(self, label, url="", icon_name=None, icon_url=None, icon_description=None, position="left", rule_before=False,
                 rule_after=False):
        self.label, self.url, self.icon_name, self.icon_url, self.icon_description, self.position, self.rule_before, \
            self.rule_after = label, url, icon_name, icon_url, icon_description, position, rule_before, rule_after
        self.sub_items = []

    def contains_icons(self):
        return any(item.icon_name or item.icon_url for item in self)

    def add(self, *args, **kwargs):
        new_item = MenuItem(*args, **kwargs)
        label = new_item.label
        for i, item in enumerate(self.sub_items):
            if item.label == label:
                self.sub_items[i] = new_item
                break
        else:
            self.sub_items.append(new_item)
        return new_item

    def get_or_create(self, item_or_label):
        label = item_or_label.label if isinstance(item_or_label, MenuItem) else item_or_label
        try:
            return self[label]
        except KeyError:
            new_item = item_or_label if isinstance(item_or_label, MenuItem) else MenuItem(item_or_label)
            self.sub_items.append(new_item)
            return new_item

    def prepend(self, items):
        if isinstance(items, (tuple, list)):
            labels = {item.label for item in items}
            self.sub_items = items + [item for item in self.sub_items if item.label not in labels]
        else:
            self.sub_items = [items] + [item for item in self.sub_items if item.label != items.label]

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.sub_items[key]
        else:
            for item in self.sub_items:
                if item.label == key:
                    return item
            else:
                raise KeyError(key)

    def __iter__(self):
        return self.sub_items.__iter__()
