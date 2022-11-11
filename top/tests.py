from django.conf import settings
from tests.tests import CustomTestCase


class TopTestCase(CustomTestCase):
    def test_user_top(self):
        response = self.user_client.get('/secure/top/')
        self.assertEqual(response.status_code, 403)

    def test_admin_top(self):
        response = self.admin_client.get('/secure/top/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Computes')

    def test_top_compute(self):
        response = self.admin_client.get('/secure/top/compute/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Top compute users')
        self.assertContains(response, '<th scope="col">Allocated cores</th>')
        # Check there is a link to jobstats within the table
        self.assertContains(response, '/secure/jobstats/')

    def test_top_gpucompute(self):
        response = self.admin_client.get('/secure/top/gpucompute/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Top GPU compute users')
        self.assertContains(response, '<th scope="col">Allocated GPUs</th>')
        self.assertContains(response, '/secure/jobstats/')

    def test_top_largemem(self):
        response = self.admin_client.get('/secure/top/largemem/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Users on largemem')
        self.assertContains(response, '<th scope="col">Allocated cores</th>')
        self.assertContains(response, '/secure/jobstats/')

    def test_top_lustre(self):
        response = self.admin_client.get('/secure/top/lustre/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Top Lustre users')
        for fs in settings.LUSTRE_FS_NAMES:
            self.assertContains(response, '<h2>{fs}</h2>'.format(fs=fs))
            json_mdt = self.admin_client.get('/secure/top/lustre/graph/lustre_mdt/{fs}.json'.format(fs=fs))
            self.assertEqual(json_mdt.status_code, 200)
            self.assertJSONKeys(json_mdt, ['lines', 'layout'])

            json_ost = self.admin_client.get('/secure/top/lustre/graph/lustre_ost/{fs}.json'.format(fs=fs))
            self.assertEqual(json_ost.status_code, 200)
            self.assertJSONKeys(json_ost, ['lines', 'layout'])
