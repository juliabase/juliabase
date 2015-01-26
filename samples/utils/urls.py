#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import absolute_import, unicode_literals

import importlib
from django.conf.urls import url
from django.core.urlresolvers import get_callable
from jb_common.utils.base import camel_case_to_underscores
from samples.views import lab_notebook
import samples.views.main


class PatternGenerator(object):
    """This class helps to build URL pattern lists for physical processes.  You
    instantiate it once in your URLconf file.  Then, you add URLs by calling
    `physical_process` for every physical process::

        pattern_generator = PatternGenerator(urlpatterns, "institute.views.samples")
        pattern_generator.deposition("ClusterToolDeposition", views={"add", "edit"})
        pattern_generator.deposition("FiveChamberDeposition", "5-chamber_depositions")
        pattern_generator.physical_process("PDSMeasurement", "number")
        pattern_generator.physical_process("Substrate", views={"edit"})
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
        second parameter.  For the “custom show” view, a :samp:`show(request,
        {process_class_name}_id)` function must exist.  If there is an
        `identifying_field`, this is used for the second parameter name
        instead.  If no URL for a custom show view is requested, a default one
        is generated using a generic view function (which is mostly
        sufficient).

        :param class_name: Name of the physical process class,
            e.g. ``"ThicknessMeasurement"``.
        :param identifying_field: If applicable, name of the model field which
            serves as “poor man's” primary key.  If not given, the ``id`` is
            used.
        :param url_name: The URL path component to be used for this process.  By
            default, this is the class name converted to underscores notation,
            with an “s” appended, e.g. ``"thickness_measurements"``.  It may
            contain slashs.
        :param views: The view functions for which URLs should be generated.
            You may choose from ``"add"``, ``"edit"``, ``"custom_show"``, and
            ``"lab_notebook"``.

        :type class_name: unicode
        :type identifying_field: unicode
        :type url_name: unicode
        :type views: set of unicode
        """
        class_name_with_underscores = camel_case_to_underscores(class_name)
        if not url_name:
            if class_name_with_underscores.endswith(("s", "x", "z")):
                url_name = class_name_with_underscores + "es"
            else:
                url_name = class_name_with_underscores + "s"
        assert not views - {"add", "edit", "custom_show", "lab_notebook"}
        normalized_id_field = identifying_field or class_name_with_underscores + "_id"
        if "lab_notebook" in views:
            self.url_patterns.extend([url(r"^{}/lab_notebook/(?P<year_and_month>.*)/export/".format(url_name),
                                          lab_notebook.export, {"process_name": class_name},
                                          "export_lab_notebook_" + class_name_with_underscores),
                                      url(r"^{}/lab_notebook/(?P<year_and_month>.*)".format(url_name),
                                          lab_notebook.show, {"process_name": class_name},
                                          "lab_notebook_" + class_name_with_underscores)])
        if "add" in views or "edit" in views or "custom_view" in views:
            module = importlib.import_module(self.views_prefix + class_name_with_underscores)
            if "add" in views or "edit" in views:
                try:
                    edit_view_callable = module.EditView.as_view()
                except AttributeError:
                    edit_view_callable = module.edit
        if "add" in views:
            self.url_patterns.append(url(r"^{}/add/$".format(url_name), edit_view_callable,
                                         {normalized_id_field: None}, "add_" + class_name_with_underscores))
        if "edit" in views:
            self.url_patterns.append(url(r"^{}/(?P<{}>.+)/edit/$".format(url_name, normalized_id_field), edit_view_callable,
                                         name="edit_" + class_name_with_underscores))
        if "custom_show" in views:
            self.url_patterns.append(url(r"^{}/(?P<{}>.+)".format(url_name, normalized_id_field), module.show,
                                         name="show_" + class_name_with_underscores))
        else:
            self.url_patterns.append(url(r"^{}/(?P<process_id>.+)".format(url_name, normalized_id_field),
                                         samples.views.main.show_process, {"process_name": class_name},
                                         name="show_" + class_name_with_underscores))

    def deposition(self, class_name, url_name=None, views={"add", "edit", "lab_notebook"}):
        """Add URLs for the views of the deposition process `class_name`.  This is a
        shorthand for `physical_process` with defaults optimized for
        depositions: ``identifying_field`` is ``"number"``, and the views
        include a lab notebook.

        :param class_name: Name of the deposition class,
            e.g. ``"FiveChamberDeposition"``.
        :param url_name: The URL path component to be used for this deposition.
            By default, this is the class name converted to underscores
            notation, with an “s” appended, e.g. ``"thickness_measurements"``.
        :param views: The view functions for which URLs should be generated.
            You may choose from ``"add"``, ``"edit"``, ``"custom_show"``, and
            ``"lab_notebook"``.

        :type class_name: unicode
        :type url_name: unicode
        :type views: set of unicode
        """
        self.physical_process(class_name, "number", url_name, views)
