from django.test.runner import DiscoverRunner


# From https://stackoverflow.com/questions/61933056/skipping-django-test-database-creation-for-read-only-externally-managed-high-s
def should_create_db(db_name):
    # analyse db_name, a key from DATABASES, to determine whether a test
    # database should be created
    return db_name != 'slurm'


class CustomTestRunner(DiscoverRunner):
    # override method from superclass to selectively skip database setup
    def setup_databases(self, **kwargs):
        # 'aliases' is a set of unique keys from settings DATABASES dictionary
        aliases = kwargs.get('aliases')
        filtered = set([i for i in aliases if should_create_db(i)])
        kwargs['aliases'] = filtered
        # 'aliases' now contains only keys which trigger test database creation
        return super().setup_databases(**kwargs)

    # there was no need to override teardown_databases()
