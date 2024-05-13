A test and developpement environment using the local `uid` resolver and dummies allocations is provided to test the portal.

To use it, copy `example/local.py` to `userportal/local.py`. The other functions are documented in `common.py` if any other overrides are needed for your environment.

To quickly test and bypass authentication, add this line to `userportal/settings/99-local.py`. Other local configuration can be added in this file to override the default settings.

```
AUTHENTICATION_BACKENDS.insert(0, 'userportal.authentication.staffRemoteUserBackend')
```

This bypasses the authentication and will use the `REMOTE_USER` header or env variable to authenticate the user. This is useful to be able to try the portal without having to set up a full IDP environment. The REMOTE_USER method can be used when using some IDP such as Shibboleth. SAML2 based IDP is now the preferred authentication method for production.

Examine the default configuration in `userportal/settings/` and override any settings in `99-local.py` as needed.

Then you can launch the example server with:

```
REMOTE_USER=someuser@alliancecan.ca affiliation=staff@alliancecan.ca python manage.py runserver
```

This will run the portal with the user `someuser` logged in as a staff member.

Automated Django tests are also available, they can be run with:

```
python manage.py test
```

This will test the various modules, including reading job data from the Slurm database and Prometheus. A temporary database for Django is created automatically for the tests. Slurm and Prometheus data are read directly from production data with a read-only account. A representative user, job and account need to be defined to be used in the tests, check the `90-tests.py` file for an example.