#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import hashlib
import pyrefdb
from django.conf import settings
from django.utils.translation import ugettext_lazy as _


def get_refdb_password(user):
    user_hash = hashlib.sha1()
    user_hash.update(settings.SECRET_KEY)
    user_hash.update(str(user.id))
    return user_hash.hexdigest()[:10]


def get_refdb_connection(user):
    return pyrefdb.Connection("drefdbuser%d" % user.id, get_refdb_password(user))


def get_lists(user, citation_key=None):
    extended_notes = get_refdb_connection(user).get_extended_notes(":NID:>0")
    choices = []
    initial = []
    refdb_username = "drefdbuser%d" % user.id
    for note in extended_notes:
        title = note.find("title").text
        if title and title.startswith(refdb_username + u"-"):
            short_name = title[len(refdb_username)+1:]
            verbose_name = note.findtext("content") or short_name
            if verbose_name == refdb_username:
                verbose_name = _(u"main list")
            choices.append((short_name, verbose_name))
            if citation_key:
                for link in note.findall("link"):
                    if link.attrib["type"] == "reference" and link.attrib["target"] == citation_key:
                        initial.append(short_name)
                        break
    return choices, initial


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
