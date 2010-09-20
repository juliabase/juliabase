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

class Searchable( object ):
    u"""This abstract class is for all Models, which should be listed
    in the search-view.
    """
    __data_types = ("string", "digit")

    class Meta:
        abstract = True

    def is_searchable(self):
        return True

    def get_search_fields(self):
        u"""This Method returns all variables, which could be used in the
        search-view.
        The return object should be a dictionary with the names of the variables
        as keys and the type of the data stored in the variables as values.

        :Return:
          a dictionary with the names of the variables as keys and data type as
          values

        :rtype: dict mapping str to ``sample.SearchView``
        """
        raise NotImplementedError("Should have implemented this")

    def append_query(self, query):
        u"""Here i use a specialty from the Django QuerySet API. In Django each QuerySet
        returns a new QuerySet which can be used as its own Object. So I can extend the
        given QuerySet by just calling the Methods I need to access the database fields
        from this Model.
        """
        raise NotImplementedError("Should have implemented this")

