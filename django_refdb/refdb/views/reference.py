#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pyrefdb
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from .. import utils


def serialize_authors(authors):
    return u"; ".join(unicode(author) for author in authors)


def parse_authors(serialized_authors):
    authors = []
    for serialized_author in serialized_authors.split(";"):
        author = pyrefdb.Author()
        parts = [part.strip() for part in serialized_author.split(",")]
        author.lastname = parts[0]
        if len(parts) > 1:
            first_and_middlenames = []
            for name in parts[1].split():
                abbreviated_names = name.split(".")
                abbreviated_names[:-1] = [name + u"." for name in abbreviated_names[:-1]]
                if abbreviated_names[-1] == ".":
                    del abbreviated_names[-1]
                first_and_middlenames.extend(abbreviated_names)
            if first_and_middlenames:
                author.firstname = first_and_middlenames[0]
            author.middlenames = first_and_middlenames[1:]
            if len(parts) == 3:
                author.suffix = parts[2]
        authors.append(author)
    return authors


def de_escape(string):
    return string.replace(u"\x2028", "\n")


def escape(string):
    return string.replace(u"\n", "\x2028")


class ReferenceForm(forms.Form):

    _ = ugettext_lazy
    reference_type = forms.ChoiceField(label=_("Type"), choices=utils.reference_types.items())
    part_title = forms.CharField(label=_("Title"), required=False)
    part_authors = forms.CharField(label=_("Authors"), required=False)
    publication_title = forms.CharField(label=_("Publication title"))
    publication_authors = forms.CharField(label=_("Authors"), required=False)
    date = forms.CharField(label=_("Date"), required=False, help_text=_("Either YYYY or YYYY-MM-DD."))
    relevance = forms.CharField(label=_("Relevance"), required=False)
    pdf = forms.CharField(label=_("PDF"), required=False, help_text=_("Relative link."))
    volume = forms.CharField(label=_("Volume"), required=False)
    issue = forms.CharField(label=_("Issue"), required=False)
    pages = forms.CharField(label=_("Pages"), required=False, help_text=_("Either PPP or AAA-EEE."))
    publisher = forms.CharField(label=_("Publisher"), required=False)
    city = forms.CharField(label=_("City"), required=False)
    address = forms.CharField(label=_("Address"), required=False, help_text=_("Contact address to the author."))
    serial = forms.CharField(label=_("Serial"), required=False)
    doi = forms.CharField(label=_("DOI"), required=False)
    weblink = forms.URLField(label=_("Weblink"), required=False)
    global_notes = forms.CharField(label=_("Global notes"), required=False, widget=forms.Textarea)
    institute_publication = forms.BooleanField(label=_("Institute publication"), required=False)
    global_reprint_locations = forms.CharField(label=_("Global reprint locations"), required=False)
    abstract = forms.CharField(label=_("Abstract"), required=False, widget=forms.Textarea)
    keywords = forms.CharField(label=_("Keywords"), required=False)
    private_notes = forms.CharField(label=_("Private notes"), required=False, widget=forms.Textarea)
    private_reprint_available = forms.BooleanField(label=_("Private reprint available"), required=False)
    private_reprint_location = forms.CharField(label=_("Private reprint location"), required=False)
    lists = forms.MultipleChoiceField(label=_("Lists"))

    def __init__(self, user, reference, *args, **kwargs):
        initial = kwargs.get("initial") or {}
        lists_choices, lists_initial = utils.get_lists(user, reference.citation_key if reference else None)
        print lists_choices, lists_initial
        if reference:
            initial["reference_type"] = reference.type
            if reference.part:
                initial["part_title"] = reference.part.title
                initial["part_authors"] = serialize_authors(reference.part.authors)
            initial["publication_title"] = reference.publication.title
            initial["publication_authors"] = serialize_authors(reference.publication.authors)
            pub_info = reference.publication.pub_info
            initial["date"] = unicode(pub_info.pub_date or u"")
            initial["relevance"] = pub_info.user_defs.get(1, u"")
            initial["pdf"] = pub_info.links.get("pdf", u"")
            initial["volume"] = pub_info.volume or u""
            initial["issue"] = pub_info.issue or u""
            initial["pages"] = "%s-%s" % (pub_info.startpage, pub_info.endpage) if pub_info.startpage and pub_info.endpage \
                else pub_info.startpage or u""
            initial["publisher"] = pub_info.publisher or u""
            initial["city"] = pub_info.city or u""
            initial["address"] = pub_info.address or u""
            initial["serial"] = pub_info.serial or u""
            initial["doi"] = pub_info.links.get("doi", u"")
            initial["weblink"] = pub_info.links.get("url", u"")
            initial["global_notes"] = de_escape(pub_info.user_defs.get(2, u""))
            initial["institute_publication"] = pub_info.user_defs.get(4) == u"1"
            initial["global_reprint_locations"] = pub_info.links.get("fulltext", u"")
            initial["abstract"] = de_escape(reference.abstract or u"")
            initial["keywords"] = u"; ".join(reference.keywords)
            if reference.lib_infos:
                lib_info = reference.lib_infos[0]
                initial["private_notes"] = de_escape(lib_info.notes)
                initial["private_reprint_available"] = lib_info.reprint_status == "IN FILE"
                initial["private_reprint_location"] = lib_info.availability or u""
            initial["lists"] = lists_initial
        kwargs["initial"] = initial
        super(ReferenceForm, self).__init__(*args, **kwargs)
        self.fields["lists"].choices = lists_choices
        self.old_lists = lists_initial


@login_required
def edit(request, citation_key):
    if citation_key:
        reference = utils.get_refdb_connection(request.user).get_references(":CK:=" + citation_key)
        if not reference:
            raise Http404("Citation key \"%s\" not found." % citation_key)
        else:
            reference = reference[0]
    else:
        reference = None
    if request.method == "POST":
        reference_form = ReferenceForm(request.user, reference, request.POST)
    else:
        reference_form = ReferenceForm(request.user, reference)
    title = _(u"Edit reference") if citation_key else _(u"Add reference")
    return render_to_response("edit_reference.html", {"title": title, "reference": reference_form},
                              context_instance=RequestContext(request))


@login_required
def view(request, citation_key):
    reference = utils.get_refdb_connection(request.user).get_references(":CK:=" + citation_key)
    if not reference:
        raise Http404("Citation key \"%s\" not found." % citation_key)
    return render_to_response("show_reference.html", {"title": _(u"View reference"), "body": reference[0]},
                              context_instance=RequestContext(request))
