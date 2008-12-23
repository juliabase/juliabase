#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Main routines and all views for the CSV table export.  Believe it or not,
this is probably the most complicated thing in Chantal.  The problem is that
data in Chantal has a tree-like structure, which is completely incompatible
with the table structure needed for CSV export.

The tree
........

The starting point is the `CSVNode` tree.  It is the result of a ``get_data``
method call of a sample, sample series, or single process.  The root note of
such a tree represents the instance whose ``get_data`` method was called.

The direct children of the top node are called “row nodes” or “row trees”
because they will form the rows of the table, by being flattened.

Every `CSVNode` has not only children, but also key–value items containing the
actual data.  Both key and value are unicodes.  Additionally, it has a ``name``
which denotes the type or class of the `CSVNode`.  For example, the ``name`` of
a process may be “PDS measurement” or “6-chamber deposition”.

Making the node names unique
............................

The first transformation which is performed is that the names are made unique
for each row tree.  This is necessary to avoid name clashs in column headings.
For this, numbers are appended if two sister nodes share the same ``name``.
Then, the names of ancestor nodes are prepended.  Therefore, the name of a node
may be “6-chamber deposition #1, layer #2”.

Finding column groups and columns
.................................

The next goal is to organise the columns.  For this I need two data structures:
The ``column_groups`` resembles the union of the nodes in all row trees,
without duplicates.  So, the first row tree is walked through, and each of its
nodes is put into the ``column_groups`` list directly.  Then, the next tree is
scanned, but only *new* nodes (i.e., with a so-far unknown ``name``) are added,
and so forth.  I try to make the order within ``column_groups`` senseful,
however in theory, it doesn't matter really.

The second data structure for columns is simply called ``columns``, and it is
built parallely to ``column_groups`` in `build_column_group_list`.  Whenever a
new column groups is added, its keys (from the key–value items ot its node) are
appended to the list of columns.  The resulting indices in ``columns`` are
saved in the column group attribute `ColumnGroup.key_indices`.  This is a
dictionary, mapping key names to their index in the ``columns`` list.

The web view
............

Now the user comes into play.  He is presented the column groups and their keys
in an HTML multiple selection widget.  The values are simply the indices in
``columns``.  Therefore, they are the result sent back to the server as a list
of integers.  Duplicates are dropped (they may occur due to shared columns, see
below).

Generating the final table
..........................

The last needed data structure is a list of all rows, generated by
`flatten_tree`.  Every row is represented by a dictionary with unicode keys
being names of column groups.  They are mapped to another dictionary mapping
key names to values (both unicodes).  This this of rows is generated by
`flatten_tree`.

Finally we're ready to generate the table with `generate_table_rows`: For each
row, the list of indices is used to find the value for the respective column by
using the ``columns`` list, which contains a `Column` instance, which is able
to retrieve the final table cell value through the `Column.get_value` method.

This way, the table is represented by a list of rows, and each row a list of
cells.  Every cell item is a unicode.  The zeroth row contains the headings,
the zeroth column the labels for the column (e.g., in case of exporting a
sample series, the sample names).

This very simple data structure can be used directly to show a preview table in
HTML, or to create the CSV data by sending it through an instance of
`UnicodeWriter`.

Making models fit for CSV export
................................

In order to get a proper node tree, all involved model instances must have a
``get_data`` method.  This method must return a `CSVNode`, which may in turn be
the root of a whole ``CSVNode`` subtree.  Additionally, it probably will append
items to the ``items`` list with the values of the database instance's
attributes.  See `CSVNode` and `csv_common.CSVItem` for further information.
Additionally, the various instances of the ``get_data`` method in various
database model classes will show you how to use it (they are all very
strightforward).
"""

import csv, cStringIO, codecs
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import HttpResponse
import django.forms as forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal.samples.views import utils
from chantal.samples.csv_common import CSVNode

class UnicodeWriter(object):
    u"""Convert a two-dimensional data structure into a UTF-8-encoded CSV byte
    string.  Inspired by <http://docs.python.org/library/csv.html#examples>.
    """
    def __init__(self, dialect=csv.excel_tab, encoding="utf-8", **kwargs):
        u"""Class constructor.  Additional keyword arguments are passed to the
        ``csv.writer`` factory function in Python's ``csv`` module.  After
        having instantiated this class, you can use `writerow` and `writerows`
        to add data to it, and then extract it in the CSV format using
        `getvalue`.

        :Parameters:
          - `dialect`: the CSV format; it defaults to Excel's TAB format
            (TAB-separated, double-quotes)
          - `encoding`: name of the output encoding to be used; defaults to
            UTF-8

        :type dialect: ``csv.Dialect``
        :type encoding: str
        """
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwargs)
        self.stream = cStringIO.StringIO()
        self.encoder = codecs.getincrementalencoder(encoding)()
    def writerow(self, row):
        u"""Add the given row to the output.

        :Parameters:
          - `row`: list of the table cells

        :type row: list of unicode
        """
        self.writer.writerow([unicode(s).encode("utf-8") for s in row])
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)
    def writerows(self, rows):
        u"""Add the given rows to the output.

        :Parameters:
          - `rows`: list of rows; each row is a list of table cells

        :type rows: list of list of unicode
        """
        for row in rows:
            self.writerow(row)
    def getvalue(self):
        u"""Get the output so far.  Normally, you will call this method after
        the instance was filled with all data.  Thus, after called this method,
        the instance of ``UnicodeWriter`` is no longer used.

        :Return:
          the table in CSV format, as an encoded octet string

        :rtype: str
        """
        return self.stream.getvalue()

class ColumnGroup(object):
    u"""Class for representing of set of columns in the table output which
    corresponds to one node type in the input tree.  In the output, the column
    groups are arranged next to each other to form the complete table.  The
    user doesn't notice that because the CSV format doesn't allow for visible
    separation (e.g. by vertical lines) between column groups.

    Instances of this class will be in a list returned by
    `build_column_group_list`.  This list serves two purposes: First, it is
    used internally in ``build_column_group_list`` for avoiding inserting a
    node name twice.  And secondly, it is used to create the multi selection
    boxes in the HTML view for the user.

    :ivar name: name of the column group which directly corresponds to the name
      of the respective `CSVNode`.  It must never contain a TAB character
      because this is used as a separator in `OldDataForm`.

    :ivar key_indices: dictionary which maps key names to their index in the
      ``columns`` list which is built parallely to the list of
      ``ColumnGroup``.

    :type name: unicode
    :type key_indices: dict mapping unicode to int
    """
    def __init__(self, name):
        u"""Class constructor.

        :Parameters:
          - `name`: the name of the `CSVNode` this column group represents

        :type name: unicode
        """
        self.name = name
        self.key_indices = {}
    def __repr__(self):
        return repr(self.name)
    def __eq__(self, other):
        u"""Equation operator.  I need this function because in
        `build_column_group_list`, I must be able to test easily whether a
        given column group is contained in a given list.

        :Parameters:
          - `other`: the instance to compare with

        :type other: `ColumnGroup`

        :Return:
          whether ``other`` is equal to the current instance

        :rtype: bool
        """
        return self.name == other.name

class Column(object):
    u"""Class for one column in the exported table.  The list of ``Column``
    instances is built in `build_column_group_list`.  It contains *all*
    columns, even those that the user doesn't choose for output.  The index in
    this list is stored in the values of `ColumnGroup.key_indices`.

    :ivar column_group_names: List of names of column groups where one can
      expect the key–value pairs for this column.

      Normally, this list contains exactly *one* item because a column points
      to exactly one particular key in one particular column group.  However in
      case of “shared columns”, this is not so simple anymore.  Then, the value
      is in exactly one of the shared columns, so we have to check all of them
      until we find something.  For more information about shared columns, see
      `csv_common.CSVItem.__init__`.

    :ivar key: the pristine name of the key this column points to, i.e. it
      doesn't contain any affixes to make it unambiguous

    :ivar heading: The heading of the column.  Basically, it's the same as
      `key`, however, if this is ambiguous because another key in another
      column groups has the same name, it is made unique by appending ``" {node
      name}"`` to it.
    """
    def __init__(self, column_group_name, key):
        u"""Class constructor.

        :Parameters:
          - `column_group_name`: the name of the column group this column is
            part of
          - `key`: the pristine key name this column corresponds to

        :type column_group_name: unicode
        :type key: unicode
        """
        self.column_group_names = [column_group_name]
        self.key = self.heading = key
    def append_name(self, column_group_name):
        u"""Append the name of a column group with a shared key.  If the
        current instance of ``Column`` is a shared key, you must call this
        method for each other column group which contains this shared key
        (instead of appending a new key to the ``columns`` list in
        `build_column_group_list`).  For more information about shared columns,
        see `csv_common.CSVItem.__init__`.

        :Parameters:
          - `column_group_name`: the name of the column group this column is
            found in as a shared key

        :type column_group_name: unicode 
        """
        self.column_group_names.append(column_group_name)
    def disambig(self):
        u"""Make the column heading unique.  Normally, the key is used directly
        for the column heading.  However, if the same key name is used in
        another column group, ``disambig_key_names`` calls this method to make
        it unique.
        """
        self.heading = u"%s {%s}" % (self.key, u" / ".join(self.column_group_names))
    def get_value(self, row):
        u"""Return the value of this column in the given row.

        :Parameters:
          - `row`: the row for which the value in this column should be
            determined

        :type row: dict mapping unicode to dict mapping unicode to unicode

        :Return:
          the cell value of this column in the given row; the empty string if
          the respective column group is not available for the given row

        :rtype: unicode
        """
        for column_group_name in self.column_group_names:
            if column_group_name in row:
                return row[column_group_name][self.key]
        return u""

def build_column_group_list(root):
    u"""Extract from the ``CVSNode`` tree the column group list and the column
    list.  The column group list can be used to show the user the columns in a
    structured form, and to export the data in ODF or Excel format.  The
    columns are used for any export, ODF, Excel, and CSV.

    :Parameters:
      - `root`: The root node of the ``CSVNode`` tree.  It must be a complete
        tree, i.e. the top-level children are considered the row tree.  The
        node names must have been made unambiguous within a row tree already
        using `CSVNode.find_unambiguous_names`.

    :type root: `CSVNode`

    :Return:
      the column groups, the column list

    :rtype: list of `ColumnGroup`, list of `Column`
    """
    def walk_row_tree(node, top_level=True):
        u"""Extract all node names from a ``CSVNode`` tree.  This routine calls
        itself recursively to walk through the tree.  Note that the inner order
        of the nodes (e.g. the chronological order of processes) is preserved
        by this method.

        :Parameters:
          - `node`: the root node of the (sub-)tree to be analysed

        :type node: `CSVNode`

        :Return:
          all node names

        :rtype: list of unicode
        """
        node.top_level = top_level
        name_list = [node]
        for child in node.children:
            name_list.extend(walk_row_tree(child, top_level=False))
        return name_list
    def disambig_key_names(columns):
        u"""Helper function for making all column headings unambiguous.  When
        the columns list is complete, and shortly before it is returned by
        ``build_column_group_list``, it is manipulated so that all ``heading``
        attributes of the columns are unique in the whole table.

        Note that this is only interesting for CSV export.  If you export to
        ODF or Excel, there is a cleaner way by using the column groups to
        format the table (vertical lines, multi-column spans in the header
        etc).  So for ODF and Excel export, the ``heading`` attribute is not
        needed but the pristine ``key`` attribute.

        :Parameters:
          - `columns`: the complete list of columns

        :type columns: list of `Column`
        """
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
                column_group = ColumnGroup(name)
                i = len(columns)
                for item in node.items:
                    if node.top_level and item.origin:
                        shared_key = (item.origin, item.key)
                        if shared_key in shared_columns:
                            column_group.key_indices[item.key] = shared_columns[shared_key]
                            columns[shared_columns[shared_key]].append_name(name)
                            continue
                        else:
                            shared_columns[shared_key] = i
                    column_group.key_indices[item.key] = i
                    columns.append(Column(name, item.key))
                    i += 1
                column_groups.insert(position, column_group)
            position += 1
    disambig_key_names(columns)
    return column_groups, columns

def flatten_tree(root):
    u"""Walk through a ``CSVNode`` tree and convert it to a list of nested
    dictionaries for easy cell value lookup.  The resulting data structure is
    used in `Column.get_value`.

    :Parameters:
      - `root`: The root node of the ``CSVNode`` tree.  It must be a complete
        tree, i.e. the top-level children are considered the row tree.  The
        node names must have been made unambiguous within a row tree already
        using `CSVNode.find_unambiguous_names`.

    :type root: `CSVNode`

    :Return:
      list of all rows containg a dictionary mapping node names (loosely
      corresponding to column group names) to dictionaries mapping key names to
      cell values

    :rtype: list of dictionary mapping unicode to dictionary mapping unicode to
      unicode
    """
    def flatten_row_tree(node):
        name_dict = {node.name: dict((item.key, item.value) for item in node.items)}
        for child in node.children:
            name_dict.update(flatten_row_tree(child))
        return name_dict
    return [flatten_row_tree(row) for row in root.children]

def generate_table_rows(flattened_tree, columns, selected_key_indices, label_column, label_column_heading):
    u"""Generate the final table suited for CSV export and HTML preview.  Note
    that for ODF or Excel output, you should also take the column group list
    into account for better formatting.

    :Parameters:
      - `flattened_tree`: the transformed tree as constructed by
        `flatten_tree`.
      - `columns`: list of columns as constructed by `build_column_group_list`
      - `selected_key_indices`: list of the column indices which the user
        selected for output
      - `label_column`: The values of the first column, which is supposed to
        contain some sort of heading of the respective row.  For example, for a
        sample series table, the rows are the samples of the series, and their
        names are printed in the first column.  Therefore, the length of this
        list must be equal to the number of rows.
      - `label_column_heading`: Description of the very first column with the
        table row headings.  This is the contents of the top left cell.  For
        example, for a sample series table, it may be ``"sample"`` because the
        rows are the samples of the series, and their names are printed in the
        first column.

    :type flattened_tree: list of dictionary mapping unicode to dictionary
      mapping unicode to unicode
    :type columns: list of `Column`
    :type selected_key_indices: list of int
    :type label_column: list of unicode
    :type label_column_heading: unicode

    :Return:
      The table as a nested list.  The outer list are the rows, the inner the
      columns.  Each cell is a unicode string.

    :rtype: list of list of unicode
    """
    # Generate headline
    table_rows = [[label_column_heading] + [unicode(columns[key_index].heading) for key_index in selected_key_indices]]
    for i, row in enumerate(flattened_tree):
        table_row = [label_column[i]]
        for key_index in selected_key_indices:
            table_row.append(columns[key_index].get_value(row))
        table_rows.append(table_row)
    return table_rows

class ColumnGroupsForm(forms.Form):
    u"""Form for the columns choice.  It has only one field, ``column_groups``,
    the result of which is a set with the selected column group names.
    """
    column_groups = forms.MultipleChoiceField(label=_(u"Column groups"))
    def __init__(self, column_groups, *args, **kwargs):
        super(ColumnGroupsForm, self).__init__(*args, **kwargs)
        self.fields["column_groups"].choices = ((column_group.name, column_group.name) for column_group in column_groups)
    def clean_column_groups(self):
        return set(self.cleaned_data["column_groups"])

class ColumnsForm(forms.Form):
    u"""Form for the columns choice.  It has only one field, ``columns``, the
    result of which is a set with the selected column indices as ints.
    """
    columns = forms.MultipleChoiceField(label=_(u"Columns"))
    def __init__(self, column_groups, columns, selected_column_groups, *args, **kwargs):
        super(ColumnsForm, self).__init__(*args, **kwargs)
        self.fields["columns"].choices = ((column_group.name, [(key_index, key_name) for key_name, key_index
                                                               in column_group.key_indices.iteritems()])
                                          for column_group in column_groups if column_group.name in selected_column_groups)
    def clean_columns(self):
        try:
            return set(int(i) for i in self.cleaned_data["columns"])
        except ValueError:
            # Untranslable because internal anyway
            raise ValidationError(u"Invalid number in column indices list")

class OldDataForm(forms.Form):
    u"""Form which stores the user input of the previous run.  It is not
    intended for user interaction, in fact it is hidden in the HTML.  By
    comparing the user's input with what is stored here, `export` can detect
    whether the user has changed something.
    """
    column_groups = forms.CharField(required=False)
    columns = forms.CharField(required=False)
    def __init__(self, *args, **kwargs):
        initial = kwargs.pop("initial", {})
        kwargs["prefix"] = "old_data"
        super(OldDataForm, self).__init__(*args, **kwargs)
        if "column_groups" in initial:
            self.fields["column_groups"].initial = u"\t".join(column_group for column_group in initial["column_groups"])
        if "columns" in initial:
            self.fields["columns"].initial = u" ".join(str(i) for i in initial["columns"])
    def clean_column_groups(self):
        return set(self.cleaned_data["column_groups"].split("\t"))
    def clean_columns(self):
        try:
            return set(int(i) for i in self.cleaned_data["columns"].split())
        except ValueError:
            # Untranslable because internal anyway
            raise ValidationError(u"Invalid number in column indices list")

class SwitchRowForm(forms.Form):
    u"""Form for the tick marks before every row in the preview table.  If it
    is checked, the respective row is included into the CSV export.
    """
    active = forms.BooleanField(required=False)

def export(request, database_object, label_column_heading, renaming_offset=1):
    u"""Helper function which does almost all work needed for a CSV table
    export view.  This is not a view per se, however, it is called by views,
    which have to do almost nothing anymore by themselves.  See for example
    `sample.export`.

    :Parameters:
      - `request`: the current HTTP Request object
      - `database_object`: the database instance that is to be exported
      - `label_column_heading`: Description of the very first column with the
        table row headings, see `generate_table_rows`.
      - `renaming_offset`: number of the nesting levels in the tree still to be
        stepped down from the root node before disambiguation of the node names
        takes place.

    :type request: ``HttpRequest``
    :type database_object: ``django.db.models.Model``
    :type label_column_heading: unicode
    :type renaming_offset: int

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    data = database_object.get_data()
    data.find_unambiguous_names(renaming_offset)
    column_groups, columns = build_column_group_list(data)
    single_column_group = set([column_groups[0].name]) if len(column_groups) == 1 else []
    table = None
    selected_column_groups = set(single_column_group)
    selected_columns = set()
    if request.method == "POST":
        column_groups_form = ColumnGroupsForm(column_groups, request.POST) if not single_column_group else None
        previous_data_form = OldDataForm(request.POST)
        if previous_data_form.is_valid():
            previous_column_groups = previous_data_form.cleaned_data["column_groups"]
            previous_columns = previous_data_form.cleaned_data["columns"]
        else:
            previous_column_groups = previous_columns = frozenset()
        columns_form = ColumnsForm(column_groups, columns, previous_column_groups, request.POST)
        if single_column_group or column_groups_form.is_valid():
            selected_column_groups = single_column_group or column_groups_form.cleaned_data["column_groups"]
            if columns_form.is_valid():
                selected_columns = columns_form.cleaned_data["columns"]
                label_column = [row.descriptive_name for row in data.children]
                table = generate_table_rows(flatten_tree(data), columns, columns_form.cleaned_data["columns"],
                                            label_column, label_column_heading)
                if not(previous_columns) and selected_columns:
                    switch_row_forms = [SwitchRowForm(prefix=str(i), initial={"active": any(row[1:])})
                                        for i, row in enumerate(table)]
                else:
                    switch_row_forms = [SwitchRowForm(request.POST, prefix=str(i)) for i in range(len(table))]
                all_switch_row_forms_valid = all([switch_row_form.is_valid() for switch_row_form in switch_row_forms])
                if all_switch_row_forms_valid and \
                        previous_column_groups == selected_column_groups and previous_columns == selected_columns:
                    reduced_table = \
                        [row for i, row in enumerate(table) if switch_row_forms[i].cleaned_data["active"] or i == 0]
                    writer = UnicodeWriter()
                    writer.writerows(reduced_table)
                    return HttpResponse(writer.getvalue(), content_type="text/csv; charset=utf-8")
        if selected_column_groups != previous_column_groups:
            columns_form = ColumnsForm(column_groups, columns, selected_column_groups, initial={"columns": selected_columns})
    else:
        column_groups_form = ColumnGroupsForm(column_groups) if not single_column_group else None
        columns_form = ColumnsForm(column_groups, columns, single_column_group)
    old_data_form = OldDataForm(initial={"column_groups": selected_column_groups, "columns": selected_columns})
    title = _(u"Table export for “%s”") % database_object
    return render_to_response("csv_export.html", {"title": title, "column_groups": column_groups_form,
                                                  "columns": columns_form,
                                                  "rows": zip(table, switch_row_forms) if table else None,
                                                  "old_data": old_data_form,
                                                  "backlink": utils.parse_query_string(request).get("next") or \
                                                      database_object.get_absolute_url()},
                              context_instance=RequestContext(request))
