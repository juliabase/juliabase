#!/usr/bin/env python
# -*- coding: utf-8 -*-

class CSVNode(object):
    def __init__(self, name):
        self.name = name
        self.items = []
        self.children = []
    def find_unambiguous_names(self, prepent_parent_name=False):
        names = [child.name for child in self.children]
        for i, child in enumerate(self.children):
            if names.count(child.name) > 1:
                child.name += u" #%d" % (names[:i].count(child.name) + 1)
            if prepent_parent_name:
                child.name = self.name + ", " + child.name
            child.find_unambiguous_names(True)
    def __repr__(self):
        return repr(self.name)
