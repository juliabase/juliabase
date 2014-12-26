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

from __future__ import absolute_import, unicode_literals, division

import datetime, re
from samples import models


deposition_index_pattern = re.compile(r"\d{3,4}")

def get_next_deposition_number(letter):
    """Find a good next deposition number.  For example, if the last run was
    called “08B-045”, this routine yields “08B-046” (unless the new year has
    begun).

    :param letter: the indentifying letter of the deposition apparatus.  For
        example, it is ``"B"`` for the 6-chamber deposition.

    :type letter: str

    :return:
      A so-far unused deposition number for the current calendar year for the
      given deposition apparatus.
    """
    prefix = r"{0}{1}-".format(datetime.date.today().strftime("%y"), letter)
    prefix_length = len(prefix)
    pattern_string = r"^{0}[0-9]+".format(re.escape(prefix))
    deposition_numbers = \
        models.Deposition.objects.filter(number__regex=pattern_string).values_list("number", flat=True).iterator()
    numbers = [int(deposition_index_pattern.match(deposition_number[prefix_length:]).group())
               for deposition_number in deposition_numbers]
    next_number = max(numbers) + 1 if numbers else 1
    return prefix + "{0:03}".format(next_number)


def get_next_deposition_or_process_number(letter, process_cls):
    """This function works like the `get_next_deposition_number` from
    `samples.utils`, but it also searches throught a given process that is
    using the same pool of numbers such as the deposition.

    For example see the FiveChamberDeposition and the FiveChamberEtching.
    There are two different processes that are made on the same apparatus and
    therefore have the same numbers.

    :param letter: the indentifying letter of the deposition apparatus.  For
        example, it is ``"B"`` for the 6-chamber deposition.
    :param process_cls: the model class from the process who has the same
      type of numbers such as the deposition.

    :type letter: str
    :type process_cls: `samples.models.PhysicalProcess`

    :return:
      A so-far unused deposition number for the current calendar year for the
      given deposition apparatus.
    """
    prefix = "{year}{letter}-".format(year=datetime.date.today().strftime("%y"), letter=letter)
    numbers = map(int, map(lambda string: string[len(prefix):],
                           set(models.Deposition.objects.filter(number__startswith=prefix).values_list('number', flat=True). \
                               iterator()) |
                           set(process_cls.objects.filter(number__startswith=prefix).values_list('number', flat=True). \
                               iterator())))
    next_number = max(numbers) + 1 if numbers else 1
    return prefix + "{0:03}".format(next_number)
