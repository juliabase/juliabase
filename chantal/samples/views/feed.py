#!/usr/bin/env python
# -*- coding: utf-8 -*-

import django.contrib.syndication.feeds
import django.contrib.auth.models
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.feedgenerator import Atom1Feed
from django.utils.translation import ugettext as _, ugettext_lazy
from chantal.samples import models
from . import utils

class Feed(django.contrib.syndication.feeds.Feed):
    feed_type = Atom1Feed
    title = "Chantal news"
    link = "/sitenews/"
    description = "New processes."

    def items(self):
        return [process.find_actual_instance() for process in models.Deposition.objects.iterator()]
    def item_author_name(self, item):
        return utils.get_really_full_name(item.operator)
    def item_author_email(self, item):
        return item.operator.email
    def item_pubdate(self, item):
        return item.timestamp

def show(request, username):
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    try:
        user_hash = utils.parse_query_string(request)["hash"]
    except KeyError:
        raise Http404(_(u"You must add a \"hash\" parameter to the query string."))
    if user_hash != utils.get_user_hash(user):
        return utils.HttpResponseSeeOther("permission_error")
    feed = Feed("latest_news", request)
    feed.link = feed.feed_url = request.path
    return HttpResponse(feed.get_feed().writeString("utf-8"), content_type="application/atom+xml; charset=utf-8")
