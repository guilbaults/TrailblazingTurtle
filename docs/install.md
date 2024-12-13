# Installation

Before installing in production, [a test environment should be set up to test the portal](development.md). This makes it easier to fully configure each module and modify as needed some functions like how the allocations are retrieved. Installing Prometheus and some exporters is also recommended to test the portal with real data.

The portal can be installed directly on a Rocky8 Apache web server or with Nginx and Gunicorn. The portal can also be deployed as a container with Podman or Kubernetes. Some scripts used to deploy both Nginx and Django containers inside the same pod are provided in the `podman` directory.
The various recommendations for any normal Django production deployment can be followed.

[Deploying Django](https://docs.djangoproject.com/en/5.0/howto/deployment/)

The database should support UTF8. With MariaDB, the default collation can be changed with the following command:

```
ALTER DATABASE userportal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Migration scripts will also ensure that the tables and columns are converted to the correct collation.

# Production with containers
Using containers is the recommended way to deploy the portal. The container is automatically built in the CI pipeline and pushed to the Github registry. This container is handling the django application. The static files are served by a standard Nginx container. Both containers are deployed in the same pod with a shared volume containing the static files.

# Production without containers on Rocky Linux 8

RPMs required for production

* `python39-pip` (python 3.9 will be used in the virtualenv)
* `gcc` (to compile python modules)
* `python3-virtualenv`
* `python39-mod_wsgi` or use Gunicorn instead of WSGI in Apache
* `python39-devel`
* `openldap-devel`
* `mariadb-devel`
* `xmlsec1` (for SAML)
* `xmlsec1-openssl` (for SAML)

Python >= 3.9 is required to fix a CVE in NumPy, you can install that version on Rocky8 inside a python virtualenv

```
/usr/bin/virtualenv-3 --python="/usr/bin/python3.9" /var/www/userportal-env
```

A file in the python env needs to be patched, check the diff in `ldapdb.patch` if using the ldapdb module.

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

In this example, Apache is running on port 8000 and Gunicorn on port 8001. Apache will handle the static files and forward the other requests to Gunicorn. An external load balancer is used to forward the requests from ports 80/443 to Apache on port 8000.

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
Our Shibboleth IDP only seems to work with Redirect binding, so we manually remove the POST binding for SingleSignOnService.

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
When SQL models are modified, the automated migration script needs to run once:
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

Kubernetes is used to serve the Django application. The production image is built with ubuntu and python3.8, Gunicorn is used to serve the application. The static files are served by Nginx. The image is built using the Containerfile in the root of the repository.

To build the image manually, you can use the following command:

```
buildah bud -t userportal
```

Kaniko is used to build the image in the CI pipeline in Gitlab. The image is pushed to the registry and then deployed to the cluster. Some of the configuration files are located in the `kubernetes` directory.
