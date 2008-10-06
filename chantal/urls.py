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
                       (r"^(?P<failed_action>.+)/permission_error$", "samples.views.main.permission_error"),
                       (r"^feeds/(?P<username>.+)$", "samples.views.feed.show"),

                       (r"^depositions/split_and_rename_samples/(?P<deposition_number>.+)",
                        "samples.views.split_after_deposition.split_and_rename_after_deposition"),
                       (r"^depositions/$", "samples.views.main.deposition_search"),
                       (r"^depositions/(?P<deposition_number>.+)$", "samples.views.main.show_deposition"),

                       (r"^samples/$", "samples.views.sample.search"),
                       (r"^samples/add/$", "samples.views.sample.add"),
                       (r"^samples/(?P<parent_name>.+)/split/", "samples.views.split_and_rename.split_and_rename"),
                       (r"^samples/(?P<sample_name>.+)/add_process/", "samples.views.sample.add_process"),
                       (r"^samples/(?P<sample_name>.+)/edit/", "samples.views.sample.edit"),
                       (r"^samples/(?P<sample_name>.+)", "samples.views.sample.show"),

                       url(r"^6-chamber_depositions/add/$", "samples.views.six_chamber_deposition.edit",
                           {"deposition_number": None}, "add_6-chamber_deposition"),
                       url(r"^6-chamber_depositions/(?P<deposition_number>.+)/edit/",
                           "samples.views.six_chamber_deposition.edit", name="edit_6-chamber_deposition"),
                       (r"^6-chamber_depositions/(?P<deposition_number>.+)", "samples.views.six_chamber_deposition.show"),

                       url(r"^large-area_depositions/add/$", "samples.views.large_area_deposition.edit",
                           {"deposition_number": None}, "add_large-area_deposition"),
                       url(r"^large-area_depositions/(?P<deposition_number>.+)/edit/",
                           "samples.views.large_area_deposition.edit", name="edit_large-area_deposition"),
                       url(r"^large-area_depositions/(?P<deposition_number>.+)", "samples.views.large_area_deposition.show"),

                       (r"^resplit/(?P<old_split_id>.+)", "samples.views.split_and_rename.split_and_rename"),
                       (r"^login$", "django.contrib.auth.views.login", {"template_name": "login.html"}),
                       (r"^logout$", "django.contrib.auth.views.logout", {"template_name": "logout.html"}),

                       (r"^sample_series/add/$", "samples.views.sample_series.new"),
                       (r"^sample_series/(?P<name>.+)/edit/$", "samples.views.sample_series.edit"),
                       (r"^sample_series/(?P<name>.+)/add_result/$", "samples.views.sample_series.add_result_process"),
                       (r"^sample_series/(?P<name>.+)$", "samples.views.sample_series.show"),

                       (r"^comments/add/$", "samples.views.comment.new"),
                       (r"^comments/(?P<process_id>.+)/edit/$", "samples.views.comment.edit"),

                       url(r"^pds_measurements/add/$", "samples.views.pds_measurement.edit", {"pd_number": None},
                           "add_pds_measurement"),
                       url(r"^pds_measurements/(?P<pd_number>\d+)/edit/$", "samples.views.pds_measurement.edit",
                           name="edit_pds_measurement"),

                       (r"^about$", "samples.views.main.about"),
                       (r"^statistics$", "samples.views.main.statistics"),
                       (r"^users/(?P<login_name>.+)$", "samples.views.main.show_user"),
                       (r"^my_layers/$", "samples.views.my_layers.edit"),
                       (r"^change_password$", "django.contrib.auth.views.password_change",
                        {"template_name": "change_password.html"}),
                       (r"^change_password/done/$", "django.contrib.auth.views.password_change_done",
                        {"template_name": "password_changed.html"}),

                       (r"^primary_keys$", "samples.views.main.primary_keys"),
                       (r"^next_deposition_number/(?P<letter>.+)$", "samples.views.main.next_deposition_number"),
                       (r"^login_remote_client$", "samples.views.main.login_remote_client"),
                       (r"^logout_remote_client$", "samples.views.main.logout_remote_client"),

                       (r"^admin/(.*)", admin.site.root),
                       )

if settings.IS_TESTSERVER:
    urlpatterns += patterns("",
                            (r"^media/(?P<path>.*)$", "django.views.static.serve",
                             {"document_root": os.path.join(settings.ROOTDIR, "media/")}),
                            )
