from django.conf import settings
from tests.tests import CustomTestCase


class AccountstatsTestCase(CustomTestCase):
    def test_accountstats(self):
        response = self.client.get('/secure/accountstats/')
        self.assertEqual(response.status_code, 302)

        response = self.user_client.get('/secure/accountstats/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your accounts')
        self.assertContains(response, 'Allocations')

        # verify that the TESTS_USER can see its own accounts
        for alloc in settings.TESTS_ACCOUNTS:
            if alloc[0] == settings.TESTS_USER:
                self.assertContains(response, alloc[1])

    def test_accountstats_admin(self):
        # admin user can see all accounts
        for alloc in settings.TESTS_ACCOUNTS:
            response = self.admin_client.get('/secure/accountstats/{account}/'.format(
                account=alloc[1]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Account use of {account}".format(
                account=alloc[1]))

            if alloc[2] == 'cpu':
                self.assertContains(response, 'CPUs were allocated')
            else:
                self.assertContains(response, 'GPUs were allocated')

    def test_accountstats_graph(self):
        for alloc in settings.TESTS_ACCOUNTS:
            graphs = ['cpu_allocated', 'cpu_used', 'cpu_wasted',
                      'mem_allocated', 'mem_used', 'mem_wasted',
                      'lustre_mdt', 'lustre_ost']
            if alloc[2] == 'gpu':
                graphs += ['gpu_priority', 'gpu_allocated', 'gpu_used', 'gpu_wasted']
            else:
                graphs += ['cpu_priority']

            for graph_type in graphs:
                response = self.user_client.get('/secure/accountstats/{account}/graph/{graph_type}.json'.format(
                    account=alloc[1],
                    graph_type=graph_type))
                self.assertEqual(response.status_code, 200)
                self.assertJSONKeys(response, ['data', 'layout'])
