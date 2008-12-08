#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Mapping URL patterns to function calls.  This is the central dispatch for
browser requests.  It takes the URL that the user chose, and converts it to a
function call – possibly with parameters.

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


:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/

"""

import os.path
from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns("",
                       (r"^$", "samples.views.main.main_menu"),
                       (r"^feeds/(?P<username>.+)", "samples.views.feed.show"),
                       (r"^my_samples/(?P<username>.+)", "samples.views.my_samples.edit"),

                       (r"^depositions/split_and_rename_samples/(?P<deposition_number>.+)",
                        "samples.views.split_after_deposition.split_and_rename_after_deposition"),
                       (r"^depositions/$", "samples.views.main.deposition_search"),
                       (r"^depositions/(?P<deposition_number>.+)", "samples.views.main.show_deposition"),

                       url(r"^samples/by_id/(?P<sample_id>\d+)(?P<path_suffix>.*)", "samples.views.sample.by_id",
                           name="show_sample_by_id"),
                       (r"^samples/$", "samples.views.sample.search"),
                       (r"^samples/add/$", "samples.views.sample.add"),
                       (r"^samples/(?P<parent_name>.+)/split/$", "samples.views.split_and_rename.split_and_rename"),
                       (r"^samples/(?P<sample_name>.+)/kill/$", "samples.views.sample_death.new"),
                       (r"^samples/(?P<sample_name>.+)/add_process/$", "samples.views.sample.add_process"),
                       (r"^samples/(?P<sample_name>.+)/edit/$", "samples.views.sample.edit"),
                       url(r"^samples/(?P<sample_name>.+)", "samples.views.sample.show", name="show_sample_by_name"),
                       (r"^bulk_rename$", "samples.views.bulk_rename.bulk_rename"),

                       url(r"^6-chamber_depositions/add/$", "samples.views.six_chamber_deposition.edit",
                           {"deposition_number": None}, "add_6-chamber_deposition"),
                       url(r"^6-chamber_depositions/(?P<deposition_number>.+)/edit/$",
                           "samples.views.six_chamber_deposition.edit", name="edit_6-chamber_deposition"),
                       (r"^6-chamber_depositions/(?P<deposition_number>.+)", "samples.views.six_chamber_deposition.show"),

                       url(r"^large-area_depositions/add/$", "samples.views.large_area_deposition.edit",
                           {"deposition_number": None}, "add_large-area_deposition"),
                       url(r"^large-area_depositions/(?P<deposition_number>.+)/edit/$",
                           "samples.views.large_area_deposition.edit", name="edit_large-area_deposition"),
                       url(r"^large-area_depositions/(?P<deposition_number>.+)", "samples.views.large_area_deposition.show"),

                       (r"^resplit/(?P<old_split_id>.+)", "samples.views.split_and_rename.split_and_rename"),
                       (r"^login$", "django.contrib.auth.views.login", {"template_name": "login.html"}),
                       (r"^logout$", "django.contrib.auth.views.logout", {"template_name": "logout.html"}),

                       (r"^sample_series/add/$", "samples.views.sample_series.new"),
                       (r"^sample_series/(?P<name>.+)/edit/$", "samples.views.sample_series.edit"),
                       (r"^sample_series/(?P<name>.+)", "samples.views.sample_series.show"),

                       url(r"^results/add/$", "samples.views.result.edit", {"process_id": None}, "add_result"),
                       url(r"^results/(?P<process_id>.+)/edit/$", "samples.views.result.edit", name="edit_result"),
                       (r"^results/(?P<process_id>.+)", "samples.views.result.show"),

                       url(r"^pds_measurements/add/$", "samples.views.pds_measurement.edit", {"pds_number": None},
                           "add_pds_measurement"),
                       url(r"^pds_measurements/(?P<pds_number>\d+)/edit/$", "samples.views.pds_measurement.edit",
                           name="edit_pds_measurement"),

                       (r"^external_operators/add/$", "samples.views.external_operator.new"),
                       (r"^external_operators/(?P<external_operator_id>.+)/edit/$", "samples.views.external_operator.edit"),
                       (r"^external_operators/(?P<external_operator_id>.+)", "samples.views.external_operator.show"),
                       (r"^external_operators/$", "samples.views.external_operator.list_"),

                       (r"^markdown$", "samples.views.markdown.sandbox"),
                       (r"^about$", "samples.views.statistics.about"),
                       (r"^statistics$", "samples.views.statistics.statistics"),
                       (r"^switch_language$", "samples.views.main.switch_language"),
                       (r"^users/(?P<login_name>.+)", "samples.views.user_details.show_user"),
                       (r"^preferences/(?P<login_name>.+)", "samples.views.user_details.edit_preferences"),
                       (r"^groups_and_permissions/(?P<login_name>.+)", "samples.views.user_details.groups_and_permissions"),
                       (r"^my_layers/(?P<login_name>.+)", "samples.views.my_layers.edit"),
                       (r"^change_password$", "django.contrib.auth.views.password_change",
                        {"template_name": "change_password.html"}),
                       (r"^change_password/done/$", "django.contrib.auth.views.password_change_done",
                        {"template_name": "password_changed.html"}),

                       (r"^groups/add/$", "samples.views.group.add"),
                       (r"^groups/$", "samples.views.group.list_"),
                       (r"^groups/(?P<name>.+)", "samples.views.group.edit"),

                       (r"^primary_keys$", "samples.views.remote_client.primary_keys"),
                       (r"^next_deposition_number/(?P<letter>.+)", "samples.views.remote_client.next_deposition_number"),
                       (r"^latest_split/(?P<sample_name>.+)", "samples.views.split_and_rename.latest_split"),
                       (r"^login_remote_client$", "samples.views.remote_client.login_remote_client"),
                       (r"^logout_remote_client$", "samples.views.remote_client.logout_remote_client"),

                       (r"^maintenance/2127ff49478d1e385867452429edbf39df986c00$",
                        "samples.views.maintenance.maintenance"),
                       (r"^admin/(.*)", admin.site.root),
                       )

if settings.IS_TESTSERVER:
    urlpatterns += patterns("",
                            (r"^media/(?P<path>.*)$", "django.views.static.serve",
                             {"document_root": os.path.join(settings.ROOTDIR, "media/")}),
                            )
