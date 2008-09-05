import os.path
from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns("",
                       (r"^$", "samples.views.main.main_menu"),
                       (r"^(?P<failed_action>.+)/permission_error$", "samples.views.main.permission_error"),
                       (r"^feeds/(?P<username>.+)$", "samples.views.main.feed"),
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
                       (r"^processes/split_and_rename_samples/(?P<process_id>.+)",
                        "samples.views.split_after_process.split_and_rename_after_process"),
                       (r"^resplits/(?P<old_split_id>.+)", "samples.views.split_and_rename.split_and_rename"),
                       (r"^login$", "django.contrib.auth.views.login", {"template_name": "login.html"}),
                       (r"^logout$", "django.contrib.auth.views.logout", {"template_name": "logout.html"}),
                       (r"^sample_series/add/$", "samples.views.sample_series.new"),
                       (r"^sample_series/(?P<name>.+)/edit/$", "samples.views.sample_series.edit"),
                       (r"^sample_series/(?P<name>.+)/add_result/$", "samples.views.sample_series.add_result_process"),
                       (r"^sample_series/(?P<name>.+)$", "samples.views.sample_series.show"),
                       (r"^comments/add/$", "samples.views.comment.new"),
                       (r"^comments/(?P<process_id>.+)/edit/$", "samples.views.comment.edit"),
                       (r"^about$", "samples.views.main.about"),
                       (r"^statistics$", "samples.views.main.statistics"),
                       (r"^users/(?P<login_name>.+)$", "samples.views.main.show_user"),
                       (r"^my_layers/$", "samples.views.my_layers.edit"),
                       (r"^change_password$", "django.contrib.auth.views.password_change",
                        {"template_name": "change_password.html"}),
                       (r"^change_password/done/$", "django.contrib.auth.views.password_change_done",
                        {"template_name": "password_changed.html"}),
                       (r"^admin/(.*)", admin.site.root),
                       )

if settings.IS_TESTSERVER:
    urlpatterns += patterns("",
                            (r"^media/(?P<path>.*)$", "django.views.static.serve",
                             {"document_root": os.path.join(settings.ROOTDIR, "media/")}),
                            )
