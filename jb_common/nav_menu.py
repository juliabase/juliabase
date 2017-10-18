#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
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


"""Functions and classes for building the main menu.
"""

import collections


class MenuItem(object):
    """Class which represents one main menu item and – if available – its subitems
    in the instance attribute ``sub_items`` (a list of `MenuItem`).  This
    yields a nested data structure which may be interpreted to create a main
    menu.  It is created by the ``build_menu`` methods of the ``AppConfig``s of
    the apps.  They are called in the reverse order of ``INSTALLED_APPS``.
    """

    def __init__(self, label, url="", icon_name=None, icon_url=None, icon_description=None, position="left"):
        """
        :param label: the translated menu label
        :param url: the URL this menu item directs to
        :param icon_name: symbolic name of the icon to be used; you may *either*
          use this *or* the ``icon_url``/``icon_description`` combination
        :param icon_url: URL path to the icon
        :param icon_description: content of the "``alt``" attribute of the
          ``<img>`` tag of the icon
        :param position: the position of the menu, e.g. left-flushed or
          right-flushed

        :type label: unicode
        :type url: str
        :type icon_name: unicode
        :type icon_url: str
        :type icon_description: unicode
        :type position: str
        """
        self.label, self.url, self.icon_name, self.icon_url, self.icon_description, self.position = \
                    label, url, icon_name, icon_url, icon_description, position
        self.sub_items = []

    def contains_icons(self):
        """Returns whether the menu contains a direct subitem with an icon.

        :return:
          whether the menu contains an item with an icon

        :rtype: bool
        """
        return any(item.icon_name or item.icon_url for item in self)

    def add(self, *args, **kwargs):
        """Adds a subitem to the menu.  If a subitem with the label already exists, it
        is replaced at the same position.  All parameters for this method are
        passed to the constructor of `MenuItem` to create the new item.

        :return:
          the newly created and inserted item

        :rtype: `MenuItem`
        """
        new_item = MenuItem(*args, **kwargs)
        label = new_item.label
        for i, item in enumerate(self.sub_items):
            if item.label == label:
                self.sub_items[i] = new_item
                break
        else:
            self.sub_items.append(new_item)
        return new_item

    def add_separator(self):
        """Appends a item separator to the list of subitems.  This may result in a
        horizontal rule in the output.
        """
        self.sub_items.append(MenuSeparator())

    def add_heading(self, label):
        """Appends a heading to the list of subitems.

        :param label: the text of the heading

        :type label: unicode
        """
        self.sub_items.append(MenuHeading(label))

    def get_or_create(self, item_or_label):
        """Retrieves a menu item from this menu with the given label.  If it doesn't
        exist yet, it is created.  This comes in handy if an app wants to
        extend a menu that may haven been already created by another app.

        :param item_or_label: the item to be returned if an item with that
          label already exists in this menu.  Alternatively, only the label of
          it, if no other constructor parameters of `MenuItem` are needed.  The
          latter is senseful for top-level menus that have only subitems, but no
          URL or icon.

        :type item_or_label: `MenuItem` or unicode

        :return:
          the found item, or newly created and inserted item

        :rtype: `MenuItem`
        """
        label = item_or_label.label if isinstance(item_or_label, MenuItem) else item_or_label
        try:
            return self[label]
        except KeyError:
            new_item = item_or_label if isinstance(item_or_label, MenuItem) else MenuItem(item_or_label)
            self.sub_items.append(new_item)
            return new_item

    def prepend(self, items):
        """Prepends the given item(s) to the list of subitems.

        :param items: the item(s) to be prepended

        :type items: list of `MenuItem` or `MenuItem`
        """
        if isinstance(items, (tuple, list)):
            labels = {item.label for item in items}
            self.sub_items = items + [item for item in self.sub_items if item.label not in labels]
        else:
            self.sub_items = [items] + [item for item in self.sub_items if item.label != items.label]

    def insert_after(self, label, items, after_separator=False):
        """Inserts item(s) after an already existing item.  This item is
        identified by its label.  If it is not found, the item(s) are appended
        to the end of the menu.

        :param label: the label of the item after which should be inserted
        :param items: the item(s) to be inserted
        :param after_separator: whether separators after the found item should
           be skipped

        :type label: unicode
        :type items: list of `MenuItem` or `MenuItem`
        :type after_separator: bool
        """
        if not isinstance(items, (tuple, list)):
            items = [items]
        i = 0
        for i, item in enumerate(self.sub_items):
            if item.label == label:
                break
        i += 1
        if after_separator:
            while i < len(self.sub_items) and isinstance(self.sub_items[i], MenuSeparator):
                i += 1
        self.sub_items[i:i] = items

    def __getitem__(self, key):
        """Gets the subitem with the given key or index.
        """
        if isinstance(key, int):
            return self.sub_items[key]
        else:
            for item in self.sub_items:
                if item.label == key:
                    return item
            else:
                raise KeyError(key)

    def __delitem__(self, key):
        """Removes the subitem with the given key or index.
        """
        if isinstance(key, int):
            del self.sub_items[key]
        else:
            for i, item in enumerate(self.sub_items):
                if item.label == key:
                    del self.sub_items[i]
                    break
            else:
                raise KeyError(key)

    def __iter__(self):
        """Lets you iterate over the `MenuItem` by iterating over its subitems.
        """
        return self.sub_items.__iter__()

    def __len__(self):
        """Returns the number of subitems.
        """
        return len(self.sub_items)


class MenuSeparator(MenuItem):
    """Special `MenuItem` which results in a separator, usually a horizontal rule.
    All other attributes of `MenuItem` are ignored.
    """
    def __init__(self):
        super(MenuSeparator, self).__init__("")


class MenuHeading(MenuItem):
    """Special `MenuItem` which results in a heading within a dopdown menu.
    The label is the text of the heading.  All other attributes of `MenuItem`
    are ignored.
    """
    def __init__(self, label):
        super(MenuHeading, self).__init__(label)
