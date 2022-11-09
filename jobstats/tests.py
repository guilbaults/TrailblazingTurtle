from django.conf import settings
from tests.tests import CustomTestCase


class JobstatsTestCase(CustomTestCase):
    def test_anonymous_user(self):
        response = self.client.get('/secure/jobstats/{user}/'.format(
            user=settings.TESTS_JOBSTATS[0][0]))
        self.assertEqual(response.status_code, 302)
        response = self.client.get('/secure/jobstats/{user}/{jobid}/'.format(
            user=settings.TESTS_JOBSTATS[0][0],
            jobid=settings.TESTS_JOBSTATS[0][1]))
        self.assertEqual(response.status_code, 302)

    def test_user_jobstats(self):
        response = self.user_client.get('/secure/jobstats/{user}/'.format(
            user=settings.TESTS_USER))
        self.assertEqual(response.status_code, 200)
