from django.conf import settings
from tests.tests import CustomTestCase


class CloudstatsTestCase(CustomTestCase):
    def test_cloudtstats_anonymous(self):
        response = self.client.get('/secure/cloudstats/')
        self.assertEqual(response.status_code, 302)

    def test_cloudtstats_user(self):
        # Normal user cannot see all projects
        response = self.user_client.get('/secure/cloudstats/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your projects')
        self.assertNotContains(response, 'All projects')

    def test_cloudstats_admin(self):
        # Admins can see all projects
        response = self.admin_client.get('/secure/cloudstats/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your projects')
        self.assertContains(response, 'All projects')

    def test_cloudstats_graph(self):
        for i in ['cpu', 'mem']:
            response = self.admin_client.get('/secure/cloudstats/graph/{i}.json?delta=3600'.format(
                i=i))
            self.assertEqual(response.status_code, 200)
            self.assertJSONKeys(response, ['data', 'layout'])

    def test_cloudstats_project(self):
        for project in settings.TESTS_CLOUD:
            response = self.admin_client.get('/secure/cloudstats/{project}/'.format(
                project=project[0]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Your instances")
            self.assertContains(response, project[1])
            self.assertContains(response, project[2])

    def test_cloudstats_project_graph(self):
        for project in settings.TESTS_CLOUD:
            for i in ['cpu', 'memory', 'disk_bandwidth', 'disk_iops', 'network_bandwidth']:
                response = self.admin_client.get('/secure/cloudstats/{project}/graph/{i}.json?delta=3600'.format(
                    project=project[0],
                    i=i))
                self.assertEqual(response.status_code, 200)
                self.assertJSONKeys(response, ['data', 'layout'])

    def test_cloudstats_instance(self):
        for project in settings.TESTS_CLOUD:
            response = self.admin_client.get('/secure/cloudstats/{project}/{instance}/'.format(
                project=project[0],
                instance=project[2]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Your instance use")

    def test_cloudstats_instance_gaph(self):
        for project in settings.TESTS_CLOUD:
            for i in ['cpu', 'memory', 'disk_bandwidth', 'disk_iops', 'network_bandwidth']:
                response = self.admin_client.get('/secure/cloudstats/{project}/{instance}/graph/{i}.json?delta=3600'.format(
                    project=project[0],
                    instance=project[2],
                    i=i))
                self.assertEqual(response.status_code, 200)
                self.assertJSONKeys(response, ['data', 'layout'])
