#!/usr/bin/env python
# -*- coding: utf-8 -*-

from chantal.samples import models

def generate_feed_for_physical_process(process, user, edit_description_form=None):
    if edit_description_form:
        pass
    else:
        entry = models.FeedNewPhysicalProcess.objects.create(originator=user, process=process)
        users = []
        for sample in process.samples.all():
            users.extend(sample.watchers.all())
        entry.users = users
