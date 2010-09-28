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

class Searchable(object):
    u"""This abstract class is for all views, which should be listed
    in the search-view.
    """
    class Meta:
        abstract = True

    def is_searchable(self):
        return True

    def get_search_fields(self):
        u"""This Method returns all fields, which could be used in the
        search-view.
        The return object should be a dictionary with the names of the fields
        as keys and a view per data stored in the database as values.

        :Return:
          a dictionary with the names of the fields as keys and views as
          values

        :rtype: dict mapping str to ``samples.views.sample_search.SearchField``
        """
        raise NotImplementedError("Should have implemented this")

    def append_query(self, query):
        raise NotImplementedError("Should have implemented this")

