from django.conf import settings
from tests.tests import CustomTestCase


class UsersummaryTestCase(CustomTestCase):
    def test_user_usersummary_redirect(self):
        response = self.user_client.get('/secure/usersummary/')
        self.assertRedirects(response, '/secure/usersummary/{user}/'.format(
            user=settings.TESTS_USER))

    def test_user_usersummary(self):
        response = self.user_client.get('/secure/usersummary/{user}/'.format(
            user=settings.TESTS_USER))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your filesystem quotas')
        self.assertContains(response, 'Your latest 10 jobs')

    def test_admin_usersummary(self):
        response = self.admin_client.get('/secure/usersummary/{user}/'.format(
            user=settings.TESTS_USER))
        self.assertEqual(response.status_code, 200)

    def test_user_other_usersummary(self):
        response = self.user_client.get('/secure/usersummary/{user}/'.format(
            user=settings.TESTS_ADMIN))
        self.assertEqual(response.status_code, 403)
