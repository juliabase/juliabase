#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.append("/home/bronger/src/chantal/current")

import csv, cStringIO, codecs
from chantal.samples.views.csv_node import CSVNode
from chantal.samples import models

class UnicodeWriter(object):
    u"""Taken from <http://docs.python.org/library/csv.html#examples>.
    """
    def __init__(self, filename, dialect=csv.excel, encoding="utf-8", **kwargs):
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwargs)
        self.stream = open(filename, "wb")
        self.encoder = codecs.getincrementalencoder(encoding)()
    def writerow(self, row):
        self.writer.writerow([unicode(s).encode("utf-8") for s in row])
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)
    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

class CSVColumnGroup(object):
    def __init__(self, name):
        self.name = name
        self.key_indices = []
    def __repr__(self):
        return repr(self.name)
    def __eq__(self, other):
        return self.name == other.name

def build_column_group_list(root):
    def walk_row_tree(node):
        name_list = [node]
        for child in node.children:
            name_list.extend(walk_row_tree(child))
        return name_list
    def disambig_key_names(keys):
        seen = set()
        duplicates = set()
        for __, __, key in keys:
            if key in seen:
                duplicates.add(key)
            else:
                seen.add(key)
        for key in keys:
            if key[2] in duplicates:
                key[2] = u"%s {%s}" % (key[1], key[0])
    keys = []
    column_groups = []
    position = 0
    for row, row_tree in enumerate(root.children):
        for node in walk_row_tree(row_tree):
            if row > 0 and node in column_groups:
                position = column_groups.index(node)
            else:
                name = node.name
                column_group = CSVColumnGroup(name)
                i = len(keys)
                for key, __ in node.items:
                    column_group.key_indices.append(i)
                    keys.append([name, key, key])
                    i += 1
                column_groups.insert(position, column_group)
            position += 1
    disambig_key_names(keys)
    return column_groups, keys

def flatten_tree(root):
    def flatten_row_tree(node):
        name_dict = {node.name: dict(node.items)}
        for child in node.children:
            name_dict.update(flatten_row_tree(child))
        return name_dict
    return [flatten_row_tree(row) for row in root.children]
    
    
pds_measurement = models.Sample.objects.get(name="08-TB-erste")
data = pds_measurement.get_data()
data.find_unambiguous_names()
column_groups, keys = build_column_group_list(data)
print flatten_tree(data)
# for row in data.children:
#     print unicode(row.name)
