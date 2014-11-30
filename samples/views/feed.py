#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Generating an Atom 1.0 feed with the user's news.
"""

from __future__ import absolute_import, unicode_literals

import datetime, time
import xml.etree.ElementTree as ElementTree
import django.contrib.auth.models
from django.template import Context, loader
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.cache import cache_page
from jb_common.utils import get_really_full_name
from jb_common import __version__
from samples import permissions, models
from django.conf import settings
import django.core.urlresolvers
from samples.views import utils


def indent(elem, level=0):
    """Indent a given ElementTree in-place by added whitespace so that it looks
    nicer in the flattened output.  Taken from the ElementTree webseite.  This
    routine may be embedded directly into ElementTree in a future version of
    it.

    :Parameters:
      - `elem`: the root element of an ElementTree tree
      - `level`: the indentation level of the root element, in numbers of space
        characters.

    :type elem: xml.etree.ElementTree.Element
    :type level: int

    :Return:
      The same tree but with added whitespace in its ``text`` and ``tail``
      attributes.

    :rtype: xml.etree.ElementTree.Element
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def get_timezone_string(timestamp=None):
    """Claculate the timezone string (e.g. ``"+02:00"``) for a given point in
    time for the local machine.  Believe it or not, Python makes it really hard
    to deal with dates timezone-independently.  Thus, the given timestamp must
    refer to the local machine's timezone.  If you omit it, the routine assumes
    the current time.  The routine takes into account the summer time.

    It returns a string that can be used directly in timestamp string, like
    ``"+02:00"`` or ``"Z"``.  It can also deal with timezones with a difference
    to GMT which is not only whole hours.

    :Parameters:
      - `timestamp`: the point in time for which the timezome should be
        calculated

    :type timestamp: ``datetime.datetime`` or ``NoneType``

    :Return:
      the timezone information string, ready for being appended to a timestamp
      string

    :rtype: str
    """
    if not timestamp:
        timestamp = time.mktime(time.localtime())
    elif isinstance(timestamp, datetime.datetime):
        timestamp = time.mktime(timestamp.timetuple())
    timedelta = datetime.timedelta(seconds=timestamp - time.mktime(time.gmtime(timestamp)[:8] + (-1,)))
    seconds = timedelta.days * 24 * 3600 + timedelta.seconds
    if abs(seconds) < 60:
        return "Z"
    sign = "-" if seconds < 0 else "+"
    seconds = abs(seconds)
    hours = seconds // 3600
    minutes = (seconds - hours * 3600) // 60
    return "{0}{1:02}:{2:02}".format(sign, hours, minutes)


def format_timestamp(timestamp):
    """Convert a timestamp to an Atom-1.0-compatible string.

    :Parameters:
      - `timestamp`: the timestamp to be converted

    :type timestamp: ``datetime.datetime``

    :Return:
      the timestamp string, ready for use in an Atom feed

    :rtype: str
    """
    return timestamp.strftime("%Y-%m-%dT%H:%M:%S") + get_timezone_string(timestamp)


@cache_page(600)
def show(request, username, user_hash):
    """View which doesn't generate an HTML page but an Atom 1.0 feed with
    current news for the user.

    The problem we have to deal with here is that the feed-reading program
    cannot login.  Therefore, it must be possible to fetch the feed without
    being logged-in.  The username is no problem, it is part of the path.
    Additionally, a secret hash (see `permissions.get_user_hash`) is appended
    to the URL in the query string.  This should be enough security for this
    purpose.

    :Parameters:
      - `request`: the current HTTP Request object
      - `username`: the login name of the user for whic the news should be
        delivered
      - `user_hash`: the secret user hash, which works as an ersatz password
        because the feed clients can't login.

    :type request: ``HttpRequest``
    :type username: str
    :type user_hash: str

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    permissions.assert_can_view_feed(user_hash, user)
    feed_absolute_url = request.build_absolute_uri(django.core.urlresolvers.reverse(
        show, kwargs={"username": username, "user_hash": user_hash}))
    feed = ElementTree.Element("feed", xmlns="http://www.w3.org/2005/Atom")
    feed.attrib["xml:base"] = request.build_absolute_uri("/")
    ElementTree.SubElement(feed, "id").text = feed_absolute_url
    ElementTree.SubElement(feed, "title").text = \
        _("JuliaBase news for {user_name}").format(user_name=get_really_full_name(user))
    entries = [entry.actual_instance for entry in user.feed_entries.all()]
    if entries:
        ElementTree.SubElement(feed, "updated").text = format_timestamp(entries[0].timestamp)
    else:
        ElementTree.SubElement(feed, "updated").text = format_timestamp(datetime.datetime.now())
    author = ElementTree.SubElement(feed, "author")
    if settings.ADMINS:
        ElementTree.SubElement(author, "name").text, ElementTree.SubElement(author, "email").text = settings.ADMINS[0]
    ElementTree.SubElement(feed, "link", rel="self", href=feed_absolute_url)
    ElementTree.SubElement(feed, "generator", version=__version__).text = "JuliaBase"
    ElementTree.SubElement(feed, "icon").text = request.build_absolute_uri("/media/juliabase/juliabase_logo.png")
    only_important = user.samples_user_details.only_important_news
    for entry in entries:
        if only_important and not entry.important:
            continue
        if isinstance(entry, (models.FeedNewSamples, models.FeedMovedSamples, models.FeedCopiedMySamples,
                              models.FeedEditedSamples)):
            # Remove orphaned entries (i.e. whose samples have been deleted)
            # because they are a) phony and b) cause tracebacks.
            if entry.samples.count() == 0:
                entry.delete()
                continue
        entry_element = ElementTree.SubElement(feed, "entry")
        ElementTree.SubElement(entry_element, "id").text = \
            "tag:{0},{1}:{2}".format(request.build_absolute_uri("/"), entry.timestamp.strftime("%Y-%m-%d"), entry.sha1_hash)
        metadata = entry.get_metadata()
        ElementTree.SubElement(entry_element, "title").text = metadata["title"]
        ElementTree.SubElement(entry_element, "updated").text = format_timestamp(entry.timestamp)
        author = ElementTree.SubElement(entry_element, "author")
        ElementTree.SubElement(author, "name").text = get_really_full_name(entry.originator)
        if entry.originator.email:
            ElementTree.SubElement(author, "email").text = entry.originator.email
        category = ElementTree.SubElement(
            entry_element, "category", term=metadata["category term"], label=metadata["category label"])
        if "link" in metadata:
            ElementTree.SubElement(entry_element, "link", rel="alternate", href=request.build_absolute_uri(metadata["link"]))
        else:
            # Add bogus <link> tags for Thunderbird, see
            # https://bugzilla.mozilla.org/show_bug.cgi?id=297569
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            if user_agent.startswith("Mozilla") and "Thunderbird" in user_agent:
                ElementTree.SubElement(
                    entry_element, "link", rel="alternate",
                    href=request.build_absolute_uri(django.core.urlresolvers.reverse("samples.views.main.main_menu")))
        template = loader.get_template("samples/" + utils.camel_case_to_underscores(entry.__class__.__name__) + ".html")
        content = ElementTree.SubElement(entry_element, "content")
        context_dict = {"entry": entry}
        context_dict.update(entry.get_additional_template_context(user))
        content.text = template.render(Context(context_dict))
        content.attrib["type"] = "html"
#    indent(feed)
    return HttpResponse("""<?xml version="1.0"?>\n<?xml-stylesheet type="text/xsl" href="/media/samples/xslt/atom2html.xslt"?>\n"""
                        + ElementTree.tostring(feed, "utf-8").decode("utf-8"),
                        content_type="application/xml; charset=utf-8")
