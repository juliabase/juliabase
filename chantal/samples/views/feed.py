#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime, time
import xml.etree.ElementTree as ElementTree
import django.contrib.auth.models
from django.template import Context, loader
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal.samples import models
from django.conf import settings
import django.core.urlresolvers
from . import utils

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
    # timestamp must be local time
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
    return timestamp.strftime("%Y-%m-%dT%H:%M:%S") + get_timezone_string(timestamp)

def show(request, username):
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    try:
        user_hash = utils.parse_query_string(request)["hash"]
    except KeyError:
        raise Http404(_(u"You must add a \"hash\" parameter to the query string."))
    if user_hash != utils.get_user_hash(user):
        return utils.HttpResponseSeeOther("permission_error")

    feed_absolute_url = \
        "http://" + settings.DOMAIN_NAME + django.core.urlresolvers.reverse(show, kwargs={"username": username})
    feed = ElementTree.Element("feed", xmlns="http://www.w3.org/2005/Atom")
    ElementTree.SubElement(feed, "id").text = feed_absolute_url
    ElementTree.SubElement(feed, "title").text = _(u"Chantal news for %s") % models.get_really_full_name(user)
    ElementTree.SubElement(feed, "updated").text = format_timestamp(datetime.datetime.now())
    author = ElementTree.SubElement(feed, "author")
    ElementTree.SubElement(author, "name").text = "Torsten Bronger"
    ElementTree.SubElement(author, "email").text = "bronger@physik.rwth-aachen.de"
    ElementTree.SubElement(feed, "link", rel="self", href=feed_absolute_url+"?hash="+user_hash)
    ElementTree.SubElement(feed, "generator", version="1.0").text = "Chantal"
    ElementTree.SubElement(feed, "icon").text = "/media/sonne.png"
    ElementTree.SubElement(feed, "logo").text = "/media/juelich.png"
    entries = [entry.find_actual_instance() for entry in models.FeedEntry.objects.filter(user=user).all()]
    for entry in entries:
        entry_element = ElementTree.SubElement(feed, "entry")
        ElementTree.SubElement(entry_element, "id").text = \
            "tag:%s,%s:%s" % (settings.DOMAIN_NAME, entry.timestamp.strftime("%Y-%m-%d"), entry.sha1_hash)
        ElementTree.SubElement(entry_element, "title").text = entry.get_title()
        ElementTree.SubElement(entry_element, "updated").text = format_timestamp(entry.timestamp)
        template = loader.get_template(utils.camel_case_to_underscores(entry.__class__.__name__) + ".html")
        content = ElementTree.SubElement(entry_element, "content")
        content.text = template.render(Context({"entry": entry}))
        content.attrib["type"] = "html"
    indent(feed)
    return HttpResponse(ElementTree.tostring(feed,"utf-8"), content_type="application/atom+xml; charset=utf-8")
