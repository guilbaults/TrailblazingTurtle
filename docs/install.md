# Production without containers on Rocky Linux 8

RPMs required for production

* `python39-pip` (python 3.9 will be used in the virtualenv)
* `gcc` (to compile python modules)
* `python3-virtualenv`
* `python39-mod_wsgi` or use gunicorn instead of WSGI in Apache
* `python39-devel`
* `openldap-devel`
* `mariadb-devel`
* `xmlsec1` (for SAML)
* `xmlsec1-openssl` (for SAML)

Python >= 3.9 is required to fix a CVE in numpy, you can install that version on Rocky8 inside a python virtualenv

```
/usr/bin/virtualenv-3 --python="/usr/bin/python3.9" /var/www/userportal-env
```

A file in the python env need to be patched, check the diff in `ldapdb.patch`

Static files are handled by Apache and need to be collected since python will not serve them:

```
python manage.py collectstatic
```

## Apache virtualhost config for WSGI

```
<VirtualHost *:443>
  ServerName userportal.int.ets1.calculquebec.ca

  ## Vhost docroot
  DocumentRoot "/var/www/userportal"
  ## Alias declarations for resources outside the DocumentRoot
  Alias /static "/var/www/userportal-static"
  Alias /favicon.ico "/var/www/userportal-static/favicon.ico"

  ## Directories, there should at least be a declaration for /var/www/userportal

  <Directory "/var/www/userportal/">
    AllowOverride None
    Require all granted
  </Directory>

  <Directory "/var/www/userportal/static">
    AllowOverride None
    Require all granted
  </Directory>

  ## Logging
  ErrorLog "/var/log/httpd/userportal.int.ets1.calculquebec.ca_error_ssl.log"
  ServerSignature Off
  CustomLog "/var/log/httpd/userportal.int.ets1.calculquebec.ca_access_ssl.log" combined

  ## SSL directives
  SSLEngine on
  SSLCertificateFile      "/etc/pki/tls/certs/userportal.int.ets1.calculquebec.ca.crt"
  SSLCertificateKeyFile   "/etc/pki/tls/private/userportal.int.ets1.calculquebec.ca.key"
  WSGIApplicationGroup %{GLOBAL}
  WSGIDaemonProcess userportal python-home=/var/www/userportal-env python-path=/var/www/userportal/
  WSGIProcessGroup userportal
  WSGIScriptAlias / "/var/www/userportal/userportal/wsgi.py"
</VirtualHost>
```

## Apache virtualhost config for Gunicorn

In this example, Apache is running on port 8000 and Gunicorn on port 8001. Apache will receive all the requests, will handle the static files and forward the other requests to Gunicorn.

```
Listen 8000

<VirtualHost *:8000>
  DocumentRoot "/var/www/userportal"
  Alias /static "/var/www/userportal-static"

  ProxyPass / http://127.0.0.1:8001/
  ProxyPassReverse / "http://127.0.0.1:8001/"

  <Directory "/var/www/userportal/">
    AllowOverride None
    Require all granted
  </Directory>

  <Directory "/var/www/userportal/static">
    AllowOverride None
    Require all granted
  </Directory>

</VirtualHost>
```

# Django Authentication
This portal is using the standard django authentication, multiple backends are supported, we are using SAML2 and the FreeIPA backend, on different clusters. Users with the is_staff attribute can access other users pages and the `top` module. 

## SAML2
For SAML2, certificates need to be generated and the metadata.xml need a little modification.

```
openssl req -nodes -new -x509 -newkey rsa:2048 -days 3650 -keyout private.key -out public.cert
```

Download the metadata file from the IDP as metadata.xml
Our Shibboleth IDP only seems to work with Redirect binding, so we remove manually the POST binding for SingleSignOnService.

# API
An API is available to modify resources in the database. This is used by the jobscript collector. A local superuser need to be created:

```
python manage.py createsuperuser
```

The token can be created with:

```
manage.py drf_create_token
```

# Upgrades
When SQL models are modified, the automated migration script need to run once:
```
python manage.py migrate
```

# Translation
Create the .po files for french: `python manage.py makemessages -l fr`

Update all message files for all languages:
```
python manage.py makemessages -a
python manage.py makemessages -a -d djangojs
```

Compile messages: `python manage.py compilemessages`

# Deployment with Kubernetes

Kubernetes is used to serve the Django application. The production image is built with ubuntu and python3.8, Gunicorn is used to serve the application. The static files are served by nginx. The image is built using the Containerfile in the root of the repository.

To build the image manually, you can use the following command:

```
buildah bud -t userportal
```

Kaniko is used to build the image in the CI pipeline in Gitlab. The image is pushed to the registry and then deployed to the cluster. Some of the configuration files are located in the `kubernetes` directory.


