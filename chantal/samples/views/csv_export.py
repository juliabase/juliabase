#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.append("/home/bronger/src/chantal/current")

import csv, cStringIO, codecs
from chantal.samples.csv_common import CSVNode
from chantal.samples import models

class UnicodeWriter(object):
    u"""Inspired by <http://docs.python.org/library/csv.html#examples>.
    """
    def __init__(self, dialect=csv.excel, encoding="utf-8", **kwargs):
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwargs)
        self.stream = cStringIO.StringIO()
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
    def getvalue(self):
        return self.stream.getvalue()

class CSVColumnGroup(object):
    def __init__(self, name):
        self.name = name
        self.key_indices = []
    def __repr__(self):
        return repr(self.name)
    def __eq__(self, other):
        return self.name == other.name

class Column(object):
    def __init__(self, column_group_name, key):
        self.column_group_names = [column_group_name]
        self.key = self.heading = key
    def append_name(self, column_group_name):
        self.column_group_names.append(column_group_name)
    def disambig(self):
        self.heading = u"%s {%s}" % (self.key, u" / ".join(self.column_group_names))
    def get_value(self, row):
        for column_group_name in self.column_group_names:
            if column_group_name in row:
                return row[column_group_name][self.key]
        return u""

def build_column_group_list(root):
    def walk_row_tree(node, top_level=True):
        node.top_level = top_level
        name_list = [node]
        for child in node.children:
            name_list.extend(walk_row_tree(child, top_level=False))
        return name_list
    def disambig_key_names(columns):
        seen = set()
        duplicates = set()
        for column in columns:
            key = column.key
            if key in seen:
                duplicates.add(key)
            else:
                seen.add(key)
        for column in columns:
            if column.key in duplicates:
                column.disambig()
    columns = []
    column_groups = []
    shared_columns = {}
    position = 0
    for row, row_tree in enumerate(root.children):
        for node in walk_row_tree(row_tree):
            if row > 0 and node in column_groups:
                position = column_groups.index(node)
            else:
                name = node.name
                column_group = CSVColumnGroup(name)
                i = len(columns)
                for item in node.items:
                    if node.top_level and item.origin:
                        shared_key = (item.origin, item.key)
                        if shared_key in shared_columns:
                            column_group.key_indices.append(shared_columns[shared_key])
                            columns[shared_columns[shared_key]].append_name(name)
                            continue
                        else:
                            shared_columns[shared_key] = i
                    column_group.key_indices.append(i)
                    columns.append(Column(name, item.key))
                    i += 1
                column_groups.insert(position, column_group)
            position += 1
    disambig_key_names(columns)
    return column_groups, columns

def flatten_tree(root):
    def flatten_row_tree(node):
        name_dict = {node.name: dict((item.key, item.value) for item in node.items)}
        for child in node.children:
            name_dict.update(flatten_row_tree(child))
        return name_dict
    return [flatten_row_tree(row) for row in root.children]

def generate_table_rows(flattened_tree, columns, selected_key_indices, first_column, first_column_heading):
    # Generate headline
    table_rows = [[first_column_heading] + [unicode(columns[key_index].heading) for key_index in selected_key_indices]]
    for i, row in enumerate(flattened_tree):
        table_row = [first_column[i]]
        for key_index in selected_key_indices:
            table_row.append(columns[key_index].get_value(row))
        table_rows.append(table_row)
    return table_rows
    
pds_measurement = models.Sample.objects.get(name="08-TB-erste")
data = pds_measurement.get_data()
data.find_unambiguous_names()
first_column = [row.descriptive_name for row in data.children]
first_column_heading = "Prozess"
column_groups, columns = build_column_group_list(data)
flattened_tree = flatten_tree(data)
#print flattened_tree
writer = UnicodeWriter()
writer.writerows(generate_table_rows(flattened_tree, columns, range(len(columns)), first_column, first_column_heading))
print writer.getvalue()

# for row in data.children:
#     print unicode(row.name)
