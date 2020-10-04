# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


from datetime import timedelta
from django.test import TestCase, override_settings
from django.test.client import Client
from samples import models
import django.utils.timezone
import institute.models as institute_models
from django.contrib.auth.models import User


@override_settings(ROOT_URLCONF="institute.tests.urls")
class DeletionTest(TestCase):
    fixtures = ["test_main"]

    @classmethod
    def setUpTestData(cls):
        cls.start = django.utils.timezone.now() - timedelta(minutes=30)
        cls.calvert = User.objects.get(username="r.calvert")
        sample = models.Sample.objects.create(name="testsample", currently_responsible_person=cls.calvert)
        cls.substrate = institute_models.Substrate.objects.create(operator=cls.calvert, timestamp=cls.start)
        sample.processes.add(cls.substrate)
        cls.split = models.SampleSplit.objects.create(operator=cls.calvert, parent=sample,
                                                      timestamp=cls.start + timedelta(minutes=10))
        sample.processes.add(cls.split)
        piece_1 = models.Sample.objects.create(name="piece-1", currently_responsible_person=cls.calvert,
                                               split_origin=cls.split)
        piece_2 = models.Sample.objects.create(name="piece-2", currently_responsible_person=cls.calvert,
                                               split_origin=cls.split)

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="r.calvert", password="12345")
        self.substrate.refresh_from_db()
        self.split.refresh_from_db()

    def test_delete_sample(self):
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-1").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertTrue(models.Process.objects.filter(pk=self.split.pk).exists())
        response = self.client.post("/samples/testsample/delete/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(models.Sample.objects.filter(name="testsample").exists())
        self.assertFalse(models.Sample.objects.filter(name="piece-1").exists())
        self.assertFalse(models.Sample.objects.filter(name="piece-2").exists())
        self.assertFalse(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertFalse(models.Process.objects.filter(pk=self.split.pk).exists())

    def test_delete_split(self):
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-1").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertTrue(models.Process.objects.filter(pk=self.split.pk).exists())
        response = self.client.post("/processes/{}/delete/".format(self.split.pk), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertFalse(models.Sample.objects.filter(name="piece-1").exists())
        self.assertFalse(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertFalse(models.Process.objects.filter(pk=self.split.pk).exists())

    def test_delete_piece_1(self):
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-1").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertTrue(models.Process.objects.filter(pk=self.split.pk).exists())
        response = self.client.post("/samples/piece-1/delete/".format(self.split.pk), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertFalse(models.Sample.objects.filter(name="piece-1").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertTrue(models.Process.objects.filter(pk=self.split.pk).exists())

    def test_delete_substrate(self):
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-1").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertTrue(models.Process.objects.filter(pk=self.split.pk).exists())
        response = self.client.post("/processes/{}/delete/".format(self.substrate.pk), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-1").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-2").exists())
        self.assertFalse(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertTrue(models.Process.objects.filter(pk=self.split.pk).exists())

    def test_delete_result_failing(self):
        result = models.Result.objects.create(operator=self.calvert, timestamp=self.start + timedelta(minutes=20))
        models.Sample.objects.get(name="piece-1").processes.add(result)
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-1").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertTrue(models.Process.objects.filter(pk=self.split.pk).exists())
        response = self.client.post("/samples/testsample/delete/".format(self.substrate.pk), follow=True)
        self.assertContains(response, "You are not allowed to delete the process “result for piece-1” because this kind of "
                            "process cannot be deleted.", status_code=401)
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=result.pk).exists())

    def test_delete_with_result(self):
        result = models.Result.objects.create(operator=self.calvert, timestamp=self.start + timedelta(minutes=20))
        models.Sample.objects.get(name="piece-1").processes.add(result)
        models.Sample.objects.get(name="14-JS-1").processes.add(result)
        self.assertTrue(models.Sample.objects.filter(name="testsample").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-1").exists())
        self.assertTrue(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=self.substrate.pk).exists())
        self.assertTrue(models.Process.objects.filter(pk=self.split.pk).exists())
        response = self.client.post("/samples/testsample/delete/".format(self.substrate.pk), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(models.Sample.objects.filter(name="testsample").exists())
        self.assertFalse(models.Sample.objects.filter(name="piece-2").exists())
        self.assertTrue(models.Process.objects.filter(pk=result.pk).exists())


@override_settings(ROOT_URLCONF="institute.tests.urls")
class DeletionFailureTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="r.calvert", password="12345")

    def test_delete_sample_too_old(self):
        response = self.client.post("/samples/14S-001/delete/")
        self.assertContains(response, "You are not allowed to delete the process “Corning glass substrate #1” "
                            "because it is older than one hour.", status_code=401)

    def test_delete_process_too_old(self):
        response = self.client.post("/processes/1/delete/")
        self.assertContains(response, "You are not allowed to delete the process “Corning glass substrate #1” "
                            "because it is older than one hour.", status_code=401)

    def test_delete_sample_not_viewable(self):
        response = self.client.post("/samples/14-JS-1/delete/")
        self.assertContains(response, "You are not allowed to view the sample since you are not in the sample&#x27;s topic, "
                            "nor are you its currently responsible person (Juliette Silverton), nor can you view all "
                            "samples.", status_code=401)


@override_settings(ROOT_URLCONF="institute.tests.urls")
class DeletionFailureAsPriviledgedUserTest(TestCase):
    fixtures = ["test_main"]

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="s.renard", password="12345")

    def test_delete_sample_not_editable(self):
        response = self.client.post("/samples/14-JS-1/delete/")
        self.assertContains(response, "You are not allowed to edit the sample “14-JS-1” (including splitting, declaring "
                            "dead, and deleting) because you are not the currently responsible person for this sample.",
                            status_code=401)
