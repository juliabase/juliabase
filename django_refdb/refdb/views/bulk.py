#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.
#
#     Django-RefDB is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public
#     License as published by the Free Software Foundation, either
#     version 3 of the License, or (at your option) any later
#     version.
#
#     Django-RefDB is distributed in the hope that it will be
#     useful, but WITHOUT ANY WARRANTY; without even the implied
#     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#     PURPOSE.  See the GNU Affero General Public License for more
#     details.
#
#     You should have received a copy of the GNU Affero General
#     Public License along with Django-RefDB.  If not, see
#     <http://www.gnu.org/licenses/>.


u"""View and routines for the bulk view.  In the bulk view, the results of a
search are displayed in pages.  Additionally, it is used to visualise
references lists.

Note that the write operations to the RefDB database are atomic, therefore, I
don't need rollback actions.
"""

from __future__ import absolute_import

import os.path
import xapian
from django.template import RequestContext, defaultfilters
from django.shortcuts import render_to_response
from django.views.decorators.http import last_modified, require_http_methods
from django.utils.http import urlencode
from django.utils.translation import ugettext as _, ugettext, ugettext_lazy
from django.contrib.auth.decorators import login_required
import django.core.urlresolvers
from django import forms
from django.core.cache import cache
from django.conf import settings
from chantal_common import utils as chantal_utils
from .. import refdb, models
from . import utils


class SearchForm(forms.Form):
    u"""Form class for the search filters.  Currently, it only accepts a RefDB
    query string.
    """

    _ = ugettext_lazy
    query_string = forms.CharField(label=_("Query string"), required=False)
    author = forms.CharField(label=_("Author"), required=False)
    title = forms.CharField(label=_("Title"), required=False)
    journal = forms.CharField(label=_("Journal"), required=False)
    year_from = forms.DecimalField(label=_("Year from"), required=False)
    year_until = forms.DecimalField(label=_("Year until"), required=False)
    full_text_query = forms.CharField(label=_("Full text"), required=False)

    def get_query_string(self, user_id):
        u"""Takes the parameters of the form and distills a RefDB query string
        from them.

        :Parameters:
          - `user_id`: ID of the currently loggeed-in user

        :type user_id: int
        
        :Return:
          the RefDB query string representing the search

        :rtype: unicode
        """
        # FixMe: Proper escaping of user-provided parameters is still needed.
        components = []
        if self.cleaned_data["query_string"]:
            components.append(self.cleaned_data["query_string"])
        if self.cleaned_data["author"]:
            components.append(u":AX:~" + self.cleaned_data["author"])
        if self.cleaned_data["title"]:
            components.append(u":TX:~" + self.cleaned_data["title"])
        if self.cleaned_data["journal"]:
            components.append(u":JO:~%s OR :JF:~%s" % (2*(self.cleaned_data["journal"],)))
        if self.cleaned_data["year_from"]:
            components.append(u":PY:>=" + str(self.cleaned_data["year_from"]))
        if self.cleaned_data["year_until"]:
            components.append(u":PY:<=" + str(self.cleaned_data["year_until"]))
        if self.cleaned_data["full_text_query"]:
            components.append(u":NCK:=django-refdb-global-pdfs OR :NCK:=django-refdb-personal-pdfs-%s" % user_id)
        if not components:
            return u":ID:>0"
        elif len(components) == 1:
            return components[0]
        else:
            return u"(" + u") AND (".join(components) + u")"

    def extract_words_to_highlight(self):
        u"""Returns the key words which were used in the full-text search.

        :Return:
          all words which took part in the full-text search; ``None`` if there
          was no full-text search

        :rtype: set of unicode
        """
        full_text_query = self.cleaned_data["full_text_query"]
        if full_text_query:
            words = full_text_query.split()
            tidy_words = set()
            for word in words:
                if word.upper() not in ["NOT", "OR", "AND", "NEAR"]:
                    tidy_words.add(word.strip('"'))
            return tidy_words


class SelectionBoxForm(forms.Form):
    u"""Form class for the tick box for each reference.  This micro-form is
    generated for each reference in the bulk view.  The actions of the central
    dispatch are performed only on selected references.
    """
    _ = ugettext_lazy
    selected = forms.BooleanField(label=_("selected"), required=False)


output_format_choices = (
    ("ris", u"RIS"),
    ("html", u"HTML"),
    ("xhtml", u"XHTML"),
    ("db31", u"DocBook 3.1"),
    ("db31x", u"DocBook XML 3.1"),
    ("db50", u"DocBook 5.0"),
    ("db50x", u"DocBook XML 3.1"),
    ("teix", u"TEI XML"),
    ("tei5x", u"TEI 5 XML"),
    ("mods", u"MODS"),
    ("bibtex", u"BibTeX"),
    ("rtf", u"RTF")
    )

class ExportForm(forms.Form):
    u"""Form class for exporting references to a particular output format.
    """
    _ = ugettext_lazy
    format = forms.ChoiceField(label=_("Export as"), choices=(("", 9*u"-"),) + output_format_choices, required=False)


class RemoveFromListForm(forms.Form):
    u"""Form class for removing references from a references list.
    """
    _ = ugettext_lazy
    remove = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        verbose_listname = kwargs.pop("verbose_listname", None)
        super(RemoveFromListForm, self).__init__(*args, **kwargs)
        if verbose_listname:
            self.fields["remove"].label = _(u"Remove from list “%s”") % verbose_listname


class AddToShelfForm(forms.Form):
    u"""Form class for adding references to a shelf.
    """
    _ = ugettext_lazy
    new_shelf = forms.ChoiceField(label=_("Add to shelf"), required=False)

    def __init__(self, connection, *args, **kwargs):
        super(AddToShelfForm, self).__init__(*args, **kwargs)
        self.fields["new_shelf"].choices = [("", 9*u"-")] + refdb.get_shelves(connection)


class AddToListForm(forms.Form):
    u"""Form class for adding references to a references list.  The user has
    the option to add to an existing list (only `existing_list` is filled) or
    to a new list (only `new_list` is filled).  He must not give both fields.
    """
    _ = ugettext_lazy
    existing_list = forms.ChoiceField(label=_("List"), required=False)
    new_list = forms.CharField(label=_("New list"), max_length=255, required=False)

    def __init__(self, user, connection, *args, **kwargs):
        u"""Class constructor.

        :Parameters:
          - `user`: current user
          - `connection`: connection to RefDB

        :type user: ``django.contrib.auth.models.User``
        :type connection: ``pyrefdb.Connection``
        """
        super(AddToListForm, self).__init__(*args, **kwargs)
        lists = refdb.get_lists(user, connection)[0]
        self.short_listnames = set(list_[0] for list_ in lists)
        self.fields["existing_list"].choices = [("", 9*"-")] + lists
        self.optional = True

    def clean(self):
        u"""Class clean method which assures that at most one of the fields is
        given.  Additionally, it checks that the name for a new list doesn't
        already exist in the database.
        """
        _ = ugettext
        cleaned_data = self.cleaned_data
        if cleaned_data["existing_list"] and cleaned_data["new_list"]:
            chantal_utils.append_error(self, _(u"You must not give both an existing and a new list."), "new_list")
            del cleaned_data["new_list"], cleaned_data["existing_list"]
        elif not self.optional and not cleaned_data["existing_list"] and not cleaned_data["new_list"]:
            chantal_utils.append_error(self, _(u"You must give either an existing or a new list."), "new_list")
            del cleaned_data["new_list"], cleaned_data["existing_list"]
        elif cleaned_data["new_list"] and cleaned_data["new_list"] in self.short_listnames:
            chantal_utils.append_error(self, _(u"This listname is already given."), "new_list")
            del cleaned_data["new_list"]
        return cleaned_data


@login_required
def search(request, database):
    u"""Searchs for references and presents the search results.  It is a
    GET-only view.

    :Parameters:
      - `request`: the current HTTP Request object
      - `database`: the name of the RefDB database

    :type request: ``HttpRequest``
    :type database: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    # Note that I make a *bound* form here (i.e. no “initial=…”) because I want
    # form validation errors to be displayed immediately.  It may be a “See
    # Other” from the bulk view after a failed validation there, and the user
    # must see the errors after all.  Note that this technique doesn't work
    # anymore as soon as `SearchForm` contains required fields.
    search_form = SearchForm(request.GET)
    return render_to_response("refdb/search.html", {"title": _(u"Search"), "search": search_form, "database": database},
                              context_instance=RequestContext(request))


def add_references_to_list(ids, add_to_list_form, user, connection):
    u"""Add references to a references list.

    :Parameters:
      - `ids`: RefDB IDs of the references to be added
      - `add_to_list_form`: bound and valid form containing the list to be
        added to
      - `user`: current user
      - `connection`: connection to RefDB

    :type ids: list of str
    :type add_to_list_form: ``django.forms.Form``
    :type user: ``django.contrib.auth.models.User``
    :type connection: ``pyrefdb.Connection``
    """
    # add_to_list_form must be bound and valid
    if add_to_list_form.cleaned_data["existing_list"]:
        listname = add_to_list_form.cleaned_data["existing_list"]
    else:
        verbose_name = add_to_list_form.cleaned_data["new_list"]
        listname = defaultfilters.slugify(verbose_name)
    connection.pick_references(ids, listname)
    if add_to_list_form.cleaned_data["new_list"]:
        extended_note = connection.get_extended_notes(":NCK:=%s-%s" % (refdb.get_username(user.id), listname))[0]
        extended_note.set_text_content(verbose_name)
        connection.update_extended_notes(extended_note)


def is_all_valid(export_form, add_to_shelf_form, add_to_list_form, remove_from_list_form, selection_box_forms):
    u"""Checks whether all forms are valid.  This routine guarantees that the
    ``is_valid`` method of all forms is called.

    :Parameters:
      - `export_form`: bound form for exporting references
      - `add_to_shelf_form`: bound form for adding references to a shelf
      - `add_to_list_form`: bound form for adding references to a references
        list
      - `remove_from_list_form`: bound form for removing references form a
        references list; may be ``None`` if the search is not limited to a
        particular references list
      - `selection_box_forms`: bound forms with the selected samples
      - `global_dummy_form`: bound form which contains global error messages
        which occur here
      - `references_list`: the references list the bulk view is limited to

    :type export_form: `ExportForm`
    :type add_to_shelf_form: `AddToShelfForm`
    :type add_to_list_form: `AddToListForm`
    :type remove_from_list_form: `RemoveFromListForm` or
      ``NoneType``
    :type selection_box_forms: list of `SelectionBoxForm`
    :type global_dummy_form: ``django.forms.Form``
    :type references_list: unicode

    :Return:
      whether all forms are valid

    :rtype: bool
    """
    all_valid = export_form.is_valid()
    all_valid = add_to_shelf_form.is_valid() and all_valid
    all_valid = add_to_list_form.is_valid() and all_valid
    all_valid = (remove_from_list_form is None or remove_from_list_form.is_valid()) and all_valid
    all_valid = all([form.is_valid() for form in selection_box_forms]) and all_valid
    return all_valid


def is_referentially_valid(export_form, add_to_shelf_form, add_to_list_form, remove_from_list_form,
                           selection_box_forms, global_dummy_form, references_list):
    u"""Test whether all forms are consistent with each other.  In particular,
    the user must use exactly one of the given forms.  He must not try to
    export references and add them to a shelf at the same time.

    :Parameters:
      - `export_form`: bound form for exporting references
      - `add_to_shelf_form`: bound form for adding references to a shelf
      - `add_to_list_form`: bound form for adding references to a references
        list
      - `remove_from_list_form`: bound form for removing references form a
        references list; may be ``None`` if the search is not limited to a
        particular references list
      - `selection_box_forms`: bound forms with the selected samples
      - `global_dummy_form`: bound form which contains global error messages
        which occur here
      - `references_list`: the references list the bulk view is limited to

    :type export_form: `ExportForm`
    :type add_to_shelf_form: `AddToShelfForm`
    :type add_to_list_form: `AddToListForm`
    :type remove_from_list_form: `RemoveFromListForm` or
      ``NoneType``
    :type selection_box_forms: list of `SelectionBoxForm`
    :type global_dummy_form: ``django.forms.Form``
    :type references_list: unicode

    :Return:
      whether all forms are consistent and obey to the constraints

    :rtype: bool
    """
    referentially_valid = True
    action = None
    actions = []
    if export_form.is_valid() and export_form.cleaned_data["format"]:
        actions.append("export")
    if add_to_shelf_form.is_valid() and add_to_shelf_form.cleaned_data["new_shelf"]:
        actions.append("shelf")
    if add_to_list_form.is_valid() and (
        add_to_list_form.cleaned_data["existing_list"] or add_to_list_form.cleaned_data["new_list"]):
        actions.append("list")
    if references_list and remove_from_list_form.is_valid() and remove_from_list_form.cleaned_data["remove"]:
        actions.append("remove")
    if not actions:
        referentially_valid = False
        if export_form.is_valid() and add_to_shelf_form.is_valid() and add_to_list_form.is_valid() and \
                (not references_list or remove_from_list_form.is_valid()):
            chantal_utils.append_error(global_dummy_form, _(u"You must select an action."))
    elif len(actions) > 1:
        chantal_utils.append_error(global_dummy_form, _(u"You can't do more that one thing at the same time."))
        referentially_valid = False
    else:
        action = actions[0]
    if not any(selection_box_form.is_valid() and selection_box_form.cleaned_data["selected"]
               for selection_box_form in selection_box_forms):
        chantal_utils.append_error(global_dummy_form, _(u"You must select at least one sample."))
        referentially_valid = False
    return referentially_valid, action


class MatchDecider(xapian.MatchDecider):
    u"""Match decider class for limiting a full-text search.  The documents
    (i.e. PDF pages) which are excluded are those that belong to private PDFs
    of other users, or which are excluded by other search parameters.
    """

    def __init__(self, citation_keys, user_hash):
        u"""Class constructor.

        :Parameters:
          - `citation_keys`: citation keys of references which are allowed in
            this search; if ``None``, all references are allowed, i.e. the
            full-text search is the only filter
          - `user_hash`: user hash of the user who performs the search; see
            `utils.get_user_hash`

        :type citation_keys: set of str, or ``NoneType``
        :type user_hash: str
        """
        super(MatchDecider, self).__init__()
        self.citation_keys, self.user_hash = citation_keys, user_hash

    def __call__(self, document):
        u"""Decides whether a Xapian document should be considered a search
        hit.

        :Parameters:
          - `document`: the document to be examined

        :type document: ``xapian.Document``

        :Return:
          whether the document should be included into the list of search hits

        :rtype: bool
        """
        include = document.get_value(0) in self.citation_keys
        include = include and (not document.get_value(2) or document.get_value(2) == self.user_hash)
        return include


def get_full_text_matches(database, full_text_query, offset, limit, match_decider):
    u"""Does the actual full-text search with Xapian.

    :Parameters:
      - `database`: the name of the RefDB database
      - `full_text_query`: the raw query string for the full text search; must
        not be empty
      - `offset`: offset of the returned hits within the complete hits list
      - `limit`: maximal number of returned hits
      - `match_decider`: Xapian match decider object, e.g. for taking the other
        search parameters into account

    :type database: unicode
    :type full_text_query: unicode
    :type offset: int
    :type limit: int
    :type match_decider: `MatchDecider`

    :Return:
      the found matches

    :rtype: ``Xapian.MSet``
    """
    database = xapian.Database(os.path.join("/var/lib/django_refdb_indices", database))
    enquire = xapian.Enquire(database)
#    enquire.set_collapse_key(0)
    query_parser = xapian.QueryParser()
    stemmer = xapian.Stem("english")
    query_parser.set_stemmer(stemmer)
    query_parser.set_database(database)
    query_parser.set_stemming_strategy(xapian.QueryParser.STEM_SOME)
    query = query_parser.parse_query(full_text_query)
    enquire.set_query(query)
    return enquire.get_mset(offset, limit, None, match_decider)


def embed_common_data(request, database):
    u"""Add a ``common_data`` attribute to request, containing various data
    used across the view.  See ``utils.CommonBulkViewData`` for further
    information.  If the GET parameters of the view are invalid, a
    ``RedirectException`` is raised so that the user can see and correct the
    errors.

    :Parameters:
      - `request`: current HTTP request object
      - `database`: the RefDB database name

    :type request: ``HttpRequest``
    :type database: unicode
    """
    search_form = SearchForm(request.GET)
    if not search_form.is_valid():
        raise utils.RedirectException(django.core.urlresolvers.reverse(search, database=database) + "?" +
                                      request.META.get("QUERY_STRING"))
    query_string = search_form.get_query_string(request.user.id)
    full_text_query = search_form.cleaned_data["full_text_query"]
    offset = request.GET.get("offset")
    limit = request.GET.get("limit")
    try:
        offset = int(offset)
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    refdb_connection = refdb.get_connection(request.user, database)
    if full_text_query:
        ids = refdb_connection.get_references(query_string, output_format="ids")
        citation_keys = set(utils.ids_to_citation_keys(refdb_connection, ids).values())
        match_decider = MatchDecider(citation_keys, utils.get_user_hash(request.user.id))
        matches = get_full_text_matches(database, full_text_query, offset, limit, match_decider)
        full_text_matches = dict((match.document.get_value(0), match) for match in matches)
        ids = utils.citation_keys_to_ids(refdb_connection, full_text_matches).values()
        number_of_references = matches.get_matches_lower_bound()
    else:
        ids = refdb_connection.get_references(query_string, output_format="ids", offset=offset, limit=limit)
        number_of_references = refdb_connection.count_references(query_string)
        full_text_matches = None
    words_to_highlight = search_form.extract_words_to_highlight()
    request.common_data = utils.CommonBulkViewData(
        refdb_connection, ids, query_string=query_string, full_text_matches=full_text_matches,
        number_of_references=number_of_references, offset=offset, limit=limit, words_to_highlight=words_to_highlight)


def build_page_links(request):
    u"""Creates the links to all other pages of the same bulk list.

    :Parameters:
      - `request`: current HTTP request object; it must have the
        ``common_data`` attribute, see `utils.CommonBulkViewData`

    :type request: ``HttpRequest``

    :Return:
      link to previous page, link to next page, all page links

    :rtype:
      str, str, list of str
    """

    def build_page_link(new_offset):
        u"""Generate the URL to another page of the current search view.  If
        there are too many search hits, the hits are split on multiple pages
        with their own offsets.  This routine builds the relative URLs to
        them.  Since ``bulk`` is a pure GET view, I just need to make sure that
        all GET parameters survive in the link.

        :Parameters:
          - `new_offset`: search hits offset for the destination page

        :type new_offset: int

        :Return:
          the relative URL to a page with the same GET parameters
        """
        new_query_dict = request.GET.copy()
        new_query_dict["offset"] = new_offset
        # I also set ``limit`` because it may have been adjusted in
        # `get_last_modification_date`
        new_query_dict["limit"] = limit
        return "?" + urlencode(new_query_dict) \
            if 0 <= new_offset < common_data.number_of_references and new_offset != offset else None

    common_data = request.common_data
    offset, limit = common_data.offset, common_data.limit
    prev_link = build_page_link(offset - limit)
    next_link = build_page_link(offset + limit)
    pages = []
    for i in range(common_data.number_of_references // limit + 1):
        link = build_page_link(i * limit)
        pages.append(link)
    return prev_link, next_link, pages
    

def get_last_modification_date(request, database):
    u"""Returns the last modification of the references found for the bulk
    view.  Note that this only includes the actually *displayed* references on
    the current page, not all references from all pages.  Additionally, the
    last modification of user settings (language, current list) is taken into
    account.

    The routine is only used in the ``last_modified`` decorator in `bulk`.

    :Parameters:
      - `request`: current HTTP request object
      - `database`: the name of the RefDB database

    :type request: ``HttpRequest``
    :type database: unicode

    :Return:
      timestamp of last modification of the displayed references

    :rtype: ``datetime.datetime``
    """
    if request.method == "GET":
        embed_common_data(request, database)
        last_modified = utils.last_modified(request.user, request.common_data.refdb_connection, request.common_data.ids)
    else:
        last_modified = None
    if last_modified:
        last_modified = max(last_modified, request.user.chantal_user_details.settings_last_modified)
    return last_modified


@login_required
@last_modified(get_last_modification_date)
def bulk(request, database):
    u"""The bulk view for references.  It gets the search parameters in the
    GET, and displays all references which matches the search parameters.  If
    they are too many, the list is split up into pages where you can navigate
    through.

    I do aggressive caching here.  First, I use the ``@last_modified``
    decorator for making use of the browser cache.  Secondly, I cache all
    references objects requested for later use, including their “extended
    attributes”.  If a second request needs more extended atttibutes, only the
    missing ones are fetched.

    :Parameters:
      - `request`: the current HTTP Request object
      - `database`: the name of the RefDB database

    :type request: ``HttpRequest``
    :type database: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    references_list = request.GET.get("list")
    if references_list:
        verbose_listname = refdb.get_verbose_listname(references_list, request.user)
    if request.method == "POST":
        connection = refdb.get_connection(request.user, database)
        export_form = ExportForm(request.POST)
        add_to_shelf_form = AddToShelfForm(request.POST, connection)
        add_to_list_form = AddToListForm(request.user, connection, request.POST)
        remove_from_list_form = RemoveFromListForm(request.POST, verbose_listname=verbose_listname, prefix="remove") \
            if references_list else None
        global_dummy_form = forms.Form(request.POST)
        ids = set()
        for key, value in request.POST.iteritems():
            id_, dash, name = key.partition("-")
            if name == "selected" and value == "on":
                ids.add(id_)
        selection_box_forms = [SelectionBoxForm(request.POST, prefix=id_) for id_ in ids]
        all_valid = \
            is_all_valid(export_form, add_to_shelf_form, add_to_list_form, remove_from_list_form, selection_box_forms)
        referentially_valid, action = is_referentially_valid(
            export_form, add_to_shelf_form, add_to_list_form, remove_from_list_form, selection_box_forms, global_dummy_form,
            references_list)
        valid_post_data = all_valid and referentially_valid
        if valid_post_data:
            if action == "export":
                query_dict = {"format": export_form.cleaned_data["format"]}
                query_dict.update((id_ + "-selected", "on") for id_ in ids)
                query_string = urlencode(query_dict)
                return chantal_utils.HttpResponseSeeOther(
                    django.core.urlresolvers.reverse("refdb.views.export.export", database=database) + "?" + query_string)
            elif action == "shelf":
                # FixMe: This must be changed from using citation keys to using
                # IDs.  However, first
                # https://sourceforge.net/tracker/?func=detail&aid=2857792&group_id=26091&atid=385991
                # needs to be fixed.
                citation_keys = [reference.citation_key for reference in connection.
                                 get_references(" OR ".join(":ID:=" + id_ for id_ in ids))]
                connection.add_note_links(":NCK:=django-refdb-shelf-" + add_to_shelf_form.cleaned_data["new_shelf"],
                                          u" ".join(":CK:=" + citation_key for citation_key in citation_keys))
            elif action == "list":
                add_references_to_list(ids, add_to_list_form, request.user, connection)
            elif action == "remove":
                connection.dump_references(ids, references_list)
        # Since the POST request is processed now, we create *now* the list
        # itself.  The reason for this is that the references data has changed
        # by processing the request, so we get a fresh list here.  This delayed
        # list generation is the reason for `embed_common_data` and
        # `utils.CommonBulkViewData` in the first place.
        embed_common_data(request, database)
        if not valid_post_data:
            references = utils.fetch_references(request.common_data.refdb_connection, request.common_data.ids, request.user)
            prev_link, next_link, pages = build_page_links(request)
            for reference in references:
                reference.selection_box = SelectionBoxForm(request.POST, prefix=reference.id)
    if request.method == "GET" or valid_post_data:
        references = utils.fetch_references(request.common_data.refdb_connection, request.common_data.ids, request.user)
        prev_link, next_link, pages = build_page_links(request)
        for reference in references:
            reference.selection_box = SelectionBoxForm(prefix=reference.id)
        export_form = ExportForm()
        add_to_shelf_form = AddToShelfForm(request.common_data.refdb_connection)
        add_to_list_form = AddToListForm(request.user, request.common_data.refdb_connection)
        global_dummy_form = forms.Form()
        if references_list:
            remove_from_list_form = RemoveFromListForm(
                initial={"listname": references_list}, verbose_listname=verbose_listname, prefix="remove")
        else:
            remove_from_list_form = None
    if request.common_data.full_text_matches is not None:
        for reference in references:
            reference.full_text_info = request.common_data.full_text_matches[reference.citation_key]
    title = _(u"Bulk view") if not references_list else _(u"List view of %s") % verbose_listname
    return render_to_response("refdb/bulk.html", {"title": title, "references": references,
                                                  "prev_link": prev_link, "next_link": next_link, "pages": pages,
                                                  "add_to_shelf": add_to_shelf_form, "export": export_form,
                                                  "add_to_list": add_to_list_form,
                                                  "remove_from_list": remove_from_list_form,
                                                  "global_dummy": global_dummy_form,
                                                  "words_to_highlight": request.common_data.words_to_highlight,
                                                  "database": database},
                              context_instance=RequestContext(request))
