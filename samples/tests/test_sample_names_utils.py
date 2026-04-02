from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings
from jb_common.models import Department
from samples.models import Sample, SampleAlias
from samples.utils import sample_names

class SampleNamesUtilsTest(TestCase):
    def setUp(self):
         if getattr(settings, "DEFAULT_DEPARTMENT", None):
            Department.objects.get_or_create(
                app_label=settings.DEFAULT_DEPARTMENT,
                defaults={'name': 'Test Dept'}
            )
         self.user = User.objects.create_user('testuser', 'test@test.com', 'password')
         self.sample = Sample.objects.create(
             name="TestSample",
             currently_responsible_person=self.user,
             current_location="Lab",
         )

    def test_get_sample_by_name(self):
        s = sample_names.get_sample("TestSample")
        self.assertEqual(s, self.sample)

    def test_get_sample_by_alias(self):
        SampleAlias.objects.create(name="AliasName", sample=self.sample)
        s = sample_names.get_sample("AliasName")
        self.assertEqual(s, self.sample)
    
    def test_get_sample_none(self):
        s = sample_names.get_sample("NonExistent")
        self.assertIsNone(s)

    def test_does_sample_exist(self):
        self.assertTrue(sample_names.does_sample_exist("TestSample"))
        self.assertFalse(sample_names.does_sample_exist("NonExistent"))
        
        SampleAlias.objects.create(name="AliasCheck", sample=self.sample)
        self.assertTrue(sample_names.does_sample_exist("AliasCheck"))

    def test_normalize_sample_name(self):
        SampleAlias.objects.create(name="OldName", sample=self.sample)
        # Main name
        self.assertEqual(sample_names.normalize_sample_name("TestSample"), "TestSample")
        # Alias -> Main name
        self.assertEqual(sample_names.normalize_sample_name("OldName"), "TestSample")
        # Non existent
        self.assertIsNone(sample_names.normalize_sample_name("Nothing"))
