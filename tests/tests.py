from django.test import TestCase


class CustomTestCase(TestCase):
    def assertJSONKeys(self, response, keys):
        self.assertEqual(set(response.json().keys()), set(keys))
