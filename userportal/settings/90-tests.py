TEST_RUNNER = 'userportal.testrunner.CustomTestRunner'

TESTS_USER = 'user01'
TESTS_ADMIN = 'admin'

# users and jobID to test
TESTS_JOBSTATS = [('user01', 1)]

# slurm accounts to test in accountstats in username, account name and allocation type format
TESTS_ACCOUNTS = [('user01', 'def-user01_cpu', 'cpu')]

# openstack allocations to test in project name, vm name and vm uuid format
TESTS_CLOUD = [('CCInternal-Beluga', 'login', '141046a7-c524-4ba7-8473-d7c77cebc5f8')]
