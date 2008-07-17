from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns("",
                       (r"^samples/(?P<sample_name>.+)", "samples.views.sample.show"),
                       (r"^edit/6-chamber_deposition/(?P<deposition_number>.+)",
                        "samples.views.six_chamber_deposition.edit"),
                       (r"^login/$", "django.contrib.auth.views.login", {"template_name": "login.html"}),
                       (r"^logout/$", "django.contrib.auth.views.logout", {"template_name": "logout.html"}),
                       (r"^change_password/$", "django.contrib.auth.views.password_change",
                        {"template_name": "change_password.html"}),
                       (r"^change_password/done/$", "django.contrib.auth.views.password_change_done",
                        {"template_name": "password_changed.html"}),
                       (r"^admin/", include("django.contrib.admin.urls")),
                       )

if settings.DEBUG:
    urlpatterns += patterns("",
                            (r"^static_media/(?P<path>.*)$", "django.views.static.serve",
                             {"document_root": "/home/bronger/src/chantal/media/"}),
                            )
