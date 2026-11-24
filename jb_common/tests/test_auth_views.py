from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from jb_common.models import Department


class LogoutViewTest(TestCase):

    def test_logout_link_displays_login_link(self):
        department = Department.objects.create(name="Logout test", app_label="iek5")
        user = User.objects.create_user(username="logout-test", password="test-only")
        user.jb_user_details.department = department
        user.jb_user_details.save()
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        response = client.get(reverse("logout"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "Thanks for spending some quality time")
        self.assertContains(response, f'href="{reverse("login")}"')
