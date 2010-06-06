#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Generating an Atom 1.0 feed with the user's news.
"""

from __future__ import absolute_import

import datetime, time
import xml.etree.ElementTree as ElementTree
import django.contrib.auth.models
from django.template import Context, loader
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.cache import cache_page
from chantal_common.utils import get_really_full_name
from samples import permissions
from django.conf import settings
import django.core.urlresolvers
from samples.views import utils


if settings.WITH_EPYDOC:
    cache_page = lambda x: lambda y: y


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
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def get_timezone_string(timestamp=None):
    u"""Claculate the timezone string (e.g. ``"+02:00"``) for a given point in
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
    seconds = timedelta.days*24*3600 + timedelta.seconds
    if abs(seconds) < 60:
        return "Z"
    sign = "-" if seconds < 0 else "+"
    seconds = abs(seconds)
    hours = seconds // 3600
    minutes = (seconds-hours*3600) // 60
    return "%s%02d:%02d" % (sign, hours, minutes)


def format_timestamp(timestamp):
    u"""Convert a timestamp to an Atom-1.0-compatible string.

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
    u"""View which doesn't generate an HTML page but an Atom 1.0 feed with
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
    url_prefix = "http://" + settings.DOMAIN_NAME
    feed_absolute_url = url_prefix + django.core.urlresolvers.reverse(show,
                                                                      kwargs={"username": username, "user_hash": user_hash})
    feed = ElementTree.Element("feed", xmlns="http://www.w3.org/2005/Atom")
    ElementTree.SubElement(feed, "id").text = feed_absolute_url
    ElementTree.SubElement(feed, "title").text = _(u"Chantal news for %s") % get_really_full_name(user)
    user_details = utils.get_profile(user)
    entries = [entry.find_actual_instance() for entry in user_details.feed_entries.all()]
    if entries:
        ElementTree.SubElement(feed, "updated").text = format_timestamp(entries[0].timestamp)
    else:
        ElementTree.SubElement(feed, "updated").text = format_timestamp(datetime.datetime.now())
    author = ElementTree.SubElement(feed, "author")
    ElementTree.SubElement(author, "name").text = "Torsten Bronger"
    ElementTree.SubElement(author, "email").text = "bronger@physik.rwth-aachen.de"
    ElementTree.SubElement(feed, "link", rel="self", href=feed_absolute_url+"?hash="+user_hash)
    ElementTree.SubElement(feed, "generator", version="1.0").text = "Chantal"
    ElementTree.SubElement(feed, "icon").text = url_prefix + "/media/ipv/sonne.png"
    ElementTree.SubElement(feed, "logo").text = url_prefix + "/media/ipv/juelich.png"
    only_important = user_details.only_important_news
    for entry in entries:
        if only_important and not entry.important:
            continue
        entry_element = ElementTree.SubElement(feed, "entry")
        ElementTree.SubElement(entry_element, "id").text = \
            "tag:%s,%s:%s" % (settings.DOMAIN_NAME, entry.timestamp.strftime("%Y-%m-%d"), entry.sha1_hash)
        metadata = entry.get_metadata()
        ElementTree.SubElement(entry_element, "title").text = metadata["title"]
        ElementTree.SubElement(entry_element, "updated").text = format_timestamp(entry.timestamp)
        author = ElementTree.SubElement(entry_element, "author")
        ElementTree.SubElement(author, "name").text = get_really_full_name(entry.originator)
        ElementTree.SubElement(author, "email").text = entry.originator.email
        category = ElementTree.SubElement(
            entry_element, "category", term=metadata["category term"], label=metadata["category label"])
        if "link" in metadata:
            ElementTree.SubElement(entry_element, "link", rel="alternate", href=metadata["link"])
        else:
            # Add bogus <link> tags for Thunderbird, see
            # https://bugzilla.mozilla.org/show_bug.cgi?id=297569
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            if user_agent.startswith("Mozilla") and "Thunderbird" in user_agent:
                ElementTree.SubElement(
                    entry_element, "link", rel="alternate",
                    href=django.core.urlresolvers.reverse("samples.views.main.main_menu"))
        template = loader.get_template("samples/" + utils.camel_case_to_underscores(entry.__class__.__name__) + ".html")
        content = ElementTree.SubElement(entry_element, "content")
        context_dict = {"entry": entry}
        context_dict.update(entry.get_additional_template_context(user_details))
        content.text = template.render(Context(context_dict))
        content.attrib["type"] = "html"
#    indent(feed)
    return HttpResponse(ElementTree.tostring(feed,"utf-8"), content_type="application/atom+xml; charset=utf-8")
