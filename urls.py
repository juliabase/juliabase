from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
#                       (r'^samples/edit/(?P<sample_name>.+)', 'samples.views.edit_sample'),
                       (r'^samples/(?P<sample_name>.+)', 'samples.views.show_sample'),
#                       (r'^processes/edit/(?P<process_name>.+)', 'samples.views.edit_process'),
                       (r'^admin/', include('django.contrib.admin.urls')),
                       )

if settings.DEBUG:
    urlpatterns += patterns('',
                            (r'^static_media/(?P<path>.*)$', 'django.views.static.serve',
                             {'document_root': '/home/bronger/src/chantal/media/'}),
                            )
