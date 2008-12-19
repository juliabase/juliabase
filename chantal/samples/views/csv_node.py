#!/usr/bin/env python
# -*- coding: utf-8 -*-

class CSVNode(object):
    def __init__(self, instance):
        if isinstance(instance, unicode):
            self.name = self.descriptive_name = instance
        else:
            self.name = unicode(instance._meta.verbose_name)
            self.descriptive_name = unicode(instance)
        self.items = []
        self.children = []
    def find_unambiguous_names(self, top_level=True):
        names = [child.name for child in self.children]
        for i, child in enumerate(self.children):
            if names.count(child.name) > 1:
                child.name += u" #%d" % (names[:i].count(child.name) + 1)
            if not top_level:
                child.name = self.name + ", " + child.name
            child.find_unambiguous_names(top_level=False)
    def __repr__(self):
        return repr(self.name)

class CSVItem(object):
    def __init__(self, key, value, origin=None):
        self.key, self.value, self.origin = unicode(key), unicode(value), origin
