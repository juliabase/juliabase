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


"""Module with classes that are needed to build nested representations of the
data contain in a certain model instance.  Such tree-like representations are
used e.g. for the CSV export of model instances.
"""

from django.utils.functional import Promise


class DataNode:
    """Class for a node in a data tree intended to hold instance data.

    :ivar name: name of this node; must be the same for node whose items carry
      the same semantics

    :ivar descriptive_name: name which is used if this node is a row node in
      the final tree, as a row description in the very first column.

    :ivar items: list of Key–value structures with the actual data.

    :ivar children: the child nodes of this node in the three; for example,
      they may be the samples of a sample series

    :type name: str
    :type descriptive_name: str
    :type items: list of `DataItem`
    :type childen: list of `DataNode`
    """

    def __init__(self, instance, descriptive_name=""):
        """Class constructor.

        :param instance: The model instance whose data is extracted, or the name
            that should be used for this node.  If you pass an instance, the
            name is the *type* of the instance, e.g. “5-chamber deposition” or
            “sample”.
        :param descriptive_name: The “first column” name of the node.  It should
            be more concrete than just the type but it depends.  For samples
            for example, it is the sample's name.  By default, it is the type
            of the instance or the string you gave as ``instance``.

        :type instance: ``models.Model`` or str
        :type descriptive_name: str
        """
        if isinstance(instance, str):
            self.name = self.descriptive_name = instance
        else:
            self.name = str(instance._meta.verbose_name)
        self.descriptive_name = str(descriptive_name) or self.name
        self.items = []
        self.children = []

    def find_unambiguous_names(self, renaming_offset=1):
        """Make all names in the whole tree of this node instance
        unambiguous.  This is done by two means:

        1. If two sister nodes share the same name, a number like ``" #1"`` is
           appended.

        2. The names of the ancestor nodes are prepended, e.g. ``"5-chamber
           deposition, layer #2"``

        :param renaming_offset: number of the nesting levels still to be stepped
            down before disambiguation of the node names takes place.

        :type renaming_offset: int
        """
        names = [child.name for child in self.children]
        for i, child in enumerate(self.children):
            if renaming_offset < 1:
                if names.count(child.name) > 1:
                    process_index = names[:i].count(child.name) + 1
                    if process_index > 1:
                        child.name += " #{0}".format(process_index)
                if renaming_offset < 0:
                    child.name = self.name + ", " + child.name
            child.find_unambiguous_names(renaming_offset - 1)

    def complete_items_in_children(self, key_sets=None, item_cache=None):
        """Assures that all decendents of this node that have the same node
        name also have the same item keys.  This is interesting for kinds of
        nodes which don't have a strict set of items.  An example are result
        processes: The user is completely free which items he gives them.  This
        irritates ``build_column_group_list``: It takes the *first* node of a
        certain ``name`` (for example ``"Nice result"``) and transforms its
        items to table columns.

        But what if the second ``"Nice result"`` for the same sample has other
        items?  This shouldn't happen certainly, but it will.  Here, we add
        the missing items (with empty strings as value).

        It must be called after `find_unambiguous_names` because the completion
        of item keys is only necessary within one column group, and the column
        groups base on the names created by ``find_unambiguous_names``.  In
        other words, if ``Nice result`` and ``Nice result #2`` don't share the
        same item keys, this is unimportant.  But if ``Nice result #2`` of two
        samples in the exported series didn't share the same item keys, this
        would result in a ``KeyError`` exception in
        :py:meth:`samples.views.table_export.Column.get_value`.

        This is not optimal for performance reasons.  But it is much easier
        than to train `build_column_group_list` to handle it.

        :param key_sets: The item keys for all node names.  It is only used in
            the recursion.  If you call this method, you never give this
            parameter.
        :param item_cache: The key names of the items for a given node.  Note
            that in contrast to `key_sets`, the keys of this are the nodes
            themselves rather than the disambiguated node names.  It is used
            for performance's sake.  If you call this method, you never give
            this parameter.

        :type key_sets: dict mapping str to set of (str, str)
        :type item_cache: dict mapping `DataNode` to set of (str, str)
        """
        if key_sets is None:
            item_cache = {}
            def collect_key_sets(node):
                """Collect all item keys of this node and its decentends.
                This is the first phase of the process.  It returns a mapping
                of node names (*not* node kinds) to item key sets.  We set both
                the ``key_sets`` and the ``item_cache`` here.
                """
                item_cache[node] = {(item.key, item.origin) for item in node.items}
                key_sets = {node.name: item_cache[node]}
                for child in node.children:
                    for name, key_set in collect_key_sets(child).items():
                        key_sets[name] = key_sets.setdefault(name, set()).union(key_set)
                return key_sets
            key_sets = collect_key_sets(self)
        missing_items = key_sets[self.name] - item_cache[self]
        for key, origin in missing_items:
            self.items.append(DataItem(key, "", origin))
        for child in self.children:
            child.complete_items_in_children(key_sets, item_cache)

    def __repr__(self):
        return repr(self.name)


class DataItem:
    """This class represents a key–value pair, holding the actual data in a
    `DataNode` tree.

    :ivar key: the key name of the data item

    :ivar value: the value of the data item

    :ivar origin: an optional name of the class from where this data item comes
      from.  Its necessity is not easy to explain.  The problem is that we have
      inheritance in the models, for example, a deposition is derived from
      `samples.models.Process`.  When calling the ``get_data`` method of a
      deposition, it first calls the ``get_data`` method of
      ``samples.models.Process``, which adds operator, timestamp, and comments
      to the items list.  However, the same is true for all other processes.

      But this means that e.g. the “timestamp” column ends up in different
      column groups when exporting the processes as rows in a table.  That's
      rubbish because it's actually always the same property.

      Thus, in order to preserve inheritance, such inherited attributes are
      called “shared columns” in JuliaBase's CSV export.  They are marked with
      a non-``None`` ``origin`` parameter which just contains a symbol for the
      model class, e.g. ``"process"`` for ``samples.models.Process``.

    :type key: str
    :type value: object
    :type origin: str or NoneType
    """

    def __init__(self, key, value, origin=None):
        """Class constructor.

        :param key: the key name of the data item
        :param value: the value of the data item
        :param origin: an optional name of the class from where this data item
            comes from.

        :type key: str or Promise (Django lazy string object)
        :type value: object
        :type origin: str or NoneType
        """
        assert isinstance(key, (str, Promise))
        self.key, self.value, self.origin = key, value, origin
