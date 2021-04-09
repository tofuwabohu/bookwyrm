""" test for app action functionality """
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


class UserAdminViews(TestCase):
    """ every response to a get request, html or json """

    def setUp(self):
        """ we need basic test data and mocks """
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        models.SiteSettings.objects.create()

    def test_user_admin_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.UserAdmin.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
