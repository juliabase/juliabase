from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

import pytest

from jb_common.models import Department


pytestmark = pytest.mark.django_db


def test_logout_link_displays_login_link():
    department = Department.objects.create(name="Logout test", app_label="iek5")
    user = User.objects.create_user(username="logout-test", password="test-only")
    user.jb_user_details.department = department
    user.jb_user_details.save()
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    response = client.get(reverse("logout"))

    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated
    assert b"Thanks for spending some quality time" in response.content
    assert f'href="{reverse("login")}"'.encode() in response.content
