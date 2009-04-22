from django.db import models
from django.contrib import admin
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _


relevance_choices = ((1, "*"), (2, "**"), (3, "***"), (4, "****"))

class Reference(models.Model):
    citation_key = models.CharField(_(u"citation key"), max_length=50, unique=True, db_index=True)
    offprint_locations = models.CharField(_(u"offprint locations"), max_length=200, blank=True)
    global_pdf_available = models.BooleanField(_(u"global PDF available"), default=False, null=True, blank=True)
    relevance = models.IntegerField(_(u"relevance"), null=True, blank=True, choices=relevance_choices)
    comments = models.TextField(_(u"comments"), blank=True, help_text=_(u"in Markdown"))
    groups = models.ManyToManyField(django.contrib.auth.models.Group, null=True, blank=True, related_name="references",
                                    verbose_name=_(u"groups"))
    users_with_personal_pdf = models.ManyToManyField(django.contrib.auth.models.User, null=True, blank=True,
                                                     related_name="references_with_personal_pdf",
                                                     verbose_name=_(u"users with personal PDF"))
    creator = models.ForeignKey(django.contrib.auth.models.User, null=True, blank=True,
                                related_name="references", verbose_name=_(u"creator"))

    class Meta:
        verbose_name = _(u"reference")
        verbose_name_plural = _(u"references")
        ordering = ["citation_key"]
        _ = lambda x: x
        permissions = (("edit_all_references", _("Can edit all references (senior user)")),)

    def __unicode__(self):
        return self.citation_key

#     @models.permalink
#     def get_absolute_url(self):
#         if self.name.startswith("*"):
#             return ("show_sample_by_id", (), {"sample_id": str(self.pk), "path_suffix": ""})
#         else:
#             return ("show_sample_by_name", [urlquote(self.name, safe="")])


admin.site.register(Reference)
