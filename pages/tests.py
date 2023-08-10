from django.conf import settings
from tests.tests import CustomTestCase


class PagesTestCase(CustomTestCase):
    def test_home(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_logged_user(self):
        response = self.user_client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '({user})'.format(
            user=settings.TESTS_USER))

    def test_logged_admin(self):
        response = self.admin_client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '({user})'.format(
            user=settings.TESTS_ADMIN))
        self.assertContains(response, 'Notes')

    def test_filesystems(self):
        response = self.client.get('/filesystems/')
        self.assertEqual(response.status_code, 200)

    def test_filesystems_graph(self):
        for ostmdt in ['ost', 'mdt']:
            for fs in settings.LUSTRE_FS_NAMES:
                response = self.client.get('/filesystems/graph/lustre/{fs}/{ostmdt}.json?delta=3600'.format(
                    fs=fs,
                    ostmdt=ostmdt))
                self.assertEqual(response.status_code, 200)
                self.assertJSONKeys(response, ['data', 'layout'])

    def test_logins(self):
        response = self.client.get('/logins/')
        self.assertEqual(response.status_code, 200)

    def test_logins_graph(self):
        for graphtype in ['cpu', 'memory', 'load', 'network']:
            for login in settings.LOGINS.keys():
                response = self.client.get('/logins/graph/{graphtype}/{login}.json?delta=3600'.format(
                    graphtype=graphtype,
                    login=login))
                self.assertEqual(response.status_code, 200)
                self.assertJSONKeys(response, ['data', 'layout'])

    def test_scheduler(self):
        response = self.client.get('/scheduler/')
        self.assertEqual(response.status_code, 200)

    def test_scheduler_graph(self):
        for graphtype in ['allocated_cpu', 'allocated_gpu']:
            response = self.client.get('/scheduler/graph/{graphtype}.json?delta=3600'.format(
                graphtype=graphtype))
            self.assertEqual(response.status_code, 200)
            self.assertJSONKeys(response, ['data', 'layout'])

    def test_dtns(self):
        response = self.client.get('/dtns/')
        self.assertEqual(response.status_code, 200)

    def test_dtns_graph(self):
        for graphtype in ['network']:
            for dtn in settings.DTNS.keys():
                response = self.client.get('/dtns/graph/{graphtype}/{dtn}.json?delta=3600'.format(
                    graphtype=graphtype,
                    dtn=dtn))
                self.assertEqual(response.status_code, 200)
                self.assertJSONKeys(response, ['data', 'layout'])
