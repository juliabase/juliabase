#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import hashlib, re
import pyrefdb
from django.conf import settings
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext as _
import django.contrib.auth.models
from . import models


class RefDBRollback(object):

    def __init__(self, user):
        self.user = user

    def execute(self):
        raise NotImplementedError


class PickrefRollback(RefDBRollback):

    def __init__(self, user, reference_id, list_name):
        super(PickrefRollback, self).__init__(user)
        self.reference_id, self.list_name = reference_id, list_name

    def execute(self):
        get_refdb_connection(self.user).pick_references([self.reference_id], self.list_name)


class DumprefRollback(RefDBRollback):

    def __init__(self, user, reference_id, list_name):
        super(DumprefRollback, self).__init__(user)
        self.reference_id, self.list_name = reference_id, list_name or None

    def execute(self):
        get_refdb_connection(self.user).dump_references([self.reference_id], self.list_name)


class UpdaterefRollback(RefDBRollback):

    def __init__(self, user, reference):
        super(UpdaterefRollback, self).__init__(user)
        self.reference = reference

    def execute(self):
        get_refdb_connection(self.user).update_references(self.reference)


class DeleterefRollback(RefDBRollback):

    def __init__(self, user, citation_key):
        super(UpdaterefRollback, self).__init__(user)
        self.reference_id = get_refdb_connection(self.user).get_references(":CK:=" + citation_key, "ids")[0]

    def execute(self):
        get_refdb_connection(self.user).delete_references([self.reference_id])


class AddnoteRollback(RefDBRollback):

    def __init__(self, user, extended_note):
        super(AddnoteRollback, self).__init__(user)
        self.extended_note = extended_note

    def execute(self):
        get_refdb_connection(self.user).add_extended_notes(self.extended_note)


class DeletenoteRollback(RefDBRollback):

    def __init__(self, user, note_citation_key):
        super(DeletenoteRollback, self).__init__(user)
        self.note_citation_key = note_citation_key

    def execute(self):
        extended_note = get_refdb_connection(self.user).get_extended_notes(":NCK:=" + self.note_citation_key,
                                                                           only_of_current_user=True)[0]
        get_refdb_connection(self.user).delete_extended_notes([extended_note.id])


class UpdatenoteRollback(RefDBRollback):

    def __init__(self, user, extended_note):
        super(UpdatenoteRollback, self).__init__(user)
        self.extended_note = extended_note

    def execute(self):
        get_refdb_connection(self.user).update_extended_notes(self.extended_note)


class LinknoteRollback(RefDBRollback):

    def __init__(self, user, note_citation_key, reference_citation_key):
        super(LinknoteRollback, self).__init__(user)
        self.note_citation_key, self.reference_citation_key = note_citation_key, reference_citation_key

    def execute(self):
        get_refdb_connection(self.user).add_note_links(":NCK:=" + self.note_citation_key,
                                                       ":CK:=" + self.reference_citation_key)


class UnlinknoteRollback(RefDBRollback):

    def __init__(self, user, note_citation_key, reference_citation_key):
        super(UnlinknoteRollback, self).__init__(user)
        self.note_citation_key, self.reference_citation_key = note_citation_key, reference_citation_key

    def execute(self):
        get_refdb_connection(self.user).remove_note_links(":NCK:=" + self.note_citation_key,
                                                          ":CK:=" + self.reference_citation_key)


def get_refdb_password(user):
    user_hash = hashlib.sha1()
    user_hash.update(settings.SECRET_KEY)
    user_hash.update(str(user.id))
    return user_hash.hexdigest()[:10]


def refdb_username(user_id):
    return settings.REFDB_USERNAME_PREFIX + str(user_id)


def get_refdb_connection(user):
    return pyrefdb.Connection(refdb_username(user.id), get_refdb_password(user))


def get_lists(user, citation_key=None):
    username = refdb_username(user.id)
    extended_notes = get_refdb_connection(user).get_extended_notes(":NCK:~^%s-" % username)
    choices = []
    initial = []
    for note in extended_notes:
        short_name = note.attrib["citekey"].partition("-")[2]
        if short_name:
            verbose_name = note.findtext("content") or short_name
            if verbose_name == username:
                verbose_name = _(u"main list")
            choices.append((short_name, verbose_name))
            if citation_key:
                for link in note.findall("link"):
                    if link.attrib["type"] == "reference" and link.attrib["target"] == citation_key:
                        initial.append(short_name)
                        break
    return choices, initial


def slugify_reference(reference):
    if reference.part and reference.part.authors:
        authors = reference.part.authors
    else:
        authors = reference.publication.authors
    author = authors[0] if authors else u""
    name = author.lastname or author.name
    if len(authors) > 1:
        name += u" et al"
    name = name.replace(" ", "_")
    if reference.part and reference.part.title:
        title = reference.part.title
    else:
        title = reference.publication.title or u""
    try:
        year = reference.publication.pub_info.pub_date.year
        year = str(year) if year is not None else u""
    except AttributeError:
        year = u""
    title = title.replace(" ", "_")
    return u"%s--%s--%s" % (slugify(name), slugify(year), slugify(title[:50]))


reference_types = {
    "ABST": _(u"abstract reference"),
    "ADVS": _(u"audiovisual material"),
    "ART": _(u"art work"),
    "BILL": _(u"bill/resolution"),
    "BOOK": _(u"whole book reference"),
    "CASE": _(u"case"),
    "CHAP": _(u"book chapter reference"),
    "COMP": _(u"computer program"),
    "CONF": _(u"conference proceeding"),
    "CTLG": _(u"catalog"),
    "DATA": _(u"data file"),
    "ELEC": _(u"electronic citation"),
    "GEN": _(u"generic"),
    "ICOMM": _(u"internet communication"),
    "INPR": _(u"in press reference"),
    "JFULL": _(u"journal – full"),
    "JOUR": _(u"journal reference"),
    "MAP": _(u"map"),
    "MGZN": _(u"magazine article"),
    "MPCT": _(u"motion picture"),
    "MUSIC": _(u"music score"),
    "NEWS": _(u"newspaper"),
    "PAMP": _(u"pamphlet"),
    "PAT": _(u"patent"),
    "PCOMM": _(u"personal communication"),
    "RPRT": _(u"report"),
    "SER": _(u"serial – book, monograph"),
    "SLIDE": _(u"slide"),
    "SOUND": _(u"sound recording"),
    "STAT": _(u"statute"),
    "THES": _(u"thesis/dissertation"),
    "UNBILL": _(u"unenacted bill/resolution"),
    "UNPB": _(u"unpublished work reference"),
    "VIDEO": _(u"video recording")}


class ExtendedData(object):

    def __init__(self):
        self.groups = set()
        self.global_pdf_available = False
        self.users_with_offprint = set()
        self.relevance = None
        self.comments = None
        self.users_with_personal_pdfs = set()
        self.creator = None

    def set_comments(self, comments):
        if not self.comments:
            self.comments = pyrefdb.XNote()
            self.comments.content = ElementTree.Element("content")
        self.comments.content.text = comments


citation_key_pattern = re.compile(r"""django-refdb-(?:
                                   group-(?P<group_id>\d+) |
                                   (?P<global_pdfs>global-pdfs) |
                                   offprints-(?P<user_id_with_offprint>\d+) |
                                   relevance-(?P<relevance>\d+) |
                                   comments-(?P<comment_ck>.+) |
                                   personal-pdfs-(?P<user_id_with_personal_pdf>\d+) |
                                   creator-(?P<creator_id>\d+) |
                                  )$""", re.VERBOSE)


def get_user(user_id, extended_note):
    try:
        return django.contrib.auth.models.User.objects.get(pk=int(user_id))
    except django.contrib.auth.models.User.DoesNotExist:
        # FixMe: Delete this extended note without making it rollback-able
        pass
    

def get_group(group_id, extended_note):
    try:
        return django.contrib.auth.models.Group.objects.get(pk=int(group_id))
    except django.contrib.auth.models.Group.DoesNotExist:
        # FixMe: Delete this extended note without making it rollback-able
        pass
    

def embed_extended_data(references):
    for reference in references:
        reference.extended_data = ExtendedData()
        for extended_note in reference.extended_notes:
            match = citation_key_pattern.match(extended_note.citation_key)
            if match:
                group_id, global_pdfs, user_id_with_offprint, relevance, \
                    comment_ck, user_id_with_personal_pdf, creator_id = match.groups()
                if group_id:
                    reference.extended_data.groups.add(get_group(group_id))
                elif global_pdfs:
                    reference.extended_data.global_pdf_available = True
                elif user_id_with_offprint:
                    reference.extended_data.users_with_offprint.add(get_user(user_id_with_offprint))
                elif relevance:
                    self.relevance = int(relevance)
                elif comment_ck:
                    self.comments = extended_note
                elif user_id_with_personal_pdf:
                    reference.extended_data.users_with_personal_pdfs.add(get_user(user_id_with_personal_pdf))
                elif creator_id:
                    reference.extended_data.creator = get_user(creator_id)
