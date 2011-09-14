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


u"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “samples”, which is the actual sample database and the
heart of Chantal.

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

from __future__ import absolute_import

from django.conf.urls.defaults import *
from django.conf import settings


urlpatterns = patterns("samples.views",
                       (r"^$", "main.main_menu"),
                       (r"^feeds/(?P<username>.+)\+(?P<user_hash>.+)", "feed.show"),
                       (r"^my_samples/(?P<username>.+)", "my_samples.edit"),

                       (r"^depositions/split_and_rename_samples/(?P<deposition_number>.+)",
                        "split_after_deposition.split_and_rename_after_deposition"),
                       (r"^depositions/$", "main.deposition_search"),
                       (r"^depositions/(?P<deposition_number>.+)", "main.show_deposition"),

                       url(r"^samples/by_id/(?P<sample_id>\d+)(?P<path_suffix>.*)", "sample.by_id",
                           name="show_sample_by_id"),
                       (r"^samples/$", "sample.search"),
                       (r"^advanced_search$", "sample.advanced_search"),
                       # FixMe: Must be regenerated with a minimal add-sample form
#                       (r"^samples/add/$", "sample.add"),
                       (r"^samples/(?P<parent_name>.+)-/split/$", "split_and_rename.split_and_rename"),
                       (r"^samples/(?P<sample_name>.+)-/kill/$", "sample_death.new"),
                       (r"^samples/(?P<sample_name>.+)-/add_process/$", "sample.add_process"),
                       (r"^samples/(?P<sample_name>.+)-/edit/$", "sample.edit"),
                       (r"^samples/(?P<sample_name>.+)-/export/$", "sample.export"),
                       url(r"^samples/(?P<sample_name>.+)", "sample.show", name="show_sample_by_name"),
                       (r"^bulk_rename$", "bulk_rename.bulk_rename"),

                       (r"^resplit/(?P<old_split_id>.+)", "split_and_rename.split_and_rename"),

                       (r"^processes/(?P<process_id>\d+)", "main.show_process"),

                       (r"^sample_series/add/$", "sample_series.new"),
                       (r"^sample_series/(?P<name>.+)-/edit/$", "sample_series.edit"),
                       (r"^sample_series/(?P<name>.+)-/export/$", "sample_series.export"),
                       (r"^sample_series/(?P<name>.+)", "sample_series.show"),

                       url(r"^results/add/$", "result.edit", {"process_id": None}, "add_result"),
                       url(r"^results/(?P<process_id>\d+)/edit/$", "result.edit", name="edit_result"),
                       (r"^results/(?P<process_id>\d+)/export/$", "result.export"),
                       (r"^results/images/(?P<process_id>\d+)", "result.show_image"),
                       (r"^results/thumbnails/(?P<process_id>\d+)", "result.show_thumbnail"),
                       (r"^results/(?P<process_id>\d+)", "result.show"),

                       url(r"^plots/thumbnails/(?P<process_id>\d+)/(?P<plot_id>.+)", "plots.show_plot",
                           {"thumbnail": True}, "process_plot_thumbnail"),
                       url(r"^plots/thumbnails/(?P<process_id>\d+)", "plots.show_plot", {"plot_id": u"", "thumbnail": True},
                           "default_process_plot_thumbnail"),
                       url(r"^plots/(?P<process_id>\d+)/(?P<plot_id>.+)", "plots.show_plot", {"thumbnail": False},
                           "process_plot"),
                       url(r"^plots/(?P<process_id>\d+)", "plots.show_plot", {"plot_id": u"", "thumbnail": False},
                           "default_process_plot"),

                       (r"^external_operators/add/$", "external_operator.new"),
                       (r"^external_operators/(?P<external_operator_id>.+)/edit/$", "external_operator.edit"),
                       (r"^external_operators/(?P<external_operator_id>.+)", "external_operator.show"),
                       (r"^external_operators/$", "external_operator.list_"),

                       (r"^users/(?P<login_name>.+)", "user_details.show_user"),
                       (r"^preferences/(?P<login_name>.+)", "user_details.edit_preferences"),
                       (r"^topics_and_permissions/(?P<login_name>.+)", "user_details.topics_and_permissions"),
                       (r"^my_layers/(?P<login_name>.+)", "my_layers.edit"),

                       (r"^permissions/$", "permissions.list_"),
                       (r"^permissions/(?P<username>.+)", "permissions.edit"),

                       (r"^topics/add/$", "topic.add"),
                       (r"^topics/$", "topic.list_"),
                       (r"^topics/(?P<name>.+)", "topic.edit"),

                       (r"^claims/(?P<username>.+)/add/$", "claim.add"),
                       (r"^claims/(?P<username>.+)/$", "claim.list_"),
                       (r"^claims/(?P<claim_id>.+)", "claim.show"),

                       (r"^primary_keys$", "json_client.primary_keys"),
                       (r"^available_items/(?P<model_name>[A-Za-z_][A-Za-z_0-9]*)", "json_client.available_items"),
                       (r"^next_deposition_number/(?P<letter>.+)", "json_client.next_deposition_number"),
                       (r"^latest_split/(?P<sample_name>.+)", "split_and_rename.latest_split"),
                       (r"^login_remote_client$", "json_client.login_remote_client"),
                       (r"^logout_remote_client$", "json_client.logout_remote_client"),
                       (r"^add_sample$", "json_client.add_sample"),
                       (r"^add_alias$", "json_client.add_alias"),
                       (r"^change_my_samples$", "json_client.change_my_samples"),

                       (r"^qr_code$", "sample.qr_code"),
                       (r"^data_matrix_code$", "sample.data_matrix_code"),

                       (r"^status/add/$", "status.add"),
                       (r"^status/$", "status.show"),
                       (r"^status/(?P<id_>\d+)/withdraw/$", "status.withdraw"),

                       (r"^fold_process/(?P<sample_id>.+)", "json_client.fold_process"),
                       (r"^folded_processes/(?P<sample_id>.+)", "json_client.get_folded_processes"),

                       (r"^merge_samples$", "merge_samples.merge"),
                       )
