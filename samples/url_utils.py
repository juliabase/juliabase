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


from __future__ import absolute_import, unicode_literals

from django.conf.urls import url
from samples.views.shared_utils import camel_case_to_underscores


class PatternGenerator(object):
    """This class helps to build URL pattern lists for physical processes.  You
    instantiate it once in your URLconf file.  Then, you add URLs by calling
    `physical_process` for every physical process.
    """

    def __init__(self, url_patterns, views_prefix):
        """
        :param url_patterns: The URL patterns to populate in situ.
        :param views_prefix: the prefix for the view functions as a Python path,
            e.g. ``"my_app.views.samples"``

        :type url_patterns: list of `url()` instances
        :type views_prefix: unicode
        """
        self.views_prefix = views_prefix + "."
        self.url_patterns = url_patterns

    def physical_process(self, class_name, identifying_field=None, url_name=None, views={"add", "edit"}):
        """Add URLs for the views of the physical process `class_name`.  For the “add”
        and the “edit” view, an :samp:`edit(request, {process_class_name}_id)`
        function must exist.  In case of “add”, ``None`` is passed as the
        second parameter.  For the “show” view, a :samp:`show(request,
        {process_class_name}_id)` function must exist.  If there is an
        `identifying_field`, this is used for the second parameter name
        instead.  If no URL for a show view is requested, a default one is
        generated using a generic view function (which is mostly sufficient).

        :param class_name: Name of the physical process class,
            e.g. ``"ThicknessMeasurement"``.
        :param identifying_field: If applicable, name of the model field which
            serves as “poor man's” primary key.  If not given, the ``id`` is
            used.
        :param url_name: The URL path component to be used for this process.  By
            default, this is the class name converted to underscores notation,
            with an “s” appended, e.g. ``"thickness_measurements"``.
        :param views: The view functions for which URLs should be generated.
            You may choose from ``"add"``, ``"edit"``, ``"show"``, and
            ``"lab_notebook"``.

        :type class_name: unicode
        :type identifying_field: unicode
        :type url_name: unicode
        :type views: set of unicode
        """
        camel_case_class_name = camel_case_to_underscores(class_name)
        url_name = url_name or camel_case_class_name + "s"
        assert not views - {"add", "edit", "show", "lab_notebook"}
        normalized_id_field = identifying_field or camel_case_class_name + "_id"
        if "add" in views:
            self.url_patterns.append(url(r"^{}/add/$".format(url_name), self.views_prefix + camel_case_class_name + ".edit",
                                         {normalized_id_field: None}, "add_" + camel_case_class_name))
        if "edit" in views:
            self.url_patterns.append(url(r"^{}/(?P<{}>.+)/edit/$".format(url_name, normalized_id_field),
                                         self.views_prefix + camel_case_class_name + ".edit", name="edit_" +
                                         camel_case_class_name))
        if "show" in views:
            self.url_patterns.append(url(r"^{}/(?P<{}>.+)".format(url_name, normalized_id_field),
                                         self.views_prefix + camel_case_class_name + ".show", name="show_" +
                                         camel_case_class_name))
        else:
            self.url_patterns.append(url(r"^{}/(?P<process_id>.+)".format(url_name, normalized_id_field),
                                         "samples.views.main.show_process", {"process_name": class_name},
                                         name="show_" + camel_case_class_name))
        if "lab_notebook" in views:
            self.url_patterns.extend([url(r"^{}/lab_notebook/(?P<year_and_month>.*)/export/".format(url_name),
                                          "samples.views.lab_notebook.export", {"process_name": class_name},
                                          "export_lab_notebook_" + camel_case_class_name),
                                      url(r"^{}/lab_notebook/(?P<year_and_month>.*)".format(url_name),
                                          "samples.views.lab_notebook.show", {"process_name": class_name},
                                          "lab_notebook_" + camel_case_class_name)])
