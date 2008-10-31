#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Helper routines for generating single feed entries.  They are called by
views shortly after the database was changed in one way or another.
"""

from chantal.samples import models

def generate_feed_for_physical_process(process, user, edit_description_form=None):
    u"""Generate a feed entry for a physical process (deposition, measurement,
    etching etc) which was recently edited or created.

    :Parameters:
      - `process`: the process which was added/edited recently
      - `user`: the user who added/edited the process (actually, his details)
      - `edit_description_form`: the form containing data about what was edited
        in the process.  ``None`` if the process was newly created.

    :type process: `models.process`
    :type user: `models.UserDetails`
    :type edit_description_form: `utils.EditDescriptionForm`
    """
    if edit_description_form:
        pass
    else:
        entry = models.FeedNewPhysicalProcess.objects.create(originator=user, process=process)
        users = []
        for sample in process.samples.all():
            users.extend(sample.watchers.all())
        entry.users = users
