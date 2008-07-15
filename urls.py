from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns("",
#                       (r"^samples/edit/(?P<sample_name>.+)", "samples.views.edit_sample"),
                       (r"^samples/(?P<sample_name>.+)", "samples.views.sample.show"),
                       (r"^edit/6-chamber_deposition/(?P<deposition_number>.+)",
                        "samples.views.six_chamber_deposition.edit"),
                       (r"^login/$", "django.contrib.auth.views.login", {"template_name": "login.html"}),
                       (r"^admin/", include("django.contrib.admin.urls")),
                       )

if settings.DEBUG:
    urlpatterns += patterns("",
                            (r"^static_media/(?P<path>.*)$", "django.views.static.serve",
                             {"document_root": "/home/bronger/src/chantal/media/"}),
                            )
