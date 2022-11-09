from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import Client


class CustomTestCase(TestCase):
    # databases = '__all__'
    databases = {'default', 'ldap'}

    @classmethod
    def setUp(self):
        self.testuser = get_user_model().objects.create_user(
            username=settings.TESTS_USER,
            password='userpassword')
        self.testadmin = get_user_model().objects.create_superuser(
            username=settings.TESTS_ADMIN,
            password='adminpassword')

        self.user_client = Client()
        self.user_client.login(username=settings.TESTS_USER, password='userpassword')

    def assertJSONKeys(self, response, keys):
        self.assertEqual(set(response.json().keys()), set(keys))
