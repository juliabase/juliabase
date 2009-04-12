#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os.path, shutil, re
import pyrefdb
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404
from django import forms
from django.forms.util import ValidationError, ErrorList
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
import django.contrib.auth.models
from django.conf import settings
from .. import utils


def serialize_authors(authors):
    return u"; ".join(unicode(author) for author in authors)


def de_escape(string):
    return string.replace(u"\x2028", "\n")


def escape(string):
    return string.replace(u"\n", "\x2028")


class EscapedTextField(forms.CharField):

    def clean(self, value):
        return escape(super(EscapedTextField, self).clean(value)) or None


class CharNoneField(forms.CharField):

    def clean(self, value):
        return super(CharNoneField, self).clean(value) or None


class MultipleGroupField(forms.MultipleChoiceField):
    u"""Form field class for the selection of groups.
    """

    def set_groups(self, user, additional_groups=frozenset()):
        u"""Set the group list shown in the widget.  You *must* call this
        method in the constructor of the form in which you use this field,
        otherwise the selection box will remain emtpy.  The selection list will
        consist of all currently active groups, plus the given additional group
        if any.  The “currently active groups” are all groups with at least one
        active user amongst its members.

        :Parameters:
          - `user`: the currently logged-in user
          - `additional_groups`: Optional additional groups to be included into
            the list.  Typically, it is the current groups of the reference,
            for example.

        :type user: ``django.contrib.auth.models.User``
        :type additional_groups: set of ``django.contrib.auth.models.Group``
        """
        all_groups = django.contrib.auth.models.Group.objects.filter(user__is_active=True).distinct()
        user_groups = user.groups.all()
        try:
            is_restricted = settings.restricted_group_test
        except AttributeError:
            is_restricted = lambda x: False
        groups = set(group for group in all_groups if not is_restricted(group) or group in user_groups)
        groups |= additional_groups
        groups = sorted(groups, key=lambda group: group.name)
        self.choices = [(group.pk, unicode(group)) for group in groups] or [(u"", 9*u"-")]

    def clean(self, value):
        value = super(MultipleGroupField, self).clean(value)
        if value:
            return django.contrib.auth.models.Group.objects.get(pk=int(value))


date_pattern = re.compile(r"(\d{4})$|(\d{4})-(\d\d?)-(\d\d?)$")
relevance_pattern = re.compile(r"\*{,4}$")
pages_pattern = re.compile(r"(.+?)(?:--(.+))?")

class ReferenceForm(forms.Form):

    _ = ugettext_lazy
    reference_type = forms.ChoiceField(label=_("Type"), choices=utils.reference_types.items())
    part_title = CharNoneField(label=_("Title"), required=False)
    part_authors = forms.CharField(label=_("Authors"), required=False)
    publication_title = forms.CharField(label=_("Publication title"))
    publication_authors = forms.CharField(label=_("Authors"), required=False)
    date = forms.CharField(label=_("Date"), required=False, help_text=_("Either YYYY or YYYY-MM-DD."))
    relevance = forms.CharField(label=_("Relevance"), required=False)
    volume = CharNoneField(label=_("Volume"), required=False)
    issue = CharNoneField(label=_("Issue"), required=False)
    startpage = CharNoneField(label=_("Start page"), required=False)
    endpage = CharNoneField(label=_("End page"), required=False)
    publisher = CharNoneField(label=_("Publisher"), required=False)
    city = CharNoneField(label=_("City"), required=False)
    address = CharNoneField(label=_("Address"), required=False, help_text=_("Contact address to the author."))
    serial = CharNoneField(label=_("Serial"), required=False)
    doi = CharNoneField(label=_("DOI"), required=False)
    weblink = forms.URLField(label=_("Weblink"), required=False)
    global_notes = EscapedTextField(label=_("Global notes"), required=False, widget=forms.Textarea)
    institute_publication = forms.BooleanField(label=_("Institute publication"), required=False)
    global_reprint_locations = CharNoneField(label=_("Global reprint locations"), required=False)
    abstract = EscapedTextField(label=_("Abstract"), required=False, widget=forms.Textarea)
    keywords = forms.CharField(label=_("Keywords"), required=False)
    private_notes = EscapedTextField(label=_("Private notes"), required=False, widget=forms.Textarea)
    private_reprint_available = forms.BooleanField(label=_("Private reprint available"), required=False)
    private_reprint_location = CharNoneField(label=_("Private reprint location"), required=False)
    lists = forms.MultipleChoiceField(label=_("Lists"), required=False)
    groups = MultipleGroupField(label=_("Groups"), required=False)
    pdf = forms.FileField(label=_(u"PDF file"), required=False)
    pdf_is_private = forms.BooleanField(label=_("PDF is private"), required=False)

    def __init__(self, user, reference, *args, **kwargs):
        initial = kwargs.get("initial") or {}
        lists_choices, lists_initial = utils.get_lists(user, reference.citation_key if reference else None)
        reference_groups = set()
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
            initial["volume"] = pub_info.volume or u""
            initial["issue"] = pub_info.issue or u""
            initial["pages"] = "%s--%s" % (pub_info.startpage, pub_info.endpage) if pub_info.startpage and pub_info.endpage \
                else pub_info.startpage or u""
            initial["publisher"] = pub_info.publisher or u""
            initial["city"] = pub_info.city or u""
            initial["address"] = pub_info.address or u""
            initial["serial"] = pub_info.serial or u""
            initial["doi"] = pub_info.links.get("doi", u"")
            initial["weblink"] = pub_info.links.get("url", u"")
            initial["global_notes"] = de_escape(pub_info.user_defs.get(2, u""))
            initial["institute_publication"] = pub_info.user_defs.get(4) == u"institute publication"
            initial["global_reprint_locations"] = pub_info.links.get("fulltext", u"")
            initial["abstract"] = de_escape(reference.abstract or u"")
            initial["keywords"] = u"; ".join(reference.keywords)
            lib_info = reference.get_lib_info("drefdbuser%d" % user.id)
            if lib_info:
                initial["private_notes"] = de_escape(lib_info.notes or u"")
                initial["private_reprint_available"] = lib_info.reprint_status == "INFILE"
                initial["private_reprint_location"] = lib_info.availability or u""
            initial["lists"] = lists_initial
            group_ids = [int(id_) for id_ in pub_info.user_defs.get(3, u"").split(":")[1:-1]]
            reference_groups = set(django.contrib.auth.models.Group.objects.filter(id__in=group_ids))
            initial["groups"] = group_ids
        kwargs["initial"] = initial
        super(ReferenceForm, self).__init__(*args, **kwargs)
        self.user = user
        self.reference = reference
        self.fields["lists"].choices = lists_choices
        self.old_lists = lists_initial
        self.fields["groups"].set_groups(user, reference_groups)

    def clean_part_authors(self):
        return [pyrefdb.Author(author) for author in self.cleaned_data["part_authors"].split(";")]

    def clean_publication_authors(self):
        return [pyrefdb.Author(author) for author in self.cleaned_data["publication_authors"].split(";")]

    def clean_date(self):
        date_string = self.cleaned_data["date"]
        if date_string:
            date = pyrefdb.Date()
            match = date_pattern.match(date_string)
            if match:
                if match.group(1):
                    date.year = int(match.group(1))
                else:
                    date.year, date.month, date.day = map(int, match.group(2, 3, 4))
                return date
            else:
                raise ValidationError(_(u"Must be either of the form YYYY or YYYY-MM-DD."))

    def clean_relevance(self):
        relevance = self.cleaned_data["relevance"]
        if not relevance_pattern.match(relevance):
            raise ValidationError(_(u"Must be up to four “*”."))
        else:
            return relevance

    def clean_weblink(self):
        return self.cleaned_data["weblink"] or None

    def clean_institute_publication(self):
        return u"institute publication" if self.cleaned_data["institute_publication"] else u"not institute publication"

    def clean_keywords(self):
        return filter(None, [keyword.strip() for keyword in self.cleaned_data["keywords"].split(";")])

    def clean_private_reprint_available(self):
        return u"INFILE" if self.cleaned_data["private_reprint_available"] else u"NOTINFILE"

    def clean_pdf(self):
        pdf_file = self.cleaned_data["pdf"]
        if pdf_file:
            if pdf_file.read(4) != "%PDF":
                raise ValidationError(_(u"The uploaded file was not a PDF file."))
            pdf_file.open()
        return pdf_file

    def clean(self):
        if self.cleaned_data["endpage"] and not self.cleaned_data["startpage"]:
            self._errors["endpage"] = ErrorList([_(u"You must not give an end page if there is no start page.")])
            del self.cleaned_data["endpage"]
        return self.cleaned_data

    def get_reference(self):
        reference = self.reference or pyrefdb.Reference()
        reference.type = self.cleaned_data["reference_type"]
        if self.cleaned_data["part_title"] or self.cleaned_data["part_authors"]:
            if not reference.part:
                reference.part = pyrefdb.Part()
            reference.part.title = self.cleaned_data["part_title"]
            reference.part.authors = self.cleaned_data["part_authors"]
        if not reference.publication:
            reference.publication = pyrefdb.Publication()
        reference.publication.title = self.cleaned_data["publication_title"]
        reference.publication.authors = self.cleaned_data["publication_authors"]
        lib_info = reference.get_or_create_lib_info("drefdbuser%d" % self.user.id)
        lib_info.notes = self.cleaned_data["private_notes"]
        lib_info.reprint_status = "INFILE" if self.cleaned_data["private_reprint_available"] else "NOTINFILE"
        lib_info.availability = self.cleaned_data["private_reprint_location"]
        if not reference.publication.pub_info:
            reference.publication.pub_info = pyrefdb.PubInfo()
        pub_info = reference.publication.pub_info
        pub_info.pub_date = self.cleaned_data["date"]
        pub_info.user_defs[1] = self.cleaned_data["relevance"]
        pub_info.volume = self.cleaned_data["volume"]
        pub_info.issue = self.cleaned_data["issue"]
        pub_info.startpage = self.cleaned_data["startpage"]
        pub_info.endpage = self.cleaned_data["endpage"]
        pub_info.publisher = self.cleaned_data["publisher"]
        pub_info.city = self.cleaned_data["city"]
        pub_info.address = self.cleaned_data["address"]
        pub_info.serial = self.cleaned_data["serial"]
        pub_info.links["doi"] = self.cleaned_data["doi"]
        pub_info.links["url"] = self.cleaned_data["weblink"]
        pub_info.user_defs[2] = self.cleaned_data["global_notes"]
        pub_info.user_defs[4] = self.cleaned_data["institute_publication"]
        pub_info.links["fulltext"] = self.cleaned_data["global_reprint_locations"]
        reference.abstract = self.cleaned_data["abstract"]
        reference.keywords = self.cleaned_data["keywords"]
        pub_info.user_defs[3] = self.cleaned_data["groups"]
        return reference

    def embed_related_information(self, reference, filename):
        if self.cleaned_data["pdf"]:
            lib_info = reference.get_or_create_lib_info("drefdbuser%d" % self.user.id)
            if self.cleaned_data["pdf_is_private"]:
                lib_info.links["pdf"] = \
                    "%sreferences/%s/%s/%s" % (settings.MEDIA_URL, reference.citation_key, self.user.id, filename)
            else:
                reference.publication.pub_info.links["pdf"] = \
                    "%sreferences/%s/%s" % (settings.MEDIA_URL, reference.citation_key, filename)
            lib_info.links["pdf"] = "PRIVATE"
            reference.publication.pub_info.links["pdf"] = "PUBLIC"
            utils.get_refdb_connection(self.user).update_references(reference)

    def save_lists(self, reference):
        for list_ in self.cleaned_data["lists"]:
            if list_ not in self.old_lists:
                listname = list_.partition("-")[2]
                utils.get_refdb_connection(self.user).pick_references([reference.id], listname or None)
        for list_ in self.old_lists:
            if list_ not in self.cleaned_data["lists"]:
                listname = list_.partition("-")[2]
                utils.get_refdb_connection(self.user).dump_references([reference.id], listname or None)

    def save(self):
        old_filename = utils.slugify_reference(self.reference) + ".pdf" if self.reference else None
        new_reference = self.get_reference()
        if self.reference:
            utils.get_refdb_connection(self.user).update_references(new_reference)
        else:
            citation_key = utils.get_refdb_connection(self.user).add_references(new_reference)[0][0]
            new_reference.citation_key = citation_key
        new_filename = utils.slugify_reference(new_reference) + ".pdf"
        rootdir = os.path.join(settings.MEDIA_ROOT, "references", new_reference.citation_key)
        if os.path.exists(rootdir) and old_filename != new_filename:
            for name in os.listdir(rootdir):
                if name == old_filename:
                    shutil.move(os.path.join(rootdir, old_filename), os.path.join(rootdir, new_filename))
                else:
                    path = os.path.join(rootdir, name)
                    if os.path.isdir(path):
                        shutil.move(os.path.join(path, old_filename), os.path.join(path, new_filename))
        pdf_file = self.cleaned_data["pdf"]
        if pdf_file:
            directory = rootdir
            if self.cleaned_data["pdf_is_private"]:
                directory = os.path.join(directory, str(self.user.id))
            if not os.path.exists(directory):
                os.makedirs(directory)
            destination = open(os.path.join(directory, new_filename), "wb+")
            for chunk in pdf_file.chunks():
                destination.write(chunk)
            destination.close()
        self.embed_related_information(new_reference, new_filename)
        self.save_lists(new_reference)


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
        reference_form = ReferenceForm(request.user, reference, request.POST, request.FILES)
        if reference_form.is_valid():
            reference_form.save()
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
    else:
        reference = reference[0]
        lib_info = reference.get_lib_info("drefdbuser%d" % request.user.id)
    pdf_path = lib_info and lib_info.links.get("pdf")
    print repr(pdf_path)
    if pdf_path:
        pdf_is_private = True
    else:
        pdf_is_private = False
        pdf_path = reference.publication.pub_info and reference.publication.pub_info.links.get("pdf")
    return render_to_response("show_reference.html", {"title": _(u"View reference"),
                                                      "reference": reference, "lib_info": lib_info,
                                                      "pdf_path": pdf_path, "pdf_is_private": pdf_is_private},
                              context_instance=RequestContext(request))
