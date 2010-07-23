#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Module with CSV-related classes that are needed in the models.  Therefore,
they cannot be defined in a view because then you'd have cyclic imports.
"""


class CSVNode(object):
    u"""Class for a node in a data tree intended for CSV export.

    :ivar name: name of this node; must be the same for node whose items carry
      the same semantics

    :ivar descriptive_name: name which is used if this node is a row node in
      the final tree, as a row description in the very first column.

    :ivar items: Key–value pairs with the actual data.  Again, for nodes with
      the same `name` (i.e. of the same *type*), this list must always have the
      same length and the sample key ordering.  Note that this is not a
      dictionary in order to preserve ordering.

    :ivar children: the child nodes of this node in the three

    :type name: unicode
    :type descriptive_name: unicode
    :type items: list of (unicode, unicode)
    :type childen: list of `CSVNode`
    """

    def __init__(self, instance, descriptive_name=u""):
        u"""Class constructor.

        :Parameters:
          - `instance`: The model instance whose data is extracted, or the name
            that should be used for this node.  If you pass an instance, the
            name is the *type* of the instance, e.g. “6-chamber deposition” or
            “sample”.
          - `descriptive_name`: The “first column” name of the node.  It should
            be more concrete than just the type but it depends.  For samples
            for example, it is the sample's name.  By default, it is the type
            of the instance or the string you gave as ``instance``.

        :type instance: ``models.Model`` or unicode
        :type descriptive_name: unicode
        """
        if isinstance(instance, unicode):
            self.name = self.descriptive_name = instance
        else:
            self.name = unicode(instance._meta.verbose_name)
        self.descriptive_name = unicode(descriptive_name) or self.name
        self.items = []
        self.children = []

    def find_unambiguous_names(self, renaming_offset=1):
        u"""Make all names in the whole tree of this node instance
        unambiguous.  This is done by two means:

        1. If two sister nodes share the same name, a number like ``" #1"`` is
           appended.

        2. The names of the ancestor nodes are prepended, e.g. ``"6-chamber
           deposition, layer #2"``

        :Parameters:
          - `renaming_offset`: number of the nesting levels still to be stepped
            down before disambiguation of the node names takes place.

        :type renaming_offset: int
        """
        names = [child.name for child in self.children]
        for i, child in enumerate(self.children):
            if renaming_offset <= 0:
                if names.count(child.name) > 1:
                    child.name += u" #{0}".format(names[:i].count(child.name) + 1)
                child.name = self.name + ", " + child.name
            child.find_unambiguous_names(renaming_offset - 1)

    def __repr__(self):
        return repr(self.name)


class CSVItem(object):
    u"""This class represents a key–value pair, holding the actual data in a
    `CSVNode` tree.

    :ivar key: the key name of the data item

    :ivar value: the value of the data item

    :ivar origin: an optional name of the class from where this data item comes
      from.  Its necessity is not easy to explain.  The problem is that we have
      inheritance in the models, for example, a deposition is derived from
      `models.Process`.  When calling the ``get_data`` method of a deposition,
      it first calls the ``get_data`` method of ``models.Process``, which adds
      operator, timestamp, and comments to the items list.  However, the same
      is true for all other processes.

      But this means that e.g. the “timestamp” column ends up in different
      column groups when exporting the processes as rows in a table.  That's
      rubbish because it's actually always the same property.

      Thus, in order to preserve inheritance, such inherited attributes are
      called “shared columns” in Chantal's CSV export.  They are marked with a
      non-``None`` ``origin`` parameter which just contains a symbol for the
      model class, e.g. ``"process"`` for ``models.Process``.

    :type key: unicode
    :type value: unicode
    :type origin: str or ``NoneType``
    """

    def __init__(self, key, value, origin=None):
        u"""Class constructor.

        :Parameters:
          - `key`: the key name of the data item
          - `value`: the value of the data item
          - `origin`: an optional name of the class from where this data item
            comes from.  See `CSVItem.origin` for more information.

        :type key: unicode
        :type value: unicode
        :type origin: str or ``NoneType``
        """
        self.key, self.value, self.origin = unicode(key), unicode(value or u""), origin
