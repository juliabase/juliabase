#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Module which defines the command ``create_or_reposition_substrate``.
It is a one-shot program which we want to save for future usage.
"""

from __future__ import absolute_import, unicode_literals

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    args = ""
    help = "Internal command for creating and repositioning the substrate process. " \
    "Use it to get sure that the first process of all samples is the substrate process."

    def handle(self, *args, **kwargs):
        from chantal_ipv.models import Sample, Substrate
        from datetime import timedelta, datetime
        from django.contrib.auth.models import User

        for sample in Sample.objects.filter(split_origin__isnull=True).iterator():
            try:
                substrate = Substrate.objects.get(samples=sample)
            except Substrate.DoesNotExist:
                substrate = Substrate.objects.create(material="custom", comments="unknown substrate",
                                                     timestamp=datetime.now(), timestamp_inaccuracy=6,
                                                     operator=User.objects.get(username="nobody"))
                substrate.samples = [sample]
            processes = sample.processes.all().order_by("timestamp")
            if processes[0].content_type.model_class() != Substrate:
                substrate.timestamp = processes[0].timestamp - timedelta(minutes=1)
                substrate.timestamp_inaccuracy = 3
                substrate.save()
