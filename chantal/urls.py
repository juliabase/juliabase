import os.path
from django.conf.urls.defaults import *
from django.conf import settings

prefix = "^" + settings.URL_PREFIX[1:]

urlpatterns = patterns("",
                       (prefix+r"$", "samples.views.main.main_menu"),
                       (prefix+r"(?P<failed_action>.+)/permission_error$", "samples.views.main.permission_error"),
                       (prefix+r"samples/(?P<sample_name>.+)", "samples.views.sample.show"),
                       (prefix+r"6-chamber_deposition/edit/(?P<deposition_number>.+)",
                        "samples.views.six_chamber_deposition.edit"),
                       (prefix+r"6-chamber_deposition/add/$", "samples.views.six_chamber_deposition.edit",
                        {"deposition_number": None}),
                       (prefix+r"processes/split_and_rename_samples/(?P<process_id>.+)",
                        "samples.views.rename_and_split_samples.split_and_rename"),
                       (prefix+r"login/$", "django.contrib.auth.views.login"),
                       (prefix+r"logout/$", "django.contrib.auth.views.logout", {"template_name": "logout.html"}),
                       (prefix+r"about/$", "samples.views.main.about"),
                       (prefix+r"change_password/$", "django.contrib.auth.views.password_change",
                        {"template_name": "change_password.html"}),
                       (prefix+r"change_password/done/$", "django.contrib.auth.views.password_change_done",
                        {"template_name": "password_changed.html"}),
                       (prefix+r"admin/", include("django.contrib.admin.urls")),
                       )

if settings.IS_TESTSERVER:
    urlpatterns += patterns("",
                            (r"^media/(?P<path>.*)$", "django.views.static.serve",
                             {"document_root": os.path.join(settings.ROOTDIR, "media/")}),
                            )
