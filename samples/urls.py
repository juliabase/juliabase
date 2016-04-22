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
from samples.views import statistics, main, feed, my_samples, split_after_deposition, sample, split_and_rename, \
    sample_death, bulk_rename, sample_series, result, plots, external_operator, user_details, permissions, topic, \
    claim, json_client, status, merge_samples, log_viewer, task_lists


app_name = "samples"

urlpatterns = [
    url(r"^about$", statistics.about, name="about"),
    url(r"^statistics$", statistics.statistics, name="statistics"),
    url(r"^$", main.main_menu, name="main_menu"),
    url(r"^feeds/(?P<username>.+)\+(?P<user_hash>.+)", feed.show, name="show_feed"),
    url(r"^my_samples/(?P<username>.+)", my_samples.edit, name="edit_my_samples"),

    url(r"^depositions/split_and_rename_samples/(?P<deposition_number>.+)",
        split_after_deposition.split_and_rename_after_deposition, name="split_and_rename_after_deposition"),
    url(r"^depositions/$", main.deposition_search, name="deposition_search"),
    url(r"^depositions/(?P<deposition_number>.+)", main.show_deposition),

    url(r"^samples/by_id/(?P<sample_id>\d+)(?P<path_suffix>.*)", sample.by_id, name="show_sample_by_id"),
    url(r"^samples/$", sample.search, name="sample_search"),
    url(r"^advanced_search$", sample.advanced_search, name="advanced_search"),
    # FixMe: Must be regenerated with a minimal add-sample form
 #   url(r"^samples/add/$", sample.add),
    url(r"^samples/(?P<parent_name>.+)/split/$", split_and_rename.split_and_rename, name="split_and_rename"),
    url(r"^samples/(?P<sample_name>.+)/kill/$", sample_death.new, name="kill_sample"),
    url(r"^samples/(?P<sample_name>.+)/add_process/$", sample.add_process, name="add_process"),
    url(r"^samples/(?P<sample_name>.+)/edit/$", sample.edit, name="edit_sample"),
    url(r"^samples/(?P<sample_name>.+)/export/$", sample.export, name="export_sample"),
    url(r"^samples/rename/$", sample.rename_sample, name="rename_sample"),
    url(r"^samples/(?P<sample_name>.+)$", sample.show, name="show_sample_by_name"),
    url(r"^bulk_rename$", bulk_rename.bulk_rename, name="bulk_rename"),

    url(r"^resplit/(?P<old_split_id>.+)", split_and_rename.split_and_rename, name="resplit"),

    url(r"^processes/(?P<process_id>\d+)$", main.show_process, name="show_process"),

    url(r"^sample_series/add/$", sample_series.new, name="add_sample_series"),
    url(r"^sample_series/(?P<name>.+)/edit/$", sample_series.edit, name="edit_sample_series"),
    url(r"^sample_series/(?P<name>.+)/export/$", sample_series.export, name="export_sample_series"),
    url(r"^sample_series/(?P<name>.+)", sample_series.show, name="show_sample_series"),

    url(r"^results/add/$", result.edit, {"process_id": None}, "add_result"),
    url(r"^results/(?P<process_id>\d+)/edit/$", result.edit, name="edit_result"),
    url(r"^results/(?P<process_id>\d+)/export/$", result.export, name="export_result"),
    url(r"^results/images/(?P<process_id>\d+)$", result.show_image, name="show_result_image"),
    url(r"^results/thumbnails/(?P<process_id>\d+)$", result.show_thumbnail, name="show_result_thumbnail"),
    url(r"^results/(?P<process_id>\d+)$", result.show, name="show_result"),

    url(r"^plots/thumbnails/(?P<process_id>\d+)/(?P<plot_id>.+)", plots.show_plot, {"thumbnail": True},
        "process_plot_thumbnail"),
    url(r"^plots/thumbnails/(?P<process_id>\d+)$", plots.show_plot, {"plot_id": "", "thumbnail": True},
        "default_process_plot_thumbnail"),
    url(r"^plots/(?P<process_id>\d+)/(?P<plot_id>.+)", plots.show_plot, {"thumbnail": False}, "process_plot"),
    url(r"^plots/(?P<process_id>\d+)$", plots.show_plot, {"plot_id": "", "thumbnail": False}, "default_process_plot"),

    url(r"^external_operators/add/$", external_operator.new, name="add_external_operator"),
    url(r"^external_operators/(?P<external_operator_id>.+)/edit/$", external_operator.edit, name="edit_external_operator"),
    url(r"^external_operators/(?P<external_operator_id>.+)", external_operator.show, name="show_external_operator"),
    url(r"^external_operators/$", external_operator.list_, name="list_external_operators"),

    url(r"^preferences/(?P<login_name>.+)", user_details.edit_preferences, name="edit_preferences"),
    url(r"^topics_and_permissions/(?P<login_name>.+)", user_details.topics_and_permissions, name="topics_and_permissions"),

    url(r"^permissions/$", permissions.list_, name="list_permissions"),
    url(r"^permissions/(?P<username>.+)", permissions.edit, name="edit_permissions"),

    url(r"^topics/add/$", topic.add, name="add_topic"),
    url(r"^topics/$", topic.list_, name="list_topics"),
    url(r"^topics/(?P<id>\d+)$", topic.edit, name="edit_topic"),

    url(r"^claims/(?P<username>.+)/add/$", claim.add, name="add_claim"),
    url(r"^claims/(?P<username>.+)/$", claim.list_, name="list_claims"),
    url(r"^claims/(?P<claim_id>\d+)$", claim.show, name="show_claim"),

    url(r"^add_sample$", json_client.add_sample),
    url(r"^primary_keys$", json_client.primary_keys),
    url(r"^available_items/(?P<model_name>[A-Za-z_][A-Za-z_0-9]*)$", json_client.available_items),
    url(r"^latest_split/(?P<sample_name>.+)", split_and_rename.latest_split),
    url(r"^login_remote_client$", json_client.login_remote_client),
    url(r"^logout_remote_client$", json_client.logout_remote_client),
    url(r"^add_alias$", json_client.add_alias),
    url(r"^change_my_samples$", json_client.change_my_samples),

    url(r"^qr_code$", sample.qr_code, name="qr_code"),
    url(r"^data_matrix_code$", sample.data_matrix_code),

    url(r"^status/add/$", status.add, name="add_status"),
    url(r"^status/$", status.show, name="show_status"),
    url(r"^status/(?P<id_>\d+)/withdraw/$", status.withdraw, name="withdraw_status"),

    url(r"^fold_process/(?P<sample_id>\d+)$", json_client.fold_process, name="fold_process"),
    url(r"^folded_processes/(?P<sample_id>\d+)$", json_client.get_folded_processes, name="get_folded_processes"),

    url(r"^merge_samples$", merge_samples.merge, name="merge_samples"),

    url(r"crawler_logs/$", log_viewer.list, name="list_log_viewers"),
    url(r"crawler_logs/(?P<process_class_name>[a-z_0-9]+)$", log_viewer.view),

    url(r"^tasks/$", task_lists.show, name="show_task_lists"),
    url(r"^tasks/add/$", task_lists.edit, {"task_id": None}),
    url(r"^tasks/(?P<task_id>\d+)/edit/$", task_lists.edit, name="edit_task_list"),
    url(r"^tasks/(?P<task_id>\d+)/remove/$", task_lists.remove, name="remove_task_list"),

    url(r"^fold_main_menu_element/", json_client.fold_main_menu_element, name="fold_main_menu_element"),
    url(r"^folded_main_menu_elements/", json_client.get_folded_main_menu_elements, name="get_folded_main_menu_elements"),
]
