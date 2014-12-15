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


"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “samples”, which is the actual sample database and the
heart of JuliaBase.

It takes the URL that the user chose, and converts it to a function call –
possibly with parameters.

The most important thing here is to enforce some URL guidelines:

    * Use plural forms.  For example, for accessing a sample, the proper URL is
      ``/samples/01B410`` instead of ``/sample/01B410``.

    * *Functions* should end in a slash, whereas objects should not.  For
      example, adding new samples is a function, so its URL is
      ``/samples/add/``.  But the sample 01B410 is a concrete object, so it's
      ``/sample/01B410``.  Function are generally add, edit, split etc.
      Objects are samples, processes, feeds, and special resources like main
      menu or login view.

    * Everything you can do with a certain object must start with the same
      prefix.  For example, everything you can do with sample 01B410 must start
      with ``/samples/01B410``.  If you just want to see it, nothing is
      appended; if you want to edit it, ``/edit/`` is appended etc.  The reason
      is that this way, it is simple to construct links by calling
      ``xxx.get_absolute_url()`` and appending something.

Note that although this is only an “application”, it contains views for
authentication (login/logout), too.  You may override them in the global URL
configuration file, though.


:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/

"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls import url


urlpatterns = [
    url(r"^about$", "samples.views.statistics.about"),
    url(r"^statistics$", "samples.views.statistics.statistics"),
    url(r"^$", "samples.views.main.main_menu"),
    url(r"^feeds/(?P<username>.+)\+(?P<user_hash>.+)", "samples.views.feed.show"),
    url(r"^my_samples/(?P<username>.+)", "samples.views.my_samples.edit"),

    url(r"^depositions/split_and_rename_samples/(?P<deposition_number>.+)",
        "samples.views.split_after_deposition.split_and_rename_after_deposition"),
    url(r"^depositions/$", "samples.views.main.deposition_search"),
    url(r"^depositions/(?P<deposition_number>.+)", "samples.views.main.show_deposition"),

    url(r"^samples/by_id/(?P<sample_id>\d+)(?P<path_suffix>.*)", "samples.views.sample.by_id", name="show_sample_by_id"),
    url(r"^samples/$", "samples.views.sample.search"),
    url(r"^advanced_search$", "samples.views.sample.advanced_search"),
    # FixMe: Must be regenerated with a minimal add-sample form
 #   url(r"^samples/add/$", "samples.views.sample.add"),
    url(r"^samples/(?P<parent_name>.+)-/split/$", "samples.views.split_and_rename.split_and_rename"),
    url(r"^samples/(?P<sample_name>.+)-/kill/$", "samples.views.sample_death.new"),
    url(r"^samples/(?P<sample_name>.+)-/add_process/$", "samples.views.sample.add_process"),
    url(r"^samples/(?P<sample_name>.+)-/edit/$", "samples.views.sample.edit"),
    url(r"^samples/(?P<sample_name>.+)-/export/$", "samples.views.sample.export"),
    url(r"^samples/rename/$", "samples.views.sample.rename_sample"),
    url(r"^samples/(?P<sample_name>.+)$", "samples.views.sample.show", name="show_sample_by_name"),
    url(r"^bulk_rename$", "samples.views.bulk_rename.bulk_rename"),

    url(r"^resplit/(?P<old_split_id>.+)", "samples.views.split_and_rename.split_and_rename"),

    url(r"^processes/(?P<process_id>\d+)", "samples.views.main.show_process"),

    url(r"^sample_series/add/$", "samples.views.sample_series.new"),
    url(r"^sample_series/(?P<name>.+)-/edit/$", "samples.views.sample_series.edit"),
    url(r"^sample_series/(?P<name>.+)-/export/$", "samples.views.sample_series.export"),
    url(r"^sample_series/(?P<name>.+)", "samples.views.sample_series.show"),

    url(r"^results/add/$", "samples.views.result.edit", {"process_id": None}, "add_result"),
    url(r"^results/(?P<process_id>\d+)/edit/$", "samples.views.result.edit", name="edit_result"),
    url(r"^results/(?P<process_id>\d+)/export/$", "samples.views.result.export"),
    url(r"^results/images/(?P<process_id>\d+)", "samples.views.result.show_image"),
    url(r"^results/thumbnails/(?P<process_id>\d+)", "samples.views.result.show_thumbnail"),
    url(r"^results/(?P<process_id>\d+)", "samples.views.result.show"),

    url(r"^plots/thumbnails/(?P<process_id>\d+)/(?P<plot_id>.+)", "samples.views.plots.show_plot", {"thumbnail": True},
        "process_plot_thumbnail"),
    url(r"^plots/thumbnails/(?P<process_id>\d+)", "samples.views.plots.show_plot", {"plot_id": "", "thumbnail": True},
        "default_process_plot_thumbnail"),
    url(r"^plots/(?P<process_id>\d+)/(?P<plot_id>.+)", "samples.views.plots.show_plot", {"thumbnail": False}, "process_plot"),
    url(r"^plots/(?P<process_id>\d+)", "samples.views.plots.show_plot", {"plot_id": "", "thumbnail": False}, "default_process_plot"),

    url(r"^external_operators/add/$", "samples.views.external_operator.new"),
    url(r"^external_operators/(?P<external_operator_id>.+)/edit/$", "samples.views.external_operator.edit"),
    url(r"^external_operators/(?P<external_operator_id>.+)", "samples.views.external_operator.show"),
    url(r"^external_operators/$", "samples.views.external_operator.list_"),

    url(r"^preferences/(?P<login_name>.+)", "samples.views.user_details.edit_preferences"),
    url(r"^topics_and_permissions/(?P<login_name>.+)", "samples.views.user_details.topics_and_permissions"),
    url(r"^my_layers/(?P<login_name>.+)", "samples.views.my_layers.edit"),

    url(r"^permissions/$", "samples.views.permissions.list_"),
    url(r"^permissions/(?P<username>.+)", "samples.views.permissions.edit"),

    url(r"^topics/add/$", "samples.views.topic.add"),
    url(r"^topics/$", "samples.views.topic.list_"),
    url(r"^topics/(?P<id>.+)", "samples.views.topic.edit"),

    url(r"^claims/(?P<username>.+)/add/$", "samples.views.claim.add"),
    url(r"^claims/(?P<username>.+)/$", "samples.views.claim.list_"),
    url(r"^claims/(?P<claim_id>.+)", "samples.views.claim.show"),

    url(r"^primary_keys$", "samples.views.json_client.primary_keys"),
    url(r"^available_items/(?P<model_name>[A-Za-z_][A-Za-z_0-9]*)", "samples.views.json_client.available_items"),
    url(r"^latest_split/(?P<sample_name>.+)", "samples.views.split_and_rename.latest_split"),
    url(r"^login_remote_client$", "samples.views.json_client.login_remote_client"),
    url(r"^logout_remote_client$", "samples.views.json_client.logout_remote_client"),
    url(r"^add_alias$", "samples.views.json_client.add_alias"),
    url(r"^change_my_samples$", "samples.views.json_client.change_my_samples"),

    url(r"^qr_code$", "samples.views.sample.qr_code"),
    url(r"^data_matrix_code$", "samples.views.sample.data_matrix_code"),

    url(r"^status/add/$", "samples.views.status.add"),
    url(r"^status/$", "samples.views.status.show"),
    url(r"^status/(?P<id_>\d+)/withdraw/$", "samples.views.status.withdraw"),

    url(r"^fold_process/(?P<sample_id>\d+)$", "samples.views.json_client.fold_process"),
    url(r"^folded_processes/(?P<sample_id>\d+)$", "samples.views.json_client.get_folded_processes"),

    url(r"^merge_samples$", "samples.views.merge_samples.merge"),

    url(r"crawler_logs/$", "samples.views.log_viewer.list"),
    url(r"crawler_logs/(?P<process_class_name>[a-z_0-9]+)", "samples.views.log_viewer.view"),

    url(r"^tasks/$", "samples.views.task_lists.show"),
    url(r"^tasks/add/$", "samples.views.task_lists.edit", {"task_id": None}),
    url(r"^tasks/(?P<task_id>\d+)/edit/$", "samples.views.task_lists.edit"),
    url(r"^tasks/(?P<task_id>\d+)/remove/$", "samples.views.task_lists.remove"),

    url(r"^fold_main_menu_element/", "samples.views.json_client.fold_main_menu_element"),
    url(r"^folded_main_menu_elements/", "samples.views.json_client.get_folded_main_menu_elements"),
]
