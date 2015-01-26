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


"""Views to add and edit substrates.
"""

from __future__ import unicode_literals, absolute_import

from django.db.models import Max
from django.utils.translation import ugettext_lazy as _, ugettext, ugettext
from institute import models as institute_models
import samples.utils.views as utils


class SubstrateForm(utils.ProcessForm):
    """Model form class for a substrate.
    """
    class Meta:
        model = institute_models.Substrate
        fields = "__all__"

    def clean(self):
        cleaned_data = super(SubstrateForm, self).clean()
        if cleaned_data.get("material") == "custom" and not cleaned_data.get("comments"):
            self.add_error("comments", _("For a custom substrate, you must give substrate comments."))
        return cleaned_data


class EditView(utils.ProcessMultipleSamplesView):
    model = institute_models.Substrate
    form_class = SubstrateForm

    def is_referentially_valid(self):
        """Test whether all forms are consistent with each other and with the
        database.  For example, no sample must get more than one substrate.

        :return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = super(EditView, self).is_referentially_valid()
        if self.forms["samples"].is_valid() and self.forms["process"].is_valid():
            for sample in self.forms["samples"].cleaned_data["sample_list"]:
                processes = sample.processes
                if processes.exists():
                    earliest_timestamp = processes.aggregate(Max("timestamp"))["timestamp__max"]
                    if earliest_timestamp < self.forms["process"].cleaned_data["timestamp"]:
                        self.forms["samples"].add_error(
                            "sample_list", _("Sample {0} has already processes before the timestamp of this substrate, "
                                             "namely from {1}.").format(sample, earliest_timestamp))
                        referentially_valid = False
                    for process in processes.all():
                        if process.content_type.model_class() == institute_models.Substrate:
                            self.forms["samples"].add_error(
                                "sample_list", _("Sample {0} has already a substrate.").format(sample))
                            referentially_valid = False
                            break
        return referentially_valid


_ = ugettext
