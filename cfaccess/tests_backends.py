from django.test import TestCase
from cfaccess.backends import CloudflareAccessLDAPBackend

class CloudflareAccessLDAPBackendTestCase(TestCase):
    def setUp(self):
        pass

    def test_clean_username(self):
        