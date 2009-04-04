#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os.path, shutil
import pyrefdb
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404
from django import forms
from django.forms.util import ValidationError
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
import django.contrib.auth.models
from django.conf import settings
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


class ReferenceForm(forms.Form):

    _ = ugettext_lazy
    reference_type = forms.ChoiceField(label=_("Type"), choices=utils.reference_types.items())
    part_title = forms.CharField(label=_("Title"), required=False)
    part_authors = forms.CharField(label=_("Authors"), required=False)
    publication_title = forms.CharField(label=_("Publication title"))
    publication_authors = forms.CharField(label=_("Authors"), required=False)
    date = forms.CharField(label=_("Date"), required=False, help_text=_("Either YYYY or YYYY-MM-DD."))
    relevance = forms.CharField(label=_("Relevance"), required=False)
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

    def clean_pdf(self):
        pdf_file = self.cleaned_data["pdf"]
        if pdf_file:
            if pdf_file.read(4) != "%PDF":
                raise ValidationError(_(u"The uploaded file was not a PDF file."))
            pdf_file.open()
        return pdf_file

    def get_reference(self):
        reference = self.reference or pyrefdb.Reference()
        reference.type = self.cleaned_data["reference_type"]

        return reference

    def save(self):
        old_filename = utils.slugify_reference(self.reference) + ".pdf" if self.reference else None
        new_reference = self.get_reference()
        if self.reference:
            utils.get_refdb_connection(self.user).update_references([new_reference])
        else:
            utils.get_refdb_connection(self.user).add_references([new_reference])
        new_filename = utils.slugify_reference(new_reference) + ".pdf"
        rootdir = os.path.join(settings.MEDIA_ROOT, "references", new_reference.id)
        if os.path.exists(rootdir) and old_filename != new_filename:
            for name in os.listdir(rootdir):
                if name == old_filename:
                    shutil.move(os.path.join(rootdir, old_filename), os.path.join(rootdir, new_filename))
                else:
                    path = os.path.join(rootdir, name)
                    if os.path.isdir(path):
                        shutil.move(os.path.join(path, old_filename), os.path.join(path, new_filename))
        pdf_file = self.cleaned_data.get("pdf")
        if pdf_file:
            path_components = [rootdir, new_filename]
            if self.cleaned_data["pdf_is_private"]:
                path_components.insert(1, str(self.user.pk))
            destination = open(os.path.join(*path_components), "wb+")
            for chunk in pdf_file.chunks():
                destination.write(chunk)
        destination.close()


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
    return render_to_response("show_reference.html", {"title": _(u"View reference"), "body": reference[0]},
                              context_instance=RequestContext(request))
