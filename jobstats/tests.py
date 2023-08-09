from django.conf import settings
from tests.tests import CustomTestCase
from jobstats.models import JobScript


class JobstatsTestCase(CustomTestCase):
    def test_anonymous_user(self):
        # A anonymous user should be redirected to login page
        response = self.client.get('/secure/jobstats/{user}/'.format(
            user=settings.TESTS_JOBSTATS[0][0]))
        self.assertEqual(response.status_code, 302)
        response = self.client.get('/secure/jobstats/{user}/{jobid}/'.format(
            user=settings.TESTS_JOBSTATS[0][0],
            jobid=settings.TESTS_JOBSTATS[0][1]))
        self.assertEqual(response.status_code, 302)

    def test_user_jobstats_redirect(self):
        # Should redirect to the user own jobstats page
        response = self.user_client.get('/secure/jobstats/')
        self.assertRedirects(response, '/secure/jobstats/{user}/'.format(
            user=settings.TESTS_USER))

    def test_user_jobstats(self):
        # A user can see only his jobstats
        response = self.user_client.get('/secure/jobstats/{user}/'.format(
            user=settings.TESTS_USER))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Internal notes')
        self.assertContains(response, 'Your current use')
        self.assertContains(response, 'Your jobs')

    def test_admin_jobstats(self):
        # A admin user can see all jobstats
        response = self.admin_client.get('/secure/jobstats/{user}/'.format(
            user=settings.TESTS_USER))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Internal notes')

    def test_user_jobstats_graph(self):
        for graph_type in ['cpu', 'mem', 'lustre_mdt', 'lustre_ost']:
            response = self.user_client.get('/secure/jobstats/{user}/graph/{graph_type}.json'.format(
                user=settings.TESTS_USER,
                graph_type=graph_type))
            self.assertEqual(response.status_code, 200)
            self.assertJSONKeys(response, ['data', 'layout'])

    def test_user_jobstats_job_table(self):
        response = self.user_client.get('/api/jobs/?format=datatables&username={user}'.format(
            user=settings.TESTS_USER))
        self.assertEqual(response.status_code, 200)
        self.assertJSONKeys(response, ['draw', 'recordsTotal', 'recordsFiltered', 'data'])

    def test_user_jobstats_job_graph(self):
        for job in settings.TESTS_JOBSTATS:
            for graph_type in [
                'cpu', 'mem', 'lustre_mdt', 'lustre_ost',
                'infiniband_bdw', 'disk_iops', 'disk_bdw', 'disk_used', 'power',
                'gpu_power', 'gpu_memory', 'gpu_utilization',
                'gpu_memory_utilization', 'gpu_pcie', 'gpu_nvlink'
            ]:
                response = self.user_client.get('/secure/jobstats/{user}/{jobid}/graph/{graph_type}.json?step=120'.format(
                    user=job[0],
                    jobid=job[1],
                    graph_type=graph_type))
                self.assertEqual(response.status_code, 200)
                self.assertJSONKeys(response, ['data', 'layout'])

    def test_user_jobstats_job_cost(self):
        for job in settings.TESTS_JOBSTATS:
            response = self.user_client.get('/secure/jobstats/{user}/{jobid}/value/cost.json'.format(
                user=job[0],
                jobid=job[1]))
            self.assertEqual(response.status_code, 200)
            self.assertJSONKeys(response, [
                'kwh', 'cloud_cost_dollar',
                'co2_emissions_kg', 'cooling_cost_dollar', 'amortization_years',
                'electric_car_range_km', 'hardware_cost_dollar', 'electricity_cost_dollar'
            ])

    def test_user_other_jobstats(self):
        # A user cannot see other user jobstats
        response = self.user_client.get('/secure/jobstats/{user}/'.format(
            user=settings.TESTS_ADMIN))
        self.assertEqual(response.status_code, 403)

    def test_user_jobstats_job(self):
        for job in settings.TESTS_JOBSTATS:
            response = self.user_client.get('/secure/jobstats/{user}/{jobid}/'.format(
                user=job[0],
                jobid=job[1]))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'Internal notes')
            self.assertContains(response, 'Details on job')
            self.assertContains(response, '({jobid})'.format(jobid=job[1]))
            self.assertContains(response, 'Submitted job script is not available')

    def test_user_jobstats_jobscript(self):
        job = settings.TESTS_JOBSTATS[0]
        jobscript = JobScript(
            id_job=job[1],
            submit_script="""#!/bin/bash
echo 'Hello World!'
sleep 60
echo 'Bye World!'"""
        )
        jobscript.save()

        response = self.user_client.get('/secure/jobstats/{user}/{jobid}/'.format(
            user=job[0],
            jobid=job[1]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Submitted job script is not available')
        self.assertContains(response, 'Hello World!')
        self.assertContains(response, 'Line 3: sleep command is used')
